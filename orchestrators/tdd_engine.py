"""The TDD loop and the dependency-graph queue drain.

``drain_queue`` is backend-agnostic: the entry scripts pass ``invoke_for_task``
(the backend's agent call) and it wires per-task invoke/verify closures around
the skill dispatchers and the verification gate.
"""
import heapq
import json
import re

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
    tokens -= test_gate.JAVA_LANG_NAMES | set(test_gate.JDK_TYPES)
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
    """Ids of queued stage-2 tasks of this domain that still have no coder payload.

    Surefire compiles every test source of the module, so a gate run while a sibling unit is
    still un-implemented can only fail on that sibling's symbols. Weaving is cheap and the gate
    is not: the orchestrator defers the gate until every payload of the domain exists, then one
    wave of gates decides the units. Without this, a pass costs one full build per unit and the
    domain never converges, because each unit's failure belongs to a peer that was never run.
    The scan itself is memoized per pass in dispatchers (one O(N) walk per domain, not per task).
    """
    project = task.get("project", "")
    return [pid for pid in dispatchers.payloadless_t2_ids(project) if pid != task["id"]]


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
        grants = int(ledger.get("grants") or 0)
        print(f"[tdd ] {task['id']} ledger holds {consumed} consumed attempts for an "
              "unchanged contract; granting one informed attempt")
        attempt_ledger.write(task["id"], grants=grants + 1)
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
        if not isinstance(demand, dict) or demand.get("owner") != export:
            continue
        kind = demand.get("kind")
        if kind in ("method", "constructor", "property", "attribute"):
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


def _blocked_by_peers(result, task):
    """True when a red stage-2 gate is NOT this unit's own fault.

    Surefire compiles the whole source set: a missing peer (or a test that will
    only compile once other tasks land) fails every task of the domain. The only
    compile failure worth retrying is one STRUCTURALLY located in this unit's own file
    (every toolchain prints "file:line: message"); a cascade of foreign symbol misses
    is a peer problem the coder cannot fix, so defer instead of burning the attempts.
    """
    if not isinstance(result, dict) or result.get("status") not in ("compile_error", "error"):
        return False
    if _own_type_member_demand(result, task):
        return False            # additive member demanded on MY exported type: nothing defers it
    if result.get("status") == "compile_error":
        missing_tokens = _identifier_tokens(" ".join(str(item) for item in (result.get("missing_symbols") or [])))
        if missing_tokens & _pending_symbols_of(task["project"], task["id"]):
            return True          # a queued peer will resolve this symbol; do not burn attempts
    owners = _queued_main_file_owners(task.get("project", ""))
    own = str(task.get("path", "")).split("/")[-1]
    locations = test_gate.error_locations(result)
    main_names = {name for name, _ in locations if name in owners}
    if own in main_names:
        # Own file blamed: only a STRUCTURAL error there is this unit's fault. A
        # "cannot find symbol" in the own file is a cascade from a foreign broken
        # definition, which no payload of this unit can repair - defer while the root
        # owner retries instead.
        own_structural = _own_structural(result, own, locations)
        if own_structural and _peer_supertype_conflict(task, result) \
                and not _peer_supertype_materialized(task, result):
            return True    # the supertype is not on the tree yet: nothing to adapt to, defer
                           # (materialized port: fall through to charge - deferral would
                           # deadlock both gates on the same module-wide compile failure)
        if not own_structural and any(owners.get(name) != task["id"] for name in main_names):
            return True
        return False                       # the own file is structurally broken: real retry
    if main_names and all(owners.get(name) != task["id"] for name in main_names):
        return True                        # every blamed production file belongs to other queued units
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
        located = {str(d.get("owner") or "") for d in demands}
        named = {owner_id for name, owner_id in owners.items()
                 if name.removesuffix(".java") in located or name in located}
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
            if dependent_task["stage"] == settings.TDD_STAGE and \
                    (settings.ROOT / "blackboard" / "coder-changes" / f"{dependent_id}.json").is_file():
                reason += (" [WOVEN-UNVERIFIED: this unit's payload is already spliced into the "
                           "source tree but its gate never ran; if OTHER units hang or fail to "
                           "compile, suspect this file]")
            task_queue.send_to_error(file, reason, dependent_task)
            print(f"[error] {file.name}: {reason}")
            if dependent_task.get("stage") == settings.TDD_STAGE:
                dispatchers.revert_weave(dependent_task, discard_payload=False)
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


def _tester_close_out(task):
    """Deterministic stage-1 close-out: validate red, guard classpath holes, dispatch the AST.

    Shared by the after-session path and the resume-skip, so a tester killed mid-session
    (valid red record on disk, no [done], no contract) is finished WITHOUT re-billing a
    full agent session.
    """
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
            "build file, so every gate of this domain would fail forever.")
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
        # deterministic import repair per affected project, re-record the red verdicts,
        # and only abort if a package is STILL foreign after the reroute.
        index = task_queue.load_index(include_error=True)
        for project in list(gaps):
            if not test_gate.repair_test_imports(workspace.project_root_for(project)):
                continue
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
                    and (workspace.project_root_for(task["project"]) / task["path"]).is_file()):
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
            pre_edit_snapshot = (refactor_audit.snapshot_sources(task)
                                 if task["stage"] == settings.EVALUATOR_STAGE else None)
            ok, reason = invoke_for_task(task, feedback)
            expected = workspace.project_root_for(task["project"]) / task["path"]
            if ok and task["stage"] != settings.TDD_STAGE and not expected.exists():
                return False, f"agent finished but {task['path']} was not created"
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
                    if _blocked_by_peers(result, task):
                        raise DeferredTask(problem)
                    return False, problem
                return True, ""      # the green gate supersedes the build gate
            if task["stage"] == settings.EVALUATOR_STAGE:
                return verification.verify_project(
                    project_root, args.verify, args.verify_timeout)
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
            task_queue.send_to_error(file, detail, task)
            print(f"[fail] {task['id']}: {detail}")
            if stage == settings.TDD_STAGE:
                dispatchers.revert_weave(task, discard_payload=True)
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
