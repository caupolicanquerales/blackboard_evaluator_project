"""The TDD loop and the dependency-graph queue drain.

``drain_queue`` is backend-agnostic: the entry scripts pass ``invoke_for_task``
(the backend's agent call) and it wires per-task invoke/verify closures around
the skill dispatchers and the verification gate.
"""
import heapq
import json
import re
import shutil
import time
from pathlib import Path

import attempt_ledger
import assembly
import dispatchers
import refactor_audit
import settings
import task_queue
import test_gate
import tasks
import telemetry
import verification
import workspace



BATCH_MIN_PEERS = 4
BATCH_MAX = 4


def _pending_symbols_of(project, exclude_id):
    """Types a sibling task still has to produce for this domain.

    Includes tasks quarantined in error/: a class whose owner waits there is a RESTORE
    problem (--retry), not a scheduling hole - consumers must defer, never abort the
    domain over it. Strict by design: only a task's EXPORT counts - intent-named types
    have no file and no producer, and counting them made the deferral rule wait forever
    on a symbol nobody would ever write.
    """
    names = set()
    for folder in (settings.QUEUE_DIR, settings.ERROR_DIR):
        for f in folder.glob(f"T2-*-{project}.json"):
            try:
                peer = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(peer, dict) and peer.get("id") != exclude_id:
                name = tasks.exported_product(peer)
                if name:
                    names.add(name)
    return names


def _resolvable_types(project, exclude_id):
    """Types the domain can still legitimately grow: exports of units in flight (queue
    or quarantine — a class whose owner waits in error/ is a RESTORE problem (--retry),
    not a hole) and names declared on disk. File stems AND nested declarations count:
    a collaborator woven as a NESTED type (record Row inside Box.java) is
    declared; visibility/import mismatches across units are code defects the retry loop
    fixes, not holes. source_files() is layout- and extension-agnostic."""
    resolvable = _pending_symbols_of(project, exclude_id)
    project_root = workspace.project_root_for(project)
    resolvable |= {f.stem for f in test_gate.source_files(project_root)}
    for src in test_gate.source_files(project_root):
        try:
            resolvable |= set(re.findall(r"\b(?:class|interface|enum|record)\s+([A-Z]\w*)",
                                         src.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return resolvable


_SYMBOL_SHAPE_RE = re.compile(r"symbol:\s+(?:class|variable|method)\s+([A-Za-z]\w*)")
_LOCATION_PACKAGE_RE = re.compile(r"location:\s+package\s+([\w.]+)")


def _excerpt_package_locations(result):
    """{symbol: {packages}} for javac 'cannot find symbol' errors located in a PACKAGE.

    javac prints `location: package X` ONLY when X RESOLVES - the package exists on the
    classpath and merely lacks the class. That is a payload defect of the importing file:
    no planner can schedule a unit that exports a class into someone else's library, and
    the importing unit's own gate must bounce its coder (2026-11-18 live: a coder wrote
    import org.springframework.r2dbc.core.Parameters; the classification read the bare
    token as a scheduling hole and aborted a healthy domain at task 8 of ~110).
    """
    out = {}
    pending = None
    for line in (result.get("excerpt") or []):
        text = str(line).replace("[ERROR]", "").strip()
        hit = _SYMBOL_SHAPE_RE.search(text)
        if hit:
            pending = hit.group(1)
            continue
        hit = _LOCATION_PACKAGE_RE.search(text)
        if hit and pending:
            out.setdefault(pending, set()).add(hit.group(1))
            pending = None
    return out


def _unresolvable_missing(result, task):
    """Missing symbols no queued task exports and no source on disk declares.

    These are scheduling holes, not code defects: deferring on them livelocks the
    domain (the owner may be quarantined, or may never have existed). The orchestrator
    aborts loudly instead of spinning, and names the remedy.
    """
    if not isinstance(result, dict):
        return []
    # Fully qualified JDK names inside javac method signatures (the arity description of
    # `cannot find symbol: method of(java.lang.String,java.time.Instant,double)`) tokenize
    # into bare type names: strip them, then subtract the known JDK short names, or a
    # contract-arity defect reads as a scheduling hole and aborts a healthy run.
    raw = " ".join(str(item) for item in (result.get("missing_symbols") or []))
    raw = re.sub(r"\b(?:java|javax|jakarta)\.[\w.]*", "", raw)
    # Only TYPE-shaped symbols can be scheduling holes. Lowercase tokens are javac
    # method/variable mismatches between woven units: real code defects the normal
    # retry loop fixes with the javac log, not aborts.
    tokens = {t for t in _identifier_tokens(raw) if t[:1].isupper() and tasks.is_type_shape(t)}
    tokens -= test_gate.java_lang_names() | set(test_gate.JDK_TYPES)
    if not tokens:
        return []
    resolvable = _resolvable_types(task.get("project", ""), task["id"])
    # A symbol the log attaches to a resolvable surface (a nested type located in
    # class Box, a method located on a variable of type Box<T>) comes
    # with that surface once its producer lands or is charged: conditional, not a hole.
    for demand in (result.get("member_demands") or []):
        if isinstance(demand, dict) and (demand.get("owner") in resolvable
                                         or demand.get("owner") == tasks.exported_product(task)):
            tokens -= _identifier_tokens(str(demand.get("member") or ""))
    # A class the log locates INSIDE an existing classpath package is a code defect of the
    # importing unit, never a schedulable type (see _excerpt_package_locations). Only a
    # package that is itself unknown is left as a possible planning hole, conservatively.
    located = _excerpt_package_locations(result)
    if located:
        ext = test_gate.external_type_index(workspace.project_root_for(task.get("project", "")))
        ext_packages = {fqn.rsplit(".", 1)[0] for names in ext.values() for fqn in names}
        for token in list(tokens):
            for pkg in located.get(token, ()):
                if pkg in ext_packages:
                    tokens.discard(token)
                    break
    return sorted(tokens - resolvable)


def _queued_main_file_owners(project):
    """{production file basename: task id} for one domain, queued OR quarantined.

    A stage-2 task's `path` IS the production file it writes - in every layout and
    language - so ownership needs no extension or src/main assumption: it comes from
    the task records themselves. Quarantined owners count: their file is pending a
    --retry restore, and a consumer whose blame names one defers instead of burning
    its own attempts on a symbol that will return.
    """
    owners = {}
    for folder in (settings.QUEUE_DIR, settings.ERROR_DIR):
        for f in folder.glob(f"T2-*-{project}.json"):
            try:
                peer = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            path = str(peer.get("path", "")).replace("\\", "/")
            if path:
                owners[path.split("/")[-1]] = peer.get("id")
    return owners


def _sibling_payloads_pending(task):
    """Ids of same-domain stage-2 tasks still without a woven payload.

    Surefire compiles every test source of the module, so a gate run while a sibling unit is
    still un-implemented can only fail on that sibling's symbols. Weaving is cheap and the
    gate is not: the orchestrator defers the gate until every payload of the domain exists,
    then one wave of gates decides the units. Without this, a pass costs one full build per
    unit and the domain never converges, because each unit's failure belongs to a peer that
    was never run.

    A QUARANTINED sibling with its payload DISCARDED counts too: its class is absent from
    the tree exactly like an unwoven one, and the restore loop gives it a re-emit attempt -
    charging peers for the hole in the meantime is the storm the ledger then feeds (measured
    live 2026-11-12: three mutually-referencing units cycled restore -> 3 blind charges ->
    discard -> repeat, while every bystander's gate ran against the partial tree).
    """
    project = task.get("project", "")
    pending = [pid for pid in dispatchers.payloadless_t2_ids(project) if pid != task["id"]]
    for f in settings.ERROR_DIR.glob(f"T2-*-{project}.json"):
        pid = f.name.split("-")[0] + "-" + f.name.split("-")[1]
        if pid != task["id"] and not (settings.ROOT / "blackboard" / "coder-changes"
                                      / f"{pid}.json").is_file():
            pending.append(pid)
    return pending


def _testless_peers(task):
    """This task plus same-domain stage-1 tasks whose test file is not on disk yet.
    Writing distinct test files cannot race (the shared target/ risk is the RUN, and
    each unit still runs its own red probe); the batch message carries each unit's
    collaborator table, so testers share the cold start - skills, manifest, baseline -
    that a per-unit session pays twenty times over."""
    root = workspace.project_root_for(task["project"])
    same = []
    for f in sorted(settings.QUEUE_DIR.glob(f"T1-*-{task['project']}.json")):
        try:
            peer = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(peer, dict) or peer.get("id") == task["id"]:
            continue
        path = str(peer.get("path", ""))
        if path and not (root / path).is_file():
            same.append(peer)
    return [task] + sorted(same, key=lambda p: str(p.get("path")))


def _payloadless_peers(task):
    """This task plus same-domain stage-2 tasks still lacking a coder payload."""
    mine = dispatchers.payloadless_t2_ids(task.get("project", ""))
    same = []
    for peer_id in sorted(mine):
        if peer_id == task["id"]:
            continue
        for f in settings.QUEUE_DIR.glob(f"{peer_id}-*.json"):
            try:
                peer = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(peer, dict) and peer.get("project") == task.get("project"):
                same.append(peer)
    ordered = [task] + sorted((p for p in same if p.get("id") != task["id"]),
                              key=lambda p: str(p.get("path")))
    return ordered


class DeferredTask(Exception):
    """Stage-2 verification blocked by not-yet-implemented peer tasks; retry next pass."""


class FatalPipeline(Exception):
    """A deterministic check found a failure no agent can fix; abort before spending more tokens.

    Example: tests import packages absent from the scaffold's classpath. Only the build file
    can add them, and stage 2 may not edit it, so every gate of the domain would fail forever.
    """


def _failure_signature(reason):
    """Digit-normalized identity of a gate failure (status, blamed files, messages).

    Line/column shifts and test counters move when a payload shifts - the defect does
    not. Two failures sharing a signature are the engine's provable repeat: a further
    coder session re-sends the same transcript against the same contract to re-derive
    the same failure, which is exactly the T2 token storm (one unit, 7 paid sessions,
    identical blame). Pure text: nothing here knows a toolchain.
    """
    import re
    text = re.sub(r"\d+", "#", str(reason or ""))
    return " ".join(text.split()).lower()[:1200]


def _tdd_attempt_state(task):
    """(contract, consumed, rejections, last_signature) from the attempt ledger.

    A moved contract (task record, red record or AST contract bytes) resets the memory:
    past failures describe work that no longer exists. An exhausted SAME-contract unit
    back in the queue (a --retry restore) gets exactly one informed extra attempt
    instead of a fresh blind three-session storm.
    """
    ledger = attempt_ledger.read(task["id"])
    contract = attempt_ledger.contract_hash(task)
    consumed = int(ledger.get("consumed") or 0)
    rejections = int(ledger.get("bounces") or 0)
    last_sig = ledger.get("signature") or None
    if ledger and ledger.get("contract") != contract:
        consumed, rejections, last_sig = 0, 0, None
    return ledger, contract, consumed, rejections, last_sig


def _missing_artifact_problem(task, ok):
    """The 'session wrote its file' guard, as a decision a test can reach.
    Only stages whose CONTRACT is "write this recorded file" are judged by it:
    tester, evaluator, scaffold. Stage 2 coders weave through the AST tool (the
    tree moves per payload, not per session), and stage 4 assembly is judged by
    its deterministic BOOT GATE alone - the mandated composition-root repair may
    MOVE the entry class to the shared ancestor package, retiring the path
    recorded at emit time (seed-002 rerun 13:51: the correct move was quarantined
    as 'was not created' and only self-healed because the per-pass reschedule
    re-emitted the task with the FRESH detected path).
    Returns a reason string or None."""
    if not ok or task.get("stage") in (settings.TDD_STAGE, settings.ASSEMBLY_STAGE):
        return None
    expected = workspace.project_root_for(task["project"]) / str(task.get("path", ""))
    if expected.exists():
        return None
    return f"agent finished but {task['path']} was not created"


def execute_with_tdd(task, invoke, verify):
    """Run one task. Stage 2 retries the coder with the verification log, up to MAX_TDD_RETRIES.

    invoke(feedback) -> (ok, reason): runs the agent and checks its output exists.
    verify() -> (ok, reason): for stage 2 first weaves the coder payload into the
    source tree, then re-runs the recorded test (green gate), then the build gate.
    Agent failures are not retried; only verification failures are. A `weave-reject:`
    reason is the WEAVER TOOL refusing the payload shape (the unit's code never ran),
    so it is bounced straight back to the coder without consuming a TDD attempt.

    Stage 2 additionally answers to the attempt ledger (``attempt_ledger``): attempts
    and bounces are consumed for the unit's LIFETIME under its contract, not per pass;
    a failure whose signature repeats a recorded one short-circuits the remaining
    attempts; and a restored unit starts its first session INFORMED - by the ledger's
    last failure (no payload on disk) or, when a payload survives, by a FREE
    re-verification that either closes the unit unbilled (green), closes it at zero
    sessions (failure already shown to a coder), or informs the granted attempt with
    the replayed verdict itself.
    """
    is_tdd = task["stage"] == settings.TDD_STAGE
    attempts = settings.MAX_TDD_RETRIES if task["stage"] in (settings.TDD_STAGE,
                                                             settings.ASSEMBLY_STAGE) else 1
    ledger, contract, consumed, rejections, last_sig = (
        _tdd_attempt_state(task) if is_tdd else ({}, "", 0, 0, None))
    granted_informed = False
    if is_tdd and consumed >= attempts:
        print(f"[tdd ] {task['id']} ledger holds {consumed} consumed attempts for an "
              "unchanged contract; granting one informed attempt")
        consumed = attempts - 1
        granted_informed = True
    feedback = None
    if is_tdd and last_sig and ledger.get("reason"):
        payload = settings.ROOT / "blackboard" / "coder-changes" / f"{task['id']}.json"
        if not payload.is_file():
            feedback = str(ledger["reason"])
            attempt_ledger.write(task["id"], fed=last_sig)
            print(f"[tdd ] {task['id']} no payload on disk: first session starts "
                  "informed by the ledger's last failure")
        elif granted_informed:
            # A granted informed attempt must NEVER be spent on the blind skip-agent
            # replay: it re-derives the memo verdict and burns the grant (a restored unit
            # was once charged 0 sessions there, its demand never shown to any coder).
            # Run the re-verification
            # FIRST, for free: green closes the unit unbilled (the §13.1 win), an
            # already-shown failure closes out at zero sessions, and anything else
            # INFORMS the granted attempt with the replay's own verdict.
            try:
                replay_ok, replay_reason = verify()
            except DeferredTask:
                raise                       # deferral charges nothing; the grant survives
            if replay_ok:
                attempt_ledger.clear(task["id"])
                print(f"[tdd ] {task['id']} restored re-verification: green, no session billed")
                return True, ""
            replay_sig = _failure_signature(replay_reason)
            if ledger.get("fed") and replay_sig == ledger.get("fed"):
                print(f"[tdd ] {task['id']} replay repeats an already-informed failure: "
                      "closing out with zero sessions")
                return False, f"{replay_reason} [failure already informed to a coder session]"
            feedback = str(replay_reason)
            attempt_ledger.write(task["id"], fed=replay_sig)
            print(f"[tdd ] {task['id']} replay failed on a demand never shown to the "
                  "coder: the granted attempt now runs INFORMED")
    reason = ""

    def _persist(charged, bounces, last_reason=None, sig=None):
        if not is_tdd:
            return
        fields = {"contract": contract, "consumed": charged, "bounces": bounces}
        if last_reason is not None:
            fields["reason"] = str(last_reason)[:1500]
            fields["signature"] = sig
        attempt_ledger.write(task["id"], **fields)

    # The grant is SPENT only now, at the moment the attempt actually bills a coder
    # session. Free replay paths that ran before (green close, already-shown close,
    # deferral) must NOT consume it: run5-run8 measured grants 8/3 and 9/3 on units
    # whose grants were all closed at zero sessions - the cap was being eaten by the
    # very mechanism designed to spend nothing.
    if granted_informed:
        attempt_ledger.write(task["id"],
                             grants=int((attempt_ledger.read(task["id"]).get("grants")
                                         or 0)) + 1)

    while consumed < attempts:
        ok, reason = invoke(feedback)
        if not ok:
            return False, reason
        if is_tdd:
            # a finished session may have written this unit's payload
            dispatchers.invalidate_payload_cache()
        try:
            ok, reason = verify()
        except DeferredTask:
            _persist(consumed, rejections)   # deferral charges nothing; keep the memory
            raise
        if ok:
            attempt_ledger.clear(task["id"])
            return True, ""
        if reason.startswith("weave-reject") and rejections < settings.MAX_WEAVE_REJECT_BOUNCES:
            rejections += 1
            print(f"[tdd ] {task['id']} payload rejected by the weaver (bounce "
                  f"{rejections}/{settings.MAX_WEAVE_REJECT_BOUNCES}); re-asking coder "
                  "without charging an attempt")
            _persist(consumed, rejections)
            feedback = reason
            continue
        # weave-reject past the bounce cap behaves like any gate failure: it charges
        consumed += 1
        sig = _failure_signature(reason) if is_tdd else None
        _persist(consumed, rejections, reason, sig)
        if is_tdd and sig and sig == last_sig:
            remaining = attempts - consumed
            if remaining > 0:
                print(f"[tdd ] {task['id']} gate failure repeats a recorded failure "
                      f"(same signature); not burning {remaining} further coder session(s)")
            reason = f"{reason} [failure signature identical to a previous attempt's]"
            break
        last_sig = sig
        feedback = reason
        if consumed < attempts:
            attempt_ledger.write(task["id"], fed=sig)
            print(f"[tdd ] {task['id']} verification failed (attempt {consumed}/{attempts}); "
                  "retrying coder with log")
    if attempts > 1:
        reason = f"TDD failed after {attempts} attempts: {reason}"
    return False, reason


def _t3_foreign_symbols(task, reason):
    """CamelCase symbols the evaluator's module build misses while a LIVE sibling T2
    unit still owns them (queued OR quarantined).

    The evaluator gate compiles the WHOLE module: while the owner of CorrelationContext
    was being re-attempted, thirteen evaluators died - and were CHARGED - on that peer's
    absence (seed-002 rerun 15:30: collateral storm with zero information value). The
    reason string is a hint here, not grammar: intersection with real pending exports is
    what defers, and deferral bills nothing.
    """
    toks = {t for t in _identifier_tokens(str(reason or ""))
            if t[:1].isupper() and tasks.is_type_shape(t)}
    return toks & _pending_symbols_of(task.get("project", ""), task.get("id", ""))


def _reopen_contract_regression(result, task):
    """Contract-regression reopen (17:04 live shape): the module-wide compile error
    sits in the MAIN file of a COMPLETED unit - it wove green against an older binding
    and a later weave moved that binding under it. That file is the root defect, but a
    completed task is invisible to every deferral rule, so live peers wait on it
    forever and the drain can only stall. Hand it back to its owner's attempt budget
    (board state only - payload and ledger stay; the engine re-adjudicates honestly).
    Returns True when at least one unit was reopened."""
    if not isinstance(result, dict) or result.get("status") not in ("compile_error", "error"):
        return False
    blamed = {name for name, _ in test_gate.error_locations(result)}
    if not blamed:
        return False
    completed = {}
    for f in settings.COMPLETE_DIR.glob("T2-*.json"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rec, dict) or rec.get("project") != task.get("project"):
            continue
        path = str(rec.get("path", "")).replace("\\", "/")
        if path:
            completed[path.split("/")[-1]] = str(rec.get("id", ""))
    hits = sorted({completed[name] for name in blamed if name in completed} - {task["id"]})
    reopened = False
    for tid in hits[:2]:                      # bounded board churn per verdict
        if task_queue.reopen_completed(tid):
            reopened = True
    return reopened


_TERMINAL_SUITE_SEEN = set()
_TERMINAL_T4_ATTRIBUTED = set()


def _safe_read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def terminal_suite_gate():
    """TERMINAL SUITE gate (live 2026-11-16 10:52 shape). The stage-3 evaluator and the
    stage-4 assembler edit production files AFTER the last wave gate ran: each is judged
    only by what it owns (the scoped final test, the boot smoke). When such an edit
    breaks a PEER's frozen test no gate ever fires again - the board fell silent at
    queue 0 while the delivered suite was red, the same exit-lie family as 2026-11-12's
    "89/96 + boot green, tree does not compile". On a quiet board the pipeline runs the
    WHOLE frozen suite over the delivered tree (the wave's own memoized verdict, keyed
    by tree fingerprint: an unchanged tree costs zero builds), attributes every red
    class to its producing unit through the stage-1 pair (class stem == test file
    stem, the same stem-equality the wave gate uses) and reopens the COMPLETED owners
    onto their attempt budgets. Reds owned by quarantined units are left to the normal
    retry path; ownerless reds are NAMED in the report - a red nobody owns is an
    operator fact, not board silence. Returns the reopened ids."""
    reopened = []
    # include_error: a red class whose OWNER is quarantined must read as "the
    # quarantine owns it" (deferred), not as "NO producing unit" - the owner map is
    # built from twos, and excluding error records made the quarantined owner
    # invisible, dressing a known quarantine up as an ownerless mystery (2026-11-16).
    index = task_queue.load_index(include_error=True)
    error_ids = {str(rec.get("id")) for f in settings.ERROR_DIR.glob("*.json")
                 if isinstance(rec := _safe_read(f), dict)}
    projects = sorted({str(rec.get("project", "")) for rec in index.values()
                       if str(rec.get("project", ""))})
    for slug in projects:
        twos = [(tid, rec) for tid, rec in sorted(index.items())
                if str(rec.get("project", "")) == slug
                and int(rec.get("stage") or 0) == settings.TDD_STAGE]
        if not twos:
            continue
        root = workspace.project_root_for(slug)
        if not root.is_dir():
            continue
        command = ""
        for _, rec in twos:
            record = test_gate.red_phase_record(rec) or {}
            command = str(record.get("command") or "").strip()
            if command:
                break
        suite = test_gate._suite_command(command) if command else None
        if not suite:
            continue
        fixed = test_gate.repair_test_imports(root)
        if fixed:
            print(f"[suite ] {slug}: repaired missing imports in {fixed} test file(s)")
        fp = test_gate._tree_fingerprint(root)
        # Same stamp the per-unit wave gate uses: a tree the wave already judged is
        # served from cache; a tree an evaluator/assembler moved re-runs ONCE.
        stamp = f"{slug}-{test_gate.WAVE_GRAMMAR}-{fp}"
        cache_file = settings.GATE_CACHE_DIR / f"wave-{stamp}.json"
        data = None
        if cache_file.is_file():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = None
        if data is None:
            data = test_gate._run_suite_once(root, suite, stamp)
        if not isinstance(data, dict):
            continue
        if (data.get("status") == "error" and not (data.get("counts") or {}).get("run")
                and test_gate._fork_boot_corruption(root)):
            # same refusal as the per-unit wave door: a fork that died on corrupted
            # build output is a tooling wound, not a verdict on the delivered tree
            cache_file.unlink(missing_ok=True)
            shutil.rmtree(root / "target", ignore_errors=True)
            data = test_gate._run_suite_once(root, suite, stamp)
            if not isinstance(data, dict):
                continue
        classes = data.get("classes") or {}
        reds = sorted(str(k) for k, v in classes.items() if v != "passed")
        if not reds and data.get("status") not in ("passed", None):
            reds = [f"<tree-wide {data.get('status')}>"]
        if not reds:
            continue
        owners = {}
        for tid, rec in twos:
            for dep in rec.get("dependsOn") or []:
                pair = index.get(str(dep))
                if pair and int(pair.get("stage") or 0) == 1:
                    stem = str(pair.get("path", "")).split("/")[-1].rsplit(".", 1)[0]
                    if stem:
                        owners[stem.lower()] = tid
        deferred, ownerless, mine = [], [], []
        # A red class whose failure is a MOCKABILITY gap on a FOREIGN closed type is a
        # victim: its owner cannot edit either the frozen test or the peer's modifier.
        # The class below (mock_impossible -> producer) charges whoever closed the type.
        mock_closed = {str(t) for t in data.get("mock_impossible") or []}
        mock_victims = set()
        for fl in (data.get("failures") or []) if mock_closed else []:
            mt = str((fl or {}).get("mock_type") or "")
            if mt not in mock_closed:
                continue
            base = str(fl.get("test", "")).rsplit(".", 1)[0].split("$")[0].split(".")[-1].lower()
            owner = owners.get(base)
            op = tasks.exported_product(index.get(owner)) if owner and index.get(owner) else ""
            if owner and op != mt:
                mock_victims.add(base)
        for key in reds:
            base = key.split("$")[0].split(".")[-1].lower()
            if base in mock_victims:
                continue
            owner = owners.get(base)
            if owner is None:
                ownerless.append(key)
            elif owner in error_ids:
                deferred.append(f"{key} (owner {owner} is quarantined)")
            else:
                mine.append((owner, key))
        # FILE blame over class blame when the evidence names a main file: a red test
        # class is often poisoned by a COLLABORATOR's source (2026-11-16: an evaluator
        # added a constructor guard to TelemetrySample.java; SampleValidatorTest - which
        # legitimately builds invalid samples for the VALIDATOR to judge - went red, and
        # the validator's owner T2-008 was charged for a file it must not touch).
        # error_locations is the engine's existing stack-agnostic file+line scanner.
        file_owner = {}
        for f in settings.COMPLETE_DIR.glob("T2-*.json"):
            rec = _safe_read(f)
            if not isinstance(rec, dict) or str(rec.get("project", "")) != slug:
                continue
            base = str(rec.get("path", "")).replace("\\", "/").split("/")[-1]
            if base:
                file_owner[base] = str(rec.get("id", ""))
        for name, _tail in test_gate.error_locations(data):
            blame = file_owner.get(name)
            if blame and blame not in error_ids:
                mine.append((blame, f"file:{name}"))
        # MOCKABILITY reds: the file that closed a mocked type is the producer's, never
        # the mocking unit's (its test is frozen and the modifier is a foreign file).
        for tname in data.get("mock_impossible") or []:
            for tid, rec in twos:
                if tasks.exported_product(rec) == str(tname) and tid not in error_ids:
                    mine.append((tid, f"mock-closed:{tname}"))
        acted = False
        for owner, _key in sorted(set(mine)):
            if task_queue.reopen_completed(owner):
                reopened.append(owner)
                acted = True
        # Ownerless integration reds belong to STAGE 4: assembly is the only unit whose
        # contract is the WHOLE tree, and its boot gate ran at ITS moment - a later
        # evaluator edit that breaks the boot had no owner left to charge (2026-11-16:
        # the scaffold smoke class sat red with no producing unit while the board idled).
        if ownerless:
            for tid, rec in sorted(index.items()):
                if (str(rec.get("project", "")) == slug
                        and int(rec.get("stage") or 0) == 4
                        and (slug, fp) not in _TERMINAL_T4_ATTRIBUTED
                        and task_queue.reopen_completed(tid)):
                    _TERMINAL_T4_ATTRIBUTED.add((slug, fp))
                    reopened.append(tid)
                    acted = True
                    break
        signature = (slug, fp)
        if signature not in _TERMINAL_SUITE_SEEN or acted:
            _TERMINAL_SUITE_SEEN.add(signature)
            lines = [f"[suite ] {slug}: delivered suite is RED - "
                     f"{len(reds)} class(es) failed after the last wave"]
            for owner, key in sorted(set(mine)):
                lines.append(f"[suite ] {slug}: reopened {owner} (owner of {key})")
            for note in sorted(set(deferred)):
                lines.append(f"[suite ] {slug}: {note} - the quarantine already owns it")
            for key in sorted(set(ownerless)):
                lines.append(f"[suite ] {slug}: {key} has NO producing unit - the "
                             "operator reads this, the board does not hide it")
            print("\n".join(lines))
    return sorted(set(reopened))


def _dangling_main_consumers(task):
    """Main-source files that still reference the product of a unit whose payload is
    being rolled back (seed-002 rerun F1: quarantine deleted DefaultIngestTelemetryUseCase.java
    and left TelemetryWiringConfiguration.java - a COMPLETED unit's file - importing a type
    that no longer exists; nothing re-adjudicates after the last verdict, so the DELIVERED
    tree stopped compiling while the board still reported 89/96 + boot green).

    Text-level and stack-neutral: word-boundary reference to the exported product name in
    any non-test source of the domain other than the unit's own file. The consumers are
    usually innocent and their owners did nothing wrong - the rollback is the defect -
    so they are NOT reopened (that would bill a healthy unit for its peer's quarantine);
    they are NAMED: in the log, and appended to the quarantine record the operator reads.
    """
    name = tasks.exported_product(task)
    if not name or not tasks.is_type_shape(name):
        return []
    pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    own = str(task.get("path", "")).split("/")[-1]
    hits = set()
    for f in test_gate.source_files(workspace.project_root_for(task.get("project", ""))):
        parts = {p.lower() for p in f.parts}
        if parts & {"test", "tests"} or f.name == own:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern.search(text):
            hits.add(str(f.relative_to(workspace.project_root_for(task.get("project", "")))))
    return sorted(hits)


def _surface_rollback_hole(task):
    """Act on a destructive revert: consumers OWNED by a completed unit go back to their
    owner (the module-wide gate will defer them at zero bill while the symbol's owner
    stays quarantined, and the queue stops lying about being empty); consumers NOBODY
    owns (assembly-era files) can only be NAMED: log + appended to the quarantine record.
    Returns the notice text ("" when the revert left no hole)."""
    dangling = _dangling_main_consumers(task)
    if not dangling:
        return ""
    owners = {}
    for rec_file in sorted(settings.COMPLETE_DIR.glob("T*-*.json")):
        if not rec_file.name.startswith(("T2-", "T3-", "T4-")):
            continue
        try:
            rec = json.loads(rec_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rec, dict) or rec.get("project") != task.get("project"):
            continue
        owners.setdefault(str(rec.get("path", "")).replace("\\", "/").split("/")[-1],
                          str(rec.get("id", "")))
    reopened, orphaned = [], []
    for rel in dangling:
        owner = owners.get(rel.split("/")[-1])
        if owner and owner != task["id"] and task_queue.reopen_completed(owner):
            reopened.append(f"{rel} -> {owner} reopened")
        else:
            orphaned.append(rel)
    tail = ("" if not orphaned else
            " - UNOWNED production files import a rolled-back artifact: the delivered "
            "tree does not compile; restore this unit with --retry or rewire the named "
            "files before delivery")
    return (" [DANGLING-CONSUMERS: " + "; ".join(reopened + orphaned)[:400] +
            f" still reference {tasks.exported_product(task)} after this rollback{tail}]")


def _note_on_quarantine(task_id, notice):
    """Append a post-revert fact to the record already sent to error/: the quarantine
    reason is the operator's first read - a rolled-back artifact that holes the MAIN tree
    must live there, not only in the pass log."""
    file = next(iter(settings.ERROR_DIR.glob(f"{task_id}-*.json")), None)
    if file is None:
        return
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
        payload["error"] = str(payload.get("error", "")) + notice
        file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        return


def _peers_outstanding(task):
    """True when stage-2 tasks of the same domain are still in the queue (unevaluated peers)."""
    project = task.get("project", "")
    return any(settings.QUEUE_DIR.glob(f"T2-*-{project}.json"))


# Structural-compile phrases naming a SUPERTYPE signature conflict (javac:
# "does not override or implement a method from a supertype"; tsc: "incorrectly
# implements"). Generic text, like every other rule in this module.
SUPERTYPE_CONFLICT_PHRASES = ("does not override", "from a supertype",
                              "incorrectly implements", "does not implement")


def _declared_supertypes_of_source(task):
    """Legacy fallback: the runner field carries these names; source grammar otherwise."""
    import re
    source = workspace.project_root_for(task["project"]) / str(task.get("path", ""))
    try:
        text = source.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return set()
    declared = set()
    for match in re.finditer(r"\b(?:implements|extends)\s+([\w.]+(?:\s*,\s*[\w.]+)*)", text):
        for part in match.group(1).split(","):
            name = part.strip().split("<")[0].split(".")[-1].strip()
            if name:
                declared.add(name)
    return declared


def _own_declared_supertypes(task, result):
    """Supertype names the adapter's own file claims: the runner's field first, source
    grammar only for verdicts recorded before it existed."""
    own = str(task.get("path", "")).split("/")[-1]
    names = {str(s) for p in (result.get("problem_kinds") or [])
             if isinstance(p, dict) and p.get("file") == own and p.get("kind") == "supertype"
             for s in (p.get("supertypes") or [])}
    return names or _declared_supertypes_of_source(task)


def _peer_supertype_materialized(task, result):
    """Is a claimed supertype already a FILE on the tree (woven by its producer, gate or
    no gate)? A materialized port is concrete: the adapter can conform to it NOW, and
    the module cannot compile until someone does - so deferring BOTH the adapter (port
    'unresolved') and the producer (blame always foreign) deadlocks every gate on the
    same failure. Ledger caps (same-signature break, fed marker, grant cap) bound the
    churn if the port shape still moves."""
    declared = _own_declared_supertypes(task, result)
    if not declared:
        return False
    stems = {f.stem for f in test_gate.source_files(workspace.project_root_for(task["project"]))}
    return bool(declared & stems)


def _peer_supertype_conflict(task, result):
    """True when a structural failure in MY file blames a supertype another QUEUED
    unit still owns. While the port's producing task has not passed its own gate, its
    method set can still move; no payload of this adapter converges on a moving
    contract (observed once: seven paid sessions on one identical conflict). The remedy
    is the peer landing, not another coder session: defer.

    Phrase classing and the blamed file's declared supertypes come from the runner's
    `problem_kinds` field (it owns every toolchain grammar); the message/regex paths
    remain only as fallback for verdicts recorded before the field existed.
    """
    own = str(task.get("path", "")).split("/")[-1]
    problems = [p for p in (result.get("problem_kinds") or [])
                if isinstance(p, dict) and p.get("file") == own and p.get("kind") == "supertype"]
    if problems:
        declared = {str(name) for p in problems for name in (p.get("supertypes") or [])}
        if not declared:
            declared = _declared_supertypes_of_source(task)
        return bool(declared & _pending_symbols_of(task.get("project", ""), task["id"]))
    messages = " ".join(message for name, message in test_gate.error_locations(result)
                        if name == own).lower()
    if not any(phrase in messages for phrase in SUPERTYPE_CONFLICT_PHRASES):
        return False
    declared = _declared_supertypes_of_source(task)
    return bool(declared & _pending_symbols_of(task.get("project", ""), task["id"]))


def _own_structural(result, own, locations):
    """A failure in MY file that is more than ripple from a foreign broken definition:
    the runner's problem kinds decide (anything but `missing-symbol` is structural);
    the cascade-shape table only answers for verdicts predating the field."""
    problems = [p for p in (result.get("problem_kinds") or []) if isinstance(p, dict)]
    if problems:
        return any(p.get("file") == own and p.get("kind") != "missing-symbol"
                   for p in problems)
    return any(name == own and not test_gate.is_cascade(message)
               for name, message in locations)


def _own_type_member_demand(result, task):
    """True when the runner reported a missing method/constructor/member ON THE TYPE THIS
    UNIT EXPORTS. `member_demands` is the run-test-tool's normalized view of every
    compiler's receiver/location grammar (the tool owns the syntax, this engine reads a
    field) - so attribution asks no language question. It outranks the pending-peer-symbol
    deferral: if every unit defers because SOME missing name belongs to a peer, nobody
    repairs the additive member and the domain livelocks in shared compile errors
    (a demanded method that every peer defers to, unit by unit, while its owner waits
    idle, is the observed failure)."""
    export = tasks.exported_product(task) or ""
    if not export:
        return False
    resolvable = None
    for demand in (result.get("member_demands") or []):
        if not isinstance(demand, dict) or not _owner_matches_export(demand.get("owner", ""),
                                                                     export):
            continue
        kind = demand.get("kind")
        if kind in ("method", "constructor", "property", "attribute", "variable"):
            return True
        if kind == "class":
            # `symbol: class Foo located in Bar` reads two ways: Foo is a NESTED type of
            # Bar (Bar's producer owns it) or a plain missing top-level type USED inside
            # Bar (whose producer or import wiring owns it). Only the nested reading is
            # Bar's fault: if Foo is anywhere else resolvable in the domain - a pending
            # export, a declared type - the gap is not on Bar's surface.
            names = _identifier_tokens(str(demand.get("member") or ""))
            if not names:
                continue
            if resolvable is None:
                resolvable = _resolvable_types(task.get("project", ""), task["id"])
            if not names & resolvable:
                return True
    return False


def _own_test_file(task):
    """The basename of this unit's frozen test: resolved through its T1 record in the
    task index (red-phase records carry verdicts, not paths)."""
    index = task_queue.load_index()
    for dep in task.get("dependsOn") or []:
        t1 = index.get(str(dep))
        if (isinstance(t1, dict) and str(dep).startswith("T1-")
                and isinstance(t1.get("path"), str)):
            return t1["path"].split("/")[-1]
    return ""


def _warn_unrevertable_poison(task):
    """A quarantined unit whose payload WAS spliced but has no weave baseline cannot be
    reverted - the tree keeps its code and every peer gate pays a full build to rediscover
    the same mystery error (seed-002 rerun 13:42: four WOVEN-UNVERIFIED dependents of a
    failed metrics unit stayed poisoned in silence). Log the state and the remedy loudly."""
    payload = settings.ROOT / "blackboard" / "coder-changes" / f"{task['id']}.json"
    weave_result = settings.BLACKBOARD / "weave-results" / f"{task['id']}.json"
    if payload.is_file() and weave_result.is_file():
        print(f"[warn ] {task['id']}: payload was woven but NO baseline exists to revert to - "
              f"{task.get('path', '?')} stays in the tree; peers pay a full build per gate "
              "until --retry re-weaves this unit green or the operator restores the file")


def _payload_proven_harmless(task):
    """True when a quarantine-time payload is PROVEN not to poison the shared tree.

    The proof is the just-adjudicated verdict itself (fresh memo on current bytes):
    status=assertion_failure means the whole module COMPILED and the suite RAN TO
    COMPLETION with this payload spliced in, and the unit's own test class was the
    one adjudicated red. Reverting such a payload deletes a type other units' files
    import - it holes the shared tree and freezes every gate (the live T2-003
    domain freeze: same-signature quarantine -> revert -> `missing=SampleValidator`
    -> all 10 peers deferred, forever). A compile_error/not_run/timeout verdict (or
    no fresh memo at all) keeps the classic revert: poison proven or unproven.
    """
    payload = settings.ROOT / "blackboard" / "coder-changes" / f"{task['id']}.json"
    weave_result = settings.ROOT / "blackboard" / "weave-results" / f"{task['id']}.json"
    if not (payload.is_file() and weave_result.is_file()):
        return False
    memo = test_gate.last_adjudicated(task)
    if not isinstance(memo, dict):
        return False
    result = memo.get("result")
    return isinstance(result, dict) and result.get("status") == "assertion_failure"


def _pending_bean_demand(result, task):
    """True when a context-boot failure demands a bean a PENDING PEER must bring.
    `bean_demands` is the runner's normalized 'the application context needs a bean
    of type X' fact (every toolchain keeps its phrasing inside the tool). A boot-wide
    frozen test can only pass once the WHOLE bean graph exists: while a demanded bean
    is a queued/quarantined peer's exported product, no payload here can converge -
    defer (zero cost: the payload stays woven, the tree keeps compiling, and an
    auto-grant recharges this unit informed when the world moves). Charged instead
    when the demanded bean IS this unit's own exported type (making that type a bean
    is its contract's work), when the demanded CLASS is already materialized on the
    tree (what is missing is REGISTRATION - a @Bean/@Component in someone's own file,
    the plan's wiring unit; deferring every demanding unit deadlocks the domain on
    one boot failure - observed live: 19 units blocked on SampleValidator while its
    woven-but-locked class sat in the tree; the ledger caps bound bystander churn),
    or when NO pending peer owns it at all (surfacing, not deadlock).
    """
    beans = result.get("bean_demands") if isinstance(result, dict) else None
    if not beans:
        return False
    simple = {str(bean).rsplit(".", 1)[-1] for bean in beans}
    if tasks.exported_product(task) in simple:
        return False
    materialized = {f.stem for f in
                    test_gate.source_files(workspace.project_root_for(task.get("project", "")))}
    if simple & materialized:
        return False
    owners = _queued_main_file_owners(task.get("project", ""))
    pending = set()
    for name, owner_id in owners.items():
        if owner_id and owner_id != task["id"]:
            pending.add(name.rsplit(".", 1)[0] if "." in name else name)
    return bool(simple & pending)


def _mock_impossible_owner(result, task):
    """The id of a FOREIGN unit whose exported type a frozen test can no longer stub
    (`mock_impossible` = the runner's normalized Mockito sealed/final gap). The mocking
    unit owns no editable surface for that fact - its test is frozen and the closure
    lives in the collaborator's file - so the producer that closed the type is charged
    (2026-11-16: an evaluator sealed an event interface and the CONSUMER's 7 stub-based
    tests died; T2-023 burned its whole life budget on a file it must not touch).
    None when the closed type IS this unit's own product: keeping a collaborator it
    itself ships stubbable is part of ITS contract, and it gets charged normally."""
    names = result.get("mock_impossible") if isinstance(result, dict) else None
    if not names:
        return None
    own = tasks.exported_product(task)
    for tid, rec in sorted(task_queue.load_index(include_error=True).items()):
        if (str(rec.get("project", "")) == str(task.get("project", ""))
                and int(rec.get("stage") or 0) == settings.TDD_STAGE
                and tasks.exported_product(rec) in set(names)
                and tasks.exported_product(rec) != own):
            return tid
    return None


def _owner_matches_export(owner, export):
    """Does a javac demand-owner spell THIS unit's exported type?

    `tasks.exported_product` is the SIMPLE name; the toolchains print owners as simple,
    package-qualified (`com.x.Color`), or the NESTED `OUTER.Inner` / `com.x.OUTER.Inner`
    shape - the outer segment owns the surface. The old exact `owner != export` comparison
    matched none of the qualified spellings, so demands on `TelemetryEvent.Type` charged
    nobody and every unit of the domain deferred on it (observed live 2026-11-18 15:20).
    """
    if not owner or not export:
        return False
    owner, export = str(owner).strip(), str(export).strip()
    if owner == export:
        return True
    o_parts = owner.split(".")
    e_simple = export.split(".")[-1]
    if o_parts[-1] == e_simple:
        return True
    return len(o_parts) >= 2 and o_parts[-2] == e_simple and o_parts[-1][:1].isupper()


def _unambiguous_member_demand(result, task):
    """A javac-proven statement about THIS type's own surface, independent of any caller.

    `symbol: variable LATE located in class ValidationStatus` cannot be repaired at the call
    site - the constant either exists on the enum or it does not - so it does not need the
    peer-call-site adjudication the method demands wait for. Method/constructor demands stay
    guarded: their spelling is only proven by the callers' own-file attempts.
    """
    export = tasks.exported_product(task) or ""
    for demand in (result.get("member_demands") or []):
        if isinstance(demand, dict) and demand.get("kind") in ("variable", "property", "attribute") \
                and _owner_matches_export(demand.get("owner", ""), export):
            return True
    return False


def _own_hallucinated_import(result, task, locations):
    """True when a symbol miss IN MY FILE names a class inside an EXISTING external package.

    Such an import references a type no task of this domain can ever produce and no peer edit
    can conjure: javac proves it against the classpath, so it is structural to MY payload, not
    a cascade. Without this edge the ANY-cascade rule defers the owner of the bad import as
    long as some other blamed file belongs to a peer (2026-11-18 live:
    import org.springframework.r2dbc.core.Parameters sat in line 13 of the repository's OWN
    file while IngestPacketUseCase.java belonged to T2-017 - T2-019 never got charged,
    consumed stayed 0, and the domain re-fatals on stuck passes forever).
    """
    own = str(task.get("path", "")).split("/")[-1]
    if not any(name == own for name, _ in locations):
        return False
    located = _excerpt_package_locations(result)
    if not located:
        return False
    ext = test_gate.external_type_index(workspace.project_root_for(task.get("project", "")))
    ext_packages = {fqn.rsplit(".", 1)[0] for names in ext.values() for fqn in names}
    return any(pkg in ext_packages for pkgs in located.values() for pkg in pkgs)


def _blocked_by_peers(result, task):
    """True when a red stage-2 gate is NOT this unit's own fault.

    Surefire compiles the whole source set: a missing peer (or a test that will
    only compile once other tasks land) fails every task of the domain. The only
    compile failure worth retrying is one STRUCTURALLY located in this unit's own file
    (every toolchain prints "file:line: message"); a cascade of foreign symbol misses
    is a peer problem the coder cannot fix, so defer instead of burning the attempts.
    """
    if not isinstance(result, dict):
        return False
    if _pending_bean_demand(result, task):
        return True              # runtime wiring gap: a pending peer's bean is demanded
    if _mock_impossible_owner(result, task):
        return True              # a peer CLOSED a type this unit's frozen test stubs
    if result.get("status") not in ("compile_error", "error"):
        return False
    owners = _queued_main_file_owners(task.get("project", ""))
    own = str(task.get("path", "")).split("/")[-1]
    locations = test_gate.error_locations(result)
    main_names = {name for name, _ in locations if name in owners}
    if own in main_names:
        # OWN FILE FIRST: a structural error in this unit's own file is always fixable
        # by its payload, no matter which peer symbols are missing - deferring on the
        # pending-peers rule while the own file is structurally broken forms a
        # two-node deferral CYCLE (wiring unit waits for the class, class owner waits
        # for the wiring file - observed live 14:58, both sides provably idle).
        # A "cannot find symbol" in the own file is still a cascade from a foreign
        # broken definition, which no payload of this unit can repair - defer.
        own_structural = _own_structural(result, own, locations)
        if own_structural and _peer_supertype_conflict(task, result) \
                and not _peer_supertype_materialized(task, result):
            return True    # the supertype is not on the tree yet: nothing to adapt to, defer
                           # (materialized port: fall through to charge - deferral would
                           # deadlock both gates on the same module-wide compile failure)
        if not own_structural and any(owners.get(name) != task["id"] for name in main_names) \
                and not _own_hallucinated_import(result, task, locations):
            return True
        return False                       # the own file is structurally broken: real retry
    if _own_type_member_demand(result, task):
        # A demand on MY exported type usually means MY payload must add the member.
        # But when EVERY blamed main file belongs to another still-live queued unit
        # and my own file is not blamed at all, the "missing member" is proven only
        # through THEIR (unadjudicated, possibly malformed) call sites - charging the
        # demand owner burned 3 attempts on T2-017 for the wiring unit's syntax while
        # the wiring file itself stayed the true defect (seed-002 rerun 14:03).
        # Let the peers' own-file attempts resolve their call sites first; if the gap
        # is genuinely mine, my frozen test will charge me afterwards.
        if main_names and all(owners.get(name) != task["id"] for name in main_names) \
                and not _unambiguous_member_demand(result, task):
            return True
        return False             # additive member demanded on MY exported type: nothing defers it
    if result.get("status") == "compile_error":
        missing_tokens = _identifier_tokens(" ".join(str(item) for item in (result.get("missing_symbols") or [])))
        if missing_tokens & _pending_symbols_of(task["project"], task["id"]):
            return True          # a queued peer will resolve this symbol; do not burn attempts
    if main_names and all(owners.get(name) != task["id"] for name in main_names):
        return True              # every blamed production file belongs to other queued units
    if locations and not main_names:
        # 1) A compile error in a frozen test is FIRST the contract duty of that test's
        #    OWN implementer (the stage-2 unit whose T1 record points at this test file):
        #    its payload must make the call its own contract shows compile - add the
        #    overload/factory the log names. "incompatible types" pair defects land here
        #    for the service unit, not for the units whose types merely APPEAR in the
        #    message (an earlier drain charged the argument type's owner for a call its
        #    file does not declare).
        blamed_files = {name for name, _ in locations}
        my_test = _own_test_file(task)
        if my_test and my_test in blamed_files:
            return False                   # my contract's own test file fails: real retry
        # 2) Otherwise only DEMANDS attribute: `member_demands` is the runner's normalized
        #    "type X lacks member m" fact (the tool owns every compiler's phrasing; the
        #    engine reads the field). The task exporting the located type retries.
        #    Conversion/arity defects without a demand name types only as incidental
        #    arguments - blaming those units charges bystanders.
        demands = [d for d in (result.get("member_demands") or []) if isinstance(d, dict)]
        if not demands:
            return True
        located = {str(d.get("owner") or "") for d in demands if str(d.get("owner") or "").strip()}
        named = {owner_id for name, owner_id in owners.items()
                 if any(_owner_matches_export(owner, name.removesuffix(".java"))
                        or _owner_matches_export(owner, name) for owner in located)}
        if task["id"] in named:
            return False                   # the gap sits in MY exported type: real retry
        return True                        # another queued unit owns the named type: defer
    if result.get("status") != "compile_error":
        return False
    export = tasks.exported_product(task) or ""
    items = result.get("missing_symbols") or []
    if export and export in _identifier_tokens(" ".join(str(item) for item in items)):
        return False
    # Structured evidence only: symbols still expected from the tree, or an open demand
    # somewhere, means the compile failure is not this unit's own defect yet.
    return bool(items) or bool(result.get("member_demands"))


def _identifier_tokens(text):
    import re
    return set(re.findall(r"[A-Za-z_$][\w$]*", text))


_WAIT_LOGGED = {}


def _log_wait(task_id, detail):
    """Print a defer reason only when it changes (or every 5 minutes at most).

    Watch mode re-polls every few seconds: an unchanged 'waiting for peers' verdict
    repeated across passes produced thousands of identical log lines per hour (W3)
    while doing zero work. Same reason + same task in a later pass stays silent.
    """
    import time as _time
    reason = (detail or "")[:200]
    previous = _WAIT_LOGGED.get(task_id)
    if previous and previous[0] == reason and _time.time() - previous[1] < 300:
        return
    _WAIT_LOGGED[task_id] = (reason, _time.time())
    print(f"[wait  ] {task_id} waiting for peers: {reason}")


def wait_snapshot():
    """Last deferral reason per task: what the operator needs to see when a drain
    stops making progress (consumed by the pipeline's stuck-pass breaker)."""
    return {task_id: reason for task_id, (reason, _ts) in _WAIT_LOGGED.items()}


def autogrant_progressing():
    """Auto-restore quarantined units that the drain can now productively re-attempt.

    Two qualifying shapes, and nothing else:
    - GRENTEES: charged stage-2 units whose last recorded failure was never shown to
      a coder session (ledger signature != fed): one informed attempt moves them.
      Units repeating an already-shown failure stay quarantined - their replay closes
      at zero sessions by design (§13.1), so restoring them would burn passes, not
      defects. Grants per contract are capped (MAX_INFORMED_GRANTS); green clears.
    - COLLATERALS: cascade quarantines ("dependsOn X not resolvable", never charged).
      Once every blocker is complete, queued, or itself being granted in this batch,
      the chain unwinds to a fixed point in ONE call; the skip-agent path re-verifies
      them without billing.

    Returns the restored ids.
    """
    try:
        kept, complete_ids = task_queue.load_valid_tasks()
    except task_queue.ScaffoldUnresolved:
        return []
    available = set(complete_ids) | {task["id"] for _, task in kept}

    grantees, cascades = [], []
    for file in sorted(settings.ERROR_DIR.glob("*.json")):
        try:
            task = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            continue
        # Cascade-shaped quarantines are governed by their DEPENDENCIES, never by the
        # budget rule: a unit that has never attempted (consumed 0) is budgeted but
        # immobile - restoring it while its blocker still lies in error/ just ping-pongs
        # it through the same fatal cycle (observed live: T2-041 restored twice with zero
        # possible progress).
        if str(task.get("error") or "").startswith("dependsOn"):
            cascades.append((task_id, task))
            continue
        ledger = attempt_ledger.read(task_id)
        if isinstance(ledger, dict) and ledger.get("signature"):
            # Unspent regular budget always qualifies: the same-signature break ended
            # the loop early (often because attribution fired at a peer's not-yet-landed
            # file), and leaving a charged-but-budgeted unit quarantined dead-locks the
            # domain behind a tooling artifact. Beyond budget: a unit qualifies while
            # its grants are under the cap AND either its last failure has never been
            # shown to a coder session, or the WORLD MOVED since its verdict (its gate
            # memo no longer matches the tree - a peer fix may have unblocked it, and
            # the free replay will tell). Storm guard intact: a shown failure on an
            # unchanged world stays quarantined (its replay closes at zero sessions).
            has_budget = int(ledger.get("consumed") or 0) < settings.MAX_TDD_RETRIES
            grants_used = int(ledger.get("grants") or 0)
            if has_budget:
                grantees.append(task_id)
            elif grants_used < settings.MAX_INFORMED_GRANTS:
                unshown = ledger.get("fed") != ledger.get("signature")
                moved = test_gate.verdict_tree_stale(task)
                if unshown or moved:
                    grantees.append(task_id)
            continue
        continue  # never-charged, never-shown, non-cascade quarantine: operator's problem

    restored = list(grantees)
    unlocking = set(grantees)
    pending = cascades
    while True:  # fixed point: a restored blocker frees its dependents in this batch
        still_waiting, progressed_now = [], False
        for task_id, task in pending:
            deps = task.get("dependsOn") or []
            if deps and all(str(dep) in available or str(dep) in unlocking for dep in deps):
                restored.append(task_id)
                unlocking.add(task_id)
                progressed_now = True
            else:
                still_waiting.append((task_id, task))
        pending = still_waiting
        if not progressed_now:
            break
    return task_queue.retry_error_tasks(restored) if restored else []


def _source_is_proven_poison(source):
    """Did SOURCE's quarantine evidence prove CODE BROKEN IN THE TREE?

    A WOVEN-CLEAN failure (the tree compiles, the suite completes, only the source unit's
    own tests are red) or a cascade reason (the source was never adjudicated) says NOTHING
    about whether dependents compile. Reverting their woven payloads anyway holes the tree
    and converts one stall into a rollback cascade - each undone class breaks another
    unit's WOVEN-CLEAN probe, which reverts that unit in turn (2026-11-18 live:
    SliceTestSupport was reverted because T2-035 was re-quarantined; the support class
    imported nothing broken, and the whole test tree stopped compiling for every sibling).
    Unreadable evidence stays conservative-revert: an unknown verdict may not poison the
    shared tree.
    """
    for f in settings.ERROR_DIR.glob(f"{source}-*"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True
        err = str(rec.get("error") or "")
        return "WOVEN-CLEAN" not in err and not err.startswith("dependsOn")
    return True


def quarantine_dependents(failed_id, tasks, files, dependents, remaining):
    """Send every transitive dependent of a failed task to the error queue."""
    pending = [failed_id]
    while pending:
        source = pending.pop()
        for dependent_id in dependents.get(source, []):
            if dependent_id not in remaining:
                continue
            dependent_task = tasks[dependent_id]
            if dependent_task["stage"] == 0:
                continue
            file = files[dependent_id]
            reason = f"dependsOn {source} not resolvable in queue or complete"
            has_payload = (settings.ROOT / "blackboard" / "coder-changes" / f"{dependent_id}.json").is_file()
            if dependent_task["stage"] == settings.TDD_STAGE and has_payload:
                reason += (" [WOVEN-UNVERIFIED: this unit's payload is already spliced into the "
                           "source tree but its gate never ran; if OTHER units hang or fail to "
                           "compile, suspect this file]")
            task_queue.send_to_error(file, reason, dependent_task)
            print(f"[error] {file.name}: {reason}")
            if (dependent_task["stage"] == settings.TDD_STAGE and has_payload
                    and _source_is_proven_poison(source)):
                if dispatchers.revert_weave(dependent_task, discard_payload=False):
                    hole = _surface_rollback_hole(dependent_task)
                    if hole:
                        print(f"[hole  ] {dependent_task['id']}:{hole}")
                        _note_on_quarantine(dependent_task["id"], hole)
                else:
                    _warn_unrevertable_poison(dependent_task)
            elif (dependent_task["stage"] == settings.TDD_STAGE and has_payload):
                print(f"[keep ] {dependent_task['id']}: woven payload kept through the cascade - "
                      f"its blocker {source} is not proven poison for the tree (behavioral or "
                      "never-adjudicated), and reverting a victim is how one stall becomes a "
                      "rollback chain")
            remaining.discard(dependent_id)
            pending.append(dependent_id)


def _ensure_task_parent(task):
    """Create the parent folder of a stage-1 test path before any agent runs.

    Copilot's create tool refuses to write when the parent folder is missing, and every
    greenfield package starts absent: without this the tester burns 2-3 extra calls
    (mkdir + re-write, ~50K tokens re-sent for the rest of its session).
    """
    if task.get("stage") != settings.TESTER_STAGE:
        return
    try:
        (workspace.project_root_for(task["project"]) / task["path"]).parent.mkdir(
            parents=True, exist_ok=True)
    except (OSError, KeyError, TypeError):
        pass


def _build_manifest_duty(task):
    """True when a stage-0 task OWNS a build file but is not the scaffold itself.

    The scaffold CREATES the build file (export marker `project_scaffold`: file on disk = done);
    a build-manifest duty MODIFIES the one the scaffold made - its artifact is always already on
    disk, so existence proves nothing (2026-11-18 live: the skip-agent resume guard 'completed'
    the queued manifest duty in 3 seconds without a session, and the next close-out fataled on
    the very gap the duty was scheduled to fill).
    """
    return (task.get("stage") == 0 and task.get("kind") == "bootstrap"
            and Path(str(task.get("path", ""))).name in settings.BUILD_FILE_NAMES
            and str(task.get("export", "")).strip() != task_queue.SCAFFOLD_EXPORT)


def _manifest_duty_pending(project):
    """True when the QUEUE holds an unfinished stage-0 build-manifest duty for the domain.

    Such a duty rewrites the classpath that `scan_red_phase_gaps` reads, and heap order runs it
    before any stage-1 work; fataling at the resume gate on a gap that the queued duty exists to
    fill deadlocks the board forever (the remedy is only valid AFTER stage 0 ran).
    """
    for file in sorted(settings.QUEUE_DIR.glob("T0-*.json")):
        try:
            task = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(task, dict) and task.get("project") == project and _build_manifest_duty(task):
            return True
    return False


def _tester_close_out(task):
    """Deterministic stage-1 close-out: validate red, guard classpath holes, dispatch the AST.

    Shared by the after-session path and the resume-skip, so a tester killed mid-session
    (valid red record on disk, no [done], no contract) is finished WITHOUT re-billing a
    full agent session.
    """
    problem = dispatchers.red_phase_problem(task)
    if problem and dispatchers.derive_red_phase(task):
        # Test on disk + unusable/missing red record is DERIVABLE: run it, pipe the
        # official writer, revalidate - before charging a session for a build result.
        problem = dispatchers.red_phase_problem(task)
    if problem:
        return False, problem
    gap = dispatchers.red_phase_dependency_gap(task)
    if gap:
        # A foreign package is most often a tester-invented import path for a type with a
        # unique owner elsewhere: the deterministic repair can reroute it. Give it the
        # chance BEFORE aborting - then re-derive the red record from the repaired file.
        project_root = workspace.project_root_for(task.get("project", ""))
        if test_gate.repair_test_imports(project_root):
            dispatchers.rerecord_red_phase(task)
            gap = dispatchers.red_phase_dependency_gap(task)
    if gap:
        raise FatalPipeline(
            f"{task['id']} tests import {len(gap)} package(s) no task produces and "
            f"the scaffold classpath lacks: {', '.join(gap)}. Stage 2 cannot edit the "
            "build file, so every gate of this domain would fail forever. Remedy: the plan "
            "omitted the build-manifest duty that owns these coordinates - emit a stage-0 "
            "bootstrap task (layer root, feature null, dependsOn empty, path = the stack's "
            "build file, export = its base name, intent = the generator-native ids plus any "
            "catalog-absent artifact required test-scoped) through the orchestrator's --emit "
            "and relaunch; the drain runs stage 0 before the remaining stage-1 work.")
    dispatchers.run_ast_dispatcher(task)
    return True, ""


def drain_queue(args, invoke_for_task):
    """Drain the queue once using an in-memory dependency graph and ready heap.

    The queue and completion folders are scanned once per pass. Tasks that become
    ready after a completion are pushed onto a heap ordered by (stage, project, path),
    keeping work grouped by domain within each stage.

    ``invoke_for_task(task, feedback)`` runs the backend-specific agent call.
    With ``args.parallel > 1`` independent domains run concurrently; at most one
    task per project is in flight so concurrent builds never share a target/ dir.
    """
    kept, complete_ids = [], set()
    try:
        kept, complete_ids = task_queue.load_valid_tasks()
    except task_queue.ScaffoldUnresolved as scaffold:
        raise FatalPipeline(str(scaffold))
    # queue membership changed since the last pass: rebuild the payload scans once
    dispatchers.invalidate_payload_cache()
    if not kept:
        return 0, []

    for _, task in kept:
        _ensure_task_parent(task)

    gaps = dispatchers.scan_red_phase_gaps()
    if gaps:
        # Stale foreign-gap records (a session killed before close-out): try the same
        # deterministic import repair per affected project, then RE-RECORD the red verdicts
        # UNCONDITIONALLY - the disk file is the truth, and the repair returning "nothing
        # changed" does NOT mean the record is current: 2026-11-18 live, a close-out-time
        # reroute left the file clean while the recorded verdict still named the old package,
        # the gated re-record was skipped for exactly that reason, and every relaunch died
        # on a gap no file contains. Re-record is zero-session: it reruns the red build.
        # A pending stage-0 build-manifest duty DEFERS the fatal: heap order runs stage 0
        # first, the classpath then re-checks per task at close-out.
        index = task_queue.load_index(include_error=True)
        for project in list(gaps):
            test_gate.repair_test_imports(workspace.project_root_for(project))
            for record_path in settings.RED_PHASE_DIR.glob("*.json"):
                try:
                    tid = str(json.loads(record_path.read_text(encoding="utf-8")).get("task_id")
                              or record_path.stem)
                except (OSError, json.JSONDecodeError):
                    continue
                stale = index.get(tid) or {}
                if stale.get("project") == project:
                    dispatchers.rerecord_red_phase(stale)
        gaps = dispatchers.scan_red_phase_gaps()
        deferred = [project for project in gaps if _manifest_duty_pending(project)]
        for project in deferred:
            print(f"[defer ] red-phase classpath gap deferred for {project}: a queued stage-0 "
                  "build-manifest duty owns the build file and runs BEFORE any stage-1 work; "
                  "the same check re-runs at each task's close-out")
        gaps = {project: pkgs for project, pkgs in gaps.items() if project not in deferred}
    if gaps:
        detail = "; ".join(f"{project}: {', '.join(pkgs)}"
                           for project, pkgs in sorted(gaps.items()))
        raise FatalPipeline(
            f"recorded red tests import packages no task produces and the scaffold "
            f"classpath lacks: {detail}. Fix the build file (stage 2 may not edit it), "
            "then relaunch; the check re-runs on every drain.")

    by_id = {task["id"]: task for _, task in kept}
    files = {task["id"]: file for file, task in kept}
    by_stage = {}
    for _, task in kept:
        by_stage.setdefault(task["stage"], []).append(task["id"])

    pending_deps = {}
    dependents = {}
    for task_id, task in by_id.items():
        unmet = [dep for dep in task["dependsOn"] if dep not in complete_ids]
        pending_deps[task_id] = len(unmet)
        for dep in unmet:
            dependents.setdefault(dep, []).append(task_id)

    processed = {"count": 0}
    attempted = set()
    remaining = set(by_id)
    deferred_ids = set()

    def eligible(task_id):
        """Attemptable: every dependency is complete, or a same-stage peer already attempted.

        A stage-2 unit defers when the whole-module compile fails on a sibling's symbols. Blocking
        that sibling afterwards would freeze the domain: nothing gets woven, so the failure repeats.
        Attempt eligibility therefore travels inside the stage, while completion (what the evaluator
        stage needs) still requires the dependency to be genuinely done.
        """
        task = by_id[task_id]
        for dep in task["dependsOn"]:
            if dep in complete_ids:
                continue
            if dep in deferred_ids and by_id.get(dep, {}).get("stage") == task["stage"]:
                continue
            return False
        return True

    def closures_for(task):
        def invoke(feedback):
            _ensure_task_parent(task)
            payload = settings.ROOT / "blackboard" / "coder-changes" / f"{task['id']}.json"
            if (task["stage"] == settings.TDD_STAGE and feedback is None and payload.is_file()):
                print(f"[skip-agent] {task['id']} coder payload already recorded; going straight to verify")
                return True, ""
            if (task["stage"] == 0 and feedback is None
                    and (workspace.project_root_for(task["project"]) / task["path"]).is_file()
                    and not _build_manifest_duty(task)):
                print(f"[skip-agent] {task['id']} bootstrap artifact already on disk "
                      f"({task['path']}); no agent session needed")
                return True, ""
            if (task["stage"] == settings.TESTER_STAGE and feedback is None
                    and (workspace.project_root_for(task["project"]) / task["path"]).is_file()):
                # Resume guard: a killed tester can leave a valid test + red record without
                # [done]. Close it out deterministically (re-dispatching the contract) instead
                # of re-billing the whole session (~130K). Invalid record -> fall through:
                # the tester runs again and overwrites it, exactly as before.
                ok_red, reason_red = _tester_close_out(task)
                if ok_red:
                    print(f"[skip-agent] {task['id']} test and valid red record on disk; "
                          "contract dispatched without a new session")
                    return True, ""
            if (task["stage"] == settings.TESTER_STAGE and feedback is None
                    and not (workspace.project_root_for(task["project"]) / task["path"]).is_file()):
                batch = getattr(invoke_for_task, "batch", None)
                siblings = _testless_peers(task) if batch else []
                if len(siblings) >= BATCH_MIN_PEERS:
                    picked = siblings[:BATCH_MAX]
                    print(f"[batch ] {task['id']} batching tester tasks for {len(picked)} tasks of {task['project']}")
                    try:
                        ok_batch, reason_batch = batch(picked)
                    except Exception as exc:  # noqa: BLE001
                        ok_batch, reason_batch = False, str(exc)
                    my_test = workspace.project_root_for(task["project"]) / task["path"]
                    if my_test.is_file():
                        ok_close, reason_close = _tester_close_out(task)
                        if ok_close:
                            print(f"[batch ] {task['id']} test written and red validated by "
                                  "the batch session; contract dispatched")
                            return True, ""
                        # A thin batch red (passed, unrun, malformed) must NOT quarantine the
                        # unit: fall through to a dedicated session that re-derives it properly.
                        print(f"[batch ] {task['id']} batch test red invalid ({reason_close[:90]}); "
                              "falling back to per-task")
                    else:
                        print(f"[batch ] {task['id']} batch wrote no test"
                              f"{'' if ok_batch else ' (' + reason_batch[:120] + ')'}; falling back to per-task")
            if task["stage"] == settings.TDD_STAGE:
                # A coder session without the unit's AST contract is a guessing session:
                # the payloads get weaved happily and die at the green wave, one coder
                # retry session (~150K tokens) per unit. Refuse the session instead.
                problem = dispatchers.ast_context_problem(task)
                if problem:
                    return False, f"ast-context gate: {problem}"
            if task["stage"] == settings.TDD_STAGE and feedback is None and not payload.is_file():
                batch = getattr(invoke_for_task, "batch", None)
                siblings = _payloadless_peers(task) if batch else []
                if len(siblings) >= BATCH_MIN_PEERS:
                    picked = siblings[:BATCH_MAX]
                    print(f"[batch ] {task['id']} batching coder payloads for {len(picked)} tasks of {task['project']}")
                    try:
                        ok_batch, reason_batch = batch(picked)
                    except Exception as exc:  # noqa: BLE001
                        ok_batch, reason_batch = False, str(exc)
                    if payload.is_file():
                        print(f"[batch ] {task['id']} payload written by the batch session; "
                              f"skipping the duplicate single-task session")
                        return True, ""
                    print(f"[batch ] {task['id']} batch wrote no payload"
                          f"{'' if ok_batch else ' (' + reason_batch[:120] + ')'}; falling back to per-task")
            if task["stage"] == settings.EVALUATOR_STAGE:
                # Session-shape storm (15:30): thirteen evaluators were BILLED to
                # re-verify a module that could not compile because a peer T2's class
                # was missing while its owner re-attempted. Defer before paying the
                # session: the same free evidence check the verify gate uses.
                ok_b, reason_b = verification.verify_project(
                    workspace.project_root_for(task["project"]), args.verify, args.verify_timeout)
                if not ok_b:
                    foreign = _t3_foreign_symbols(task, reason_b)
                    if foreign:
                        raise DeferredTask(
                            f"module build misses {', '.join(sorted(foreign)[:3])}: owned by "
                            "live sibling units - evaluator session not billed")
            pre_edit_snapshot = (refactor_audit.snapshot_sources(task)
                                 if task["stage"] == settings.EVALUATOR_STAGE else None)
            started = time.time()
            ok, reason = invoke_for_task(task, feedback)
            problem = _missing_artifact_problem(task, ok)
            if not problem and ok and _build_manifest_duty(task):
                # A MUTATION duty is not proved by existence: the build file has been on disk
                # since the scaffold made it, so the existence guard read the container's honest
                # "no pom was moved" halt as [done] (2026-11-18 live). The duty is delivered only
                # when the session moved the file it owns (mtime is content-time, mv-safe).
                moved = workspace.project_root_for(task["project"]) / str(task.get("path", ""))
                if moved.is_file() and moved.stat().st_mtime < started:
                    problem = (f"build-manifest duty ended with {task['path']} untouched - its "
                               "contract is to MODIFY the build file the scaffold already "
                               "created, and an unchanged classpath repeats the same gap on "
                               "every relaunch")
            if problem:
                return False, problem
            if ok and task["stage"] == settings.TESTER_STAGE:
                return _tester_close_out(task)
            if ok and task["stage"] == settings.EVALUATOR_STAGE:
                problem = dispatchers.evaluate_result_problem(task)
                if problem:
                    if _peers_outstanding(task):
                        raise DeferredTask(f"evaluate artifact pending ({problem}) while peers remain queued")
                    return False, problem
                refactor_audit.attach_engine_diff(task, pre_edit_snapshot)
            return ok, reason

        def verify():
            project_root = workspace.project_root_for(task["project"])
            if task["stage"] == settings.TDD_STAGE:
                problem = dispatchers.run_code_weaver_dispatcher(task)
                if problem:
                    return False, problem
                waiting = _sibling_payloads_pending(task)
                if waiting:
                    raise DeferredTask(f"{len(waiting)} sibling payload(s) still pending "
                                       f"({', '.join(waiting[:3])}); gate deferred until the "
                                       "domain is fully woven")
                problem, result = test_gate.green_test_result(task)
                if result is not None and result.get("status") == "not_run":
                    raise FatalPipeline(
                        f"{task['id']} test gate could not EXECUTE ({str(result.get('reason'))[:160]}). "
                        "An environment/tooling fault is nobody's unit defect: the drain aborts "
                        "instead of charging coder attempts.")
                if problem:
                    holes = _unresolvable_missing(result, task)
                    if holes:
                        raise FatalPipeline(
                            f"{task['id']} cannot compile against {len(holes)} symbol(s) no "
                            f"queued task exports and no source declares: {', '.join(holes[:8])}. "
                            "This is a scheduling hole, not a code defect; deferring would "
                            "livelock the domain. Close it with: "
                            "python3 orchestrators/closure.py --project-root <root> --emit")
                    if _reopen_contract_regression(result, task):
                        raise DeferredTask(str(problem) +
                                           " [contract-regression owner reopened to queue]")
                    mock_owner = _mock_impossible_owner(result, task)
                    if mock_owner and task_queue.reopen_completed(mock_owner):
                        raise DeferredTask(
                            str(problem) +
                            f" [mockability gap: {mock_owner} closed a type this unit's "
                            "frozen test stubs - its producer owns the fix, not this unit]")
                    if _blocked_by_peers(result, task):
                        raise DeferredTask(problem)
                    return False, problem
                return True, ""      # the green gate supersedes the build gate
            if task["stage"] == settings.EVALUATOR_STAGE:
                ok_build, reason_build = verification.verify_project(
                    project_root, args.verify, args.verify_timeout)
                if not ok_build:
                    foreign = _t3_foreign_symbols(task, reason_build)
                    if foreign:
                        raise DeferredTask(
                            f"module build misses {', '.join(sorted(foreign)[:3])}: owned by "
                            "live sibling units - evaluator deferred, not charged")
                return ok_build, reason_build
            if task["stage"] == settings.ASSEMBLY_STAGE:
                # The gate IS the verification: the container boots or it does not.
                # No agent artifact is trusted - the engine runs the smoke test itself.
                return assembly.gate(task)
            return verification.run_verification(
                project_root, args.verify, args.verify_scope, task, args.verify_timeout)

        return invoke, verify

    def attempt(task):
        invoke, verify = closures_for(task)
        try:
            ok, reason = execute_with_tdd(task, invoke, verify)
        except DeferredTask as defer:
            return "defer", str(defer)
        return ("done", "") if ok else ("fail", reason)

    def finalize(task_id, outcome, detail, stage, ready, limit_hit):
        file = files[task_id]
        task = by_id[task_id]
        if outcome == "done":
            with telemetry.span("blackboard.complete", {"file": file.name,
                                                        **telemetry.task_attributes(task)}):
                file.replace(settings.COMPLETE_DIR / file.name)
            print(f"[done] {task['id']}")
            complete_ids.add(task_id)
            deferred_ids.discard(task_id)
            remaining.discard(task_id)
            for dependent_id in dependents.get(task_id, []):
                pending_deps[dependent_id] -= 1
            push_eligible(task_id, stage, ready)
        elif outcome == "defer":
            _log_wait(task_id, detail)
            deferred_ids.add(task_id)
            push_eligible(task_id, stage, ready)
            return
        else:
            proven_harmless = (stage == settings.TDD_STAGE and _payload_proven_harmless(task))
            if proven_harmless:
                detail = detail + " [WOVEN-CLEAN: payload compiles and the suite completes with it in the tree - left woven for peers; only this unit's own tests are red]"
            task_queue.send_to_error(file, detail, task)
            print(f"[fail] {task['id']}: {detail}")
            if stage == 0 and task.get("kind") == "bootstrap" and not task.get("dependsOn"):
                # The domain ROOT is broken: cascading ~90 dependents one by one into
                # error/ turned recoverable waits into a 91-file graveyard and a watch
                # loop that spun silently on an empty queue (seed-002 rerun, 2026-11-12).
                # Dependents STAY in the queue; the next launch's ScaffoldUnresolved (or
                # --retry after the fix) resumes the domain. One fatal line, no scatter.
                what = ("build-manifest duty" if _build_manifest_duty(task) else "scaffold")
                raise FatalPipeline(
                    f"stage-0 {what} {task['id']} of '{task.get('project', '?')}' failed: "
                    f"{str(detail)[:300]} - the domain cannot build while its root is broken; "
                    f"its {len(dependents.get(task_id, []))} dependent(s) stayed in the queue. "
                    "Fix the container stage (MCP image/skill/environment) and relaunch with --retry.")
            if stage == settings.TDD_STAGE and not proven_harmless \
                    and not str(detail).startswith("dependsOn"):
                if dispatchers.revert_weave(task, discard_payload=True):
                    notice = _surface_rollback_hole(task)
                    if notice:
                        print(f"[hole  ] {task['id']}:{notice}")
                        _note_on_quarantine(task["id"], notice)
                else:
                    _warn_unrevertable_poison(task)
            elif stage == settings.TDD_STAGE and str(detail).startswith("dependsOn"):
                # A DEPENDENCY-CASCADE quarantine reverting its payload is rollback
                # suicide (2026-11-18 live: T2-037 was restored, its blocker re-quarantined
                # under a sibling race, the cascade reason reached this handler, the revert
                # undid SliceTestSupport - and the now-uncompilable test tree poisoned every
                # sibling's WOVEN-CLEAN probe, so each kept unit's payload got rolled back
                # in turn). A scheduling stall proves NOTHING about these bytes: the woven
                # payload and the record stay intact; WOVEN-UNVERIFIED already routes the
                # suspicion, and --retry restores the unit to adjudicate for real.
                print(f"[keep ] {task['id']}: dependency-cascade quarantine - payload woven, "
                      "record kept: not adjudicated, not proven poison")
            elif proven_harmless:
                print(f"[keep ] {task['id']}: payload stays woven - reverting would hole every "
                      "file that imports this unit's types (the T2-003 domain freeze)")
            remaining.discard(task_id)
            quarantine_dependents(task_id, by_id, files, dependents, remaining)
        processed["count"] += 1

    workers = max(1, int(getattr(args, "parallel", 1) or 1))

    def push_eligible(task_id, stage, ready):
        """Queue the dependents that this task's outcome may have made attemptable."""
        for dependent_id in dependents.get(task_id, []):
            if (dependent_id in remaining and dependent_id not in attempted
                    and by_id[dependent_id]["stage"] == stage and eligible(dependent_id)):
                heapq.heappush(ready, (tasks.task_sort_key(by_id[dependent_id]), dependent_id))

    def next_ready(stage, ready, busy):
        """Pop the next attemptable item.

        Items that are not attemptable are dropped rather than parked: every event that can change
        eligibility (a completion or a deferral) re-queues the dependents it affects, and a task
        already attempted this pass is never attempted twice. That is what keeps the stage loop from
        spinning on the whole-module gate failures of a domain that is still being woven.
        """
        while ready:
            item = heapq.heappop(ready)
            _, task_id = item
            if task_id not in remaining or task_id in attempted or not eligible(task_id):
                continue
            if workers > 1 and by_id[task_id]["project"] in busy:
                heapq.heappush(ready, item)
                return None
            attempted.add(task_id)
            return item
        return None

    for stage in sorted(by_stage):
        ready = []
        for task_id in by_stage[stage]:
            if task_id in remaining and eligible(task_id):
                heapq.heappush(ready, (tasks.task_sort_key(by_id[task_id]), task_id))

        if workers == 1:
            while ready:
                item = next_ready(stage, ready, set())
                if item is None:
                    break
                _, task_id = item
                task = by_id[task_id]
                print(f"[run ] {task['id']} -> {task['targetAgent']} ({task['path']})")
                outcome, detail = attempt(task)
                finalize(task_id, outcome, detail, stage, ready, False)
                if args.limit and processed["count"] >= args.limit:
                    return processed["count"], []
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=workers) as pool:
                inflight = {}
                busy = set()
                while ready or inflight:
                    while ready and len(inflight) < workers:
                        item = next_ready(stage, ready, busy)
                        if item is None:
                            break
                        _, task_id = item
                        task = by_id[task_id]
                        busy.add(task["project"])
                        print(f"[run ] {task['id']} -> {task['targetAgent']} ({task['path']})")
                        inflight[pool.submit(attempt, task)] = task_id
                    if not inflight:
                        break
                    future = next(as_completed(inflight))
                    task_id = inflight.pop(future)
                    busy.discard(by_id[task_id]["project"])
                    outcome, detail = future.result()
                    finalize(task_id, outcome, detail, stage, ready, False)
                    if args.limit and processed["count"] >= args.limit:
                        return processed["count"], []

        if any(task_id in remaining for task_id in by_stage[stage]):
            blocked = sorted(remaining, key=lambda item: tasks.task_sort_key(by_id[item]))
            return processed["count"], blocked
    if remaining:
        blocked = sorted(remaining, key=lambda item: tasks.task_sort_key(by_id[item]))
        return processed["count"], blocked
    return processed["count"], []
