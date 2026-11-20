"""Blackboard queue files: reading, indexing, emitting, and quarantining tasks."""
import json
import re
import shutil
from pathlib import Path

import ddd
import settings
import tasks
import telemetry
import test_gate


# The stage 0 scaffold's declared export (the architect prompt spells it). It is the
# identity of the task that generates a domain project root - path shape alone stopped
# identifying it the moment a second dependency-free stage 0 family (database migrations)
# shared the board, and any future specialist that queues bootstrap work inherits the
# ambiguity: the marker is the answer, the shape scan is only the legacy fallback.
SCAFFOLD_EXPORT = "project_scaffold"


def read_queue():
    entries = []
    for file in settings.QUEUE_DIR.glob("*.json"):
        try:
            task = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            entries.append(((999, file.name), file, None, f"unreadable JSON: {exc}"))
            continue
        if not isinstance(task, dict):
            entries.append(((998, file.name), file, None, "task must be a JSON object"))
            continue
        stage = task.get("stage")
        path = task.get("path")
        if isinstance(stage, int) and isinstance(path, str):
            entries.append((tasks.task_sort_key(task), file, task, None))
        else:
            entries.append(((997, file.name), file, task, None))
    entries.sort(key=lambda entry: entry[0])
    return entries


def load_index(include_error=False):
    """Task records by id, from queue + complete (and error/ when asked).

    include_error is for PRODUCER lookups only: a type whose producing task sits
    quarantined in error/ awaiting --retry HAS an owner; closure-style gap scans that
    miss it fabricate duplicate producers (the W4/WindowQuery class of incident) and
    abort healthy restarts with the wrong remedy. Consumers that must see only
    live work (emit-duplicate checks, --retry membership, id allocation) keep the
    default and treat error/ as absent, which is exactly the queue's semantics.
    """
    index = {}
    folders = (settings.QUEUE_DIR, settings.COMPLETE_DIR,
               settings.ERROR_DIR if include_error else None)
    for folder in folders:
        if folder is None:
            continue
        for file in folder.glob("*.json"):
            try:
                task = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(task, dict) and isinstance(task.get("id"), str):
                index[task["id"]] = task
    return index


def complete_task_ids():
    """IDs read from the content of completed files (names are T-###-<domain>.json)."""
    ids = set()
    for file in settings.COMPLETE_DIR.glob("*.json"):
        try:
            task = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(task, dict) and isinstance(task.get("id"), str):
            ids.add(task["id"])
    return ids


def next_task_id(stage):
    """Next free id for a stage, from queue and complete (ids are never reused)."""
    numbers = []
    for task_id in load_index():
        match = settings.ID_PATTERN.match(task_id)
        if match and int(match.group(1)) == stage:
            numbers.append(int(match.group(2)))
    return f"T{stage}-{(max(numbers) + 1 if numbers else 1):03d}"


def scaffold_task_id(slug):
    """Id of the stage 0 scaffold task of one domain project.

    Database tasks depend on it, so they cannot run before the domain project exists.
    The `export` marker is the PRIMARY key: stage 0 stopped being a single-task family when
    the database step began queueing dependency-free migration tasks, and any later
    bootstrap family inherits that ambiguity - the shape scan alone would credit whichever
    id sorted first. The dependency-free scan survives only as the fallback for boards
    written before the marker was taught.
    """
    dependency_free = []
    for task_id, task in sorted(load_index().items()):
        if not (settings.ID_PATTERN.match(task_id) and task_id.startswith("T0-")
                and task.get("kind") == "bootstrap" and task.get("project") == slug):
            continue
        if str(task.get("export", "")).strip() == SCAFFOLD_EXPORT:
            return task_id
        path_parts = str(task.get("path", "")).split("/")
        if not task.get("dependsOn") and "migrations" not in path_parts:
            dependency_free.append(task_id)
    return dependency_free[0] if dependency_free else "T0-000"


def database_task_ids(slug):
    """Ids of the database tasks already queued or complete for one domain project.

    Used to keep the database phase idempotent: re-running it would emit duplicates.
    """
    found = []
    for task_id, task in sorted(load_index().items()):
        if (task.get("project") == slug and task_id.startswith("T0-")
                and "migrations" in str(task.get("path", "")).split("/")):
            found.append(task_id)
    return found


def stage_task_summary(stage):
    lines = []
    for task_id, task in sorted(load_index().items()):
        match = settings.ID_PATTERN.match(task_id)
        if match and int(match.group(1)) == stage:
            lines.append(f"- {task_id}: {task.get('path')} ({task.get('intent')})")
    return "\n".join(lines) or "- none"


def reopen_completed(task_id):
    """Put a COMPLETED task back into the queue (same record bytes, same file name).

    Used by contract-regression detection: when a later weave moves a binding a
    completed file consumes, the compile error lands in that completed unit's own
    file - invisible to deferral (it is neither queued nor quarantined) while every
    live peer waits on it forever. Reopening hands the defect to its true owner's
    attempt budget; the T3 mirror that depends on it requeues too (validation would
    otherwise quarantine it as dangling). Returns True when the record moved.
    """
    src = next(iter(settings.COMPLETE_DIR.glob(f"{task_id}-*.json")), None)
    if src is None:
        return False
    try:
        task = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    project = str(task.get("project", ""))
    src.replace(settings.QUEUE_DIR / src.name)
    for mirror in list(settings.COMPLETE_DIR.glob("T3-*.json")):
        try:
            dep = json.loads(mirror.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if task_id in (dep.get("dependsOn") or []):
            mirror.replace(settings.QUEUE_DIR / mirror.name)
    (settings.GATE_CACHE_DIR / f"{task_id}.json").unlink(missing_ok=True)
    print(f"[reopen] {task_id}: completed file no longer compiles under the moved contract "
          f"- unit '{project}' back in the queue for re-adjudication")
    return True


def send_to_error(file, reason, task):
    if task is None:
        try:
            task = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            task = {"raw": file.read_text(encoding="utf-8", errors="replace")}
    payload = dict(task) if isinstance(task, dict) else {"raw": str(task)}
    payload["error"] = reason
    with telemetry.span("blackboard.error", {"file": file.name, "reason": reason,
                                             **telemetry.task_attributes(payload)}) as current:
        telemetry.mark_error(current, reason)
        (settings.ERROR_DIR / file.name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        # Idempotent: a task can be swept by the dependent-cascade while its own gate is
        # still running; whichever quarantine loses the race must not crash the drain.
        file.unlink(missing_ok=True)


def retry_error_tasks(patterns=()):
    """Move quarantined task files from blackboard/error back into the queue.

    Returns the restored ids. A file is restored when it still carries a valid
    task id; without patterns every error file moves, with patterns only the ids
    or file names matching one of them. Transient failures (a missing tool, an
    unreachable daemon) quarantine a whole dependency chain; this is how the
    chain comes back once the environment is fixed.
    """
    index = load_index()
    restored = []
    for file in sorted(settings.ERROR_DIR.glob("*.json")):
        try:
            task = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(task, dict) or not settings.ID_PATTERN.match(str(task.get("id", ""))):
            continue
        haystacks = (str(task["id"]), file.name)
        if patterns and not any(pattern in name for pattern in patterns for name in haystacks):
            continue
        if task["id"] in index:
            file.unlink()
            print(f"[skip ] {task['id']}: already in queue or complete")
            continue
        task.pop("error", None)
        destination = settings.QUEUE_DIR / tasks.task_file_name(task)
        destination.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
        file.unlink()
        index[task["id"]] = task
        restored.append(task["id"])
        print(f"[retry] {task['id']} -> queue/{destination.name}")
    return restored


def _claim_norm(text) -> str:
    return " ".join(str(text or "").strip().lower().rstrip(".").split())


OBSERVABILITY_SURFACES = ("correlation_key", "step_logs", "audit_trail", "metrics", "export")


def _steplog_claim_errors(staged, index):
    """STRATEGY OBSERVABILITY FLOOR + STEP-LOG CLAIM COVERAGE (2026-11-13, two layers of
    the same live failure). The execution strategy promised 5 step logs, phase 2 claimed
    none, the delivered code logged nothing - and every gate stayed green, because all
    validators check consistency and none checked completeness. Layer 1 (the FLOOR):
    every executable context's strategy MUST carry the complete observability surface -
    correlation key, step logs, audit records, named metrics, export - UNCONDITIONALLY,
    whether or not the business description asked for auditing or visibility; a strategy
    without the floor is refused before claims are even read (the old version SKIPPED
    silent strategies, which was the loophole one layer deeper). Layer 2 (the CLAIMS):
    every step_logs entry must be claimed VERBATIM (normalized exact text) by exactly ONE
    stage-2 task; unowned entries, double claims and off-plan claims are refused naming
    the string. Boards whose project has NO strategy file (legacy, unknown stacks) still
    skip - coverage cannot be demanded of a plan that never went through phase 1.

    Layer 2 only applies once the project HAS stage-2 tasks on the board (queue or staged
    batch). The pipeline schedules the stage-0 scaffold task in phase 1, BEFORE any
    decomposition exists - demanding claims there is a phase-order hole no agent can fix:
    live 2026-11-16 09:50 the architect burned 19 calls (budget 12) chasing an impossible
    refusal on T0 and the run died `[fatal] no scaffold task`. Coverage is not lost: the
    FIRST stage-2 emit for the slug re-runs this gate over the whole board and refuses an
    incomplete decomposition (pinned by V1/V6)."""
    errors = []
    projects = {str(t.get("project", "")) for t in staged if t.get("project")}
    for slug in sorted(projects):
        file = settings.COMPLETE_DIR / f"execution-strategy-{slug}.json"
        if not file.is_file():
            continue
        try:
            strategy = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        obs = strategy.get("observability")
        if not isinstance(obs, dict) or not obs:
            errors.append(
                f"{slug}: the execution strategy carries NO `observability` object - the "
                "audit + step-log floor is UNCONDITIONAL for every executable context: "
                "correlation key, step logs, audit-trail records, named metrics and the "
                "export surface are planned whether or not the business description asked "
                "for them; a service nobody can audit or observe at runtime is a "
                "compliance hole no later gate can see - write the strategy first")
            continue
        missing = [surface for surface in OBSERVABILITY_SURFACES if not obs.get(surface)]
        if missing:
            errors.append(
                f"{slug}: the strategy's observability object is missing the mandatory floor "
                f"surfaces {missing} - all five (correlation_key, step_logs, audit_trail, "
                "metrics, export) are required: an incomplete promise becomes incomplete "
                "code (2026-11-13: 5 step logs planned, 0 owned, 0 logged, all gates green)")
            continue
        # BOTH strategy spellings flatten (tasks.step_log_entries): the per-context
        # dict is what agent-strategy-architect actually writes - the list-only reader
        # let a dict floor skip the whole completeness law (2026-11-20, V9)
        entries = tasks.step_log_entries(obs.get("step_logs"))
        wanted = {}
        for entry in entries:
            key = _claim_norm(entry)
            if key:
                wanted.setdefault(key, str(entry).strip())
        if not wanted:
            continue
        claims = {}
        by_id = {}
        for record in list(index.values()) + list(staged):
            if isinstance(record, dict) and record.get("id"):
                by_id[str(record["id"])] = record
        if not any(str(r.get("project", "")) == slug
                   and int(r.get("stage") or 0) == settings.TDD_STAGE
                   for r in by_id.values()):
            continue  # phase-order hole: decomposition has not landed yet (see docstring)
        for record in by_id.values():
            if (str(record.get("project", "")) != slug
                    or int(record.get("stage") or 0) != settings.TDD_STAGE):
                continue
            for entry in ((record.get("observability") or {}).get("step_logs") or []):
                key = _claim_norm(entry)
                if key:
                    claims.setdefault(key, []).append(str(record.get("id", "?")))
        for key, entry in wanted.items():
            owners = claims.get(key) or []
            if not owners:
                errors.append(
                    f"{slug}: step log '{entry}' is promised by the execution strategy but "
                    "claimed by NO stage-2 unit - an unowned step log is a log line that "
                    "will never exist: add it VERBATIM to exactly one unit's "
                    "`observability.step_logs` (its coder logs it, its tester asserts it)")
            elif len(owners) > 1:
                errors.append(
                    f"{slug}: step log '{entry}' claimed by {sorted(set(owners))} - exactly "
                    "one owner: the class that crosses that boundary")
        for key, owners in claims.items():
            if key not in wanted:
                errors.append(
                    f"{slug}: unit(s) {sorted(set(owners))} claim step log '{key}' the "
                    "execution strategy never planned - fix the plan or the claim")
    return errors


# --- RULE (z): SHARED LITERALS ARE TABLED, NOT PROSE (2026-11-19, the R1/R2 roots of the
# 2026-11-18 drain). Meter names and request-path routes are literals used by >= 2 contracts
# (the registering unit, the recording units, the frozen test pair). While they lived only in
# intent prose, one board carried BOTH spellings as frozen law: the metrics facade's delivered
# names (`telemetry.validation.failed`) and the plan + consumer test names
# (`telemetry.samples.validation_failed`) - and the controller's test posting `/ingress/packets`
# against a chain, an intent and a slice all spelling `/telemetry/ingress`. No payload satisfies
# such a pair: the use case can only reach the collaborator's frozen API, and a deny-by-default
# chain never answers 202 on an unmapped route - the coder dies 3/3 on an unsatisfiable contract
# while every per-unit gate stayed green. Rule (l) named this class and admitted structure could
# not see it; the two `ast_hints` fields make the vocabulary visible and this gate joins it:
#   z1 every meter name is `owns`ed by exactly one unit; every `uses` names that owner
#      VERBATIM (a near-miss spelling is refused naming the closest tabled name); when the
#      whole domain is decomposed under the law, every strategy-floor metric has an owner;
#   z2 every (method, path) is `serves`d by exactly one unit; every `uses` names it verbatim;
#   z3 a literal spelled in a staged unit's own text (intent or a tabled `semantics`) must sit
#      in that unit's table - prose is never the only home of a shared literal;
#   z4 one unit, one table: its stage-1 and stage-2 twins carry IDENTICAL ast_hints when both
#      are staged; against a twin already on the board, every key present on both must match
#      (a regen cannot contradict the delivered table; either side may still ADD the
#      vocabulary keys).
# Duty words are stack-neutral; counting is per UNIT FAMILY (the T1/T2 pair of one number is
# one owner, not two). Boards that carry neither field and never spell a literal in prose skip
# the whole law - legacy readability (the F3 doctrine).
#   z5 a PROPERTY PATH is a shared literal too: units that bind or seed one table it in
#      `ast_hints.config` as {path, kind: value|list|map[, fields]} - the BINDING unit's
#      record declares the shape, the CONFIG unit cites it VERBATIM; the same path tabled
#      in two kinds (or two field sets), or a `value`/`map` child under a tabled `list`
#      prefix, is the impossible pair 2026-11-19 R4 froze (the record bound devices as a
#      LIST of (id, secret-hash, scope); the config contract seeded devices.secret-hash as
#      a SCALAR - no file satisfies both readers);
#   z6 the slice that imports a guard must be able to CONSTRUCT the chain: a surface unit
#      that pins a guard citing its served route must also table, among its own
#      collaborators, every PROJECT product the guard's table declares (its dependencies
#      and its method parameters). An untabled product is a bean the slice cannot supply -
#      R3: the controller test imported the chain whose concrete manager bean the wiring
#      factory (the plan's "sole registration mechanism") keeps out of every slice, and
#      the context died NoSuchBeanDefinition while its sibling test, which pinned the
#      manager, loaded fine.
ROUTE_PROSE_RE = re.compile(r"(?<![\w/:.\-])(/[A-Za-z][\w{}-]*(?:/[\w{}.*-]+)*)")


def _config_canon(path):
    """Relaxed-binding canonical form: each dotted segment camel->kebab, lowercase - so the
    binder's `secretHash` and the seed's `secret-hash` are ONE literal, as the runtime
    itself reads them."""
    return ".".join(re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", str(path).strip()).lower()
                    .split("."))


def _signature_param_text(signature):
    text = str(signature or "")
    return text[text.index("("):] if "(" in text else ""


def _config_entry_shape(record):
    return [(str(e.get("path")), str(e.get("kind")),
             tuple(sorted(_config_canon(f) for f in (e.get("fields") or []))))
            for e in _z_tables(record, "config") if isinstance(e, dict) and e.get("path")]

def _unit_family(record):
    """The id number one unit's T1/T2/T3 records share - owners are counted per unit."""
    ident = str(record.get("id", ""))
    return ident.rsplit("-", 1)[-1] if "-" in ident else ident


def _route_key(method, path):
    return (str(method or "").strip().upper(), "/" + str(path or "").strip().strip("/"))


def _route_prose(text):
    """Route-shaped literals in a unit's text: leading-slash, >=2 segments, first alphabetic.
    File paths (extension in the last segment) stay rule (a)'s territory; media types,
    placeholders and relative paths cannot match (the lookbehind eats their preceding char)."""
    found = []
    for match in ROUTE_PROSE_RE.finditer(str(text or "")):
        literal = match.group(1).rstrip("/")
        last = literal.rsplit("/", 1)[-1]
        if ".." in literal or re.search(r"\.\w{1,5}$", last):
            continue
        if literal not in found:
            found.append(literal)
    return found


def _closest_spelling(name, candidates):
    import difflib
    near = difflib.get_close_matches(str(name), sorted(candidates), n=1, cutoff=0.75)
    return f" - closest tabled spelling: '{near[0]}'" if near else ""


def _z_tables(record, key):
    hints = record.get("ast_hints") if isinstance(record.get("ast_hints"), dict) else {}
    entries = hints.get(key)
    return entries if isinstance(entries, list) else []


def _z_has_table(record, key):
    hints = record.get("ast_hints") if isinstance(record.get("ast_hints"), dict) else {}
    return isinstance(hints.get(key), list)


def _shared_literal_errors(staged, index):
    errors = []
    universe = {}
    for record in list(index.values()) + list(staged):
        if isinstance(record, dict) and record.get("id"):
            universe[str(record["id"])] = record
    staged_ids = {str(t.get("id")) for t in staged}
    projects = {str(t.get("project", "")) for t in staged if t.get("project")}
    for slug in sorted(projects):
        units = [r for r in universe.values()
                 if str(r.get("project", "")) == slug
                 and int(r.get("stage") or 0) in (1, 2)]
        strategy = {}
        file = settings.COMPLETE_DIR / f"execution-strategy-{slug}.json"
        try:
            strategy = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            strategy = {}
        obs = strategy.get("observability") if isinstance(strategy, dict) else {}
        floor = set()
        for entry in (obs or {}).get("metrics") or []:
            name = str((entry or {}).get("name") if isinstance(entry, dict) else entry).strip()
            if name:
                floor.add(name)

        # z4 - one unit, one table.
        by_family = {}
        for record in units:
            if isinstance(record.get("ast_hints"), dict):
                by_family.setdefault(_unit_family(record), []).append(record)
        for members in by_family.values():
            if len(members) < 2:
                continue
            by_stage = {int(m.get("stage") or 0): m for m in members}
            twin_a, twin_b = by_stage.get(1), by_stage.get(2)
            if twin_a is None or twin_b is None:
                continue
            hints_a, hints_b = twin_a["ast_hints"], twin_b["ast_hints"]
            both_new = (str(twin_a.get("id")) in staged_ids
                        and str(twin_b.get("id")) in staged_ids)
            if both_new:
                if hints_a != hints_b:
                    differ = sorted(k for k in set(hints_a) | set(hints_b)
                                    if hints_a.get(k) != hints_b.get(k))
                    errors.append(
                        f"{twin_a.get('id')}/{twin_b.get('id')}: the test task and the code task of "
                        f"one unit carry DIFFERENT ast_hints in {differ} - the tester asserts the "
                        "table it is given and the coder implements the table it is given; two "
                        "tables are two contracts and no payload satisfies both (rule (z4): the "
                        "pair must carry IDENTICAL tables - mirror the table VERBATIM into the twin)")
            else:
                for key in sorted(set(hints_a) & set(hints_b)):
                    if hints_a[key] != hints_b[key]:
                        staged_side = twin_a if str(twin_a.get("id")) in staged_ids else twin_b
                        delivered = twin_b if staged_side is twin_a else twin_a
                        errors.append(
                            f"{staged_side.get('id')}: its ast_hints.{key} disagrees with the "
                            f"table its unit twin {delivered.get('id')} carries on the board - "
                            "the frozen artifact already asserts/writes the delivered table; fix "
                            "this draft to match it, or move the change to the domain's replan "
                            f"(--replan {slug}) (rule (z4))")

        # collect the declared vocabulary (owner counts are per unit family)
        meters = {}
        for record in units:
            for entry in _z_tables(record, "meters"):
                if (isinstance(entry, dict) and entry.get("name")
                        and entry.get("duty") in ("owns", "uses")):
                    slot = meters.setdefault(str(entry["name"]),
                                             {"owns": set(), "uses": set()})
                    slot[entry.get("duty")].add(_unit_family(record))
        routes = {}
        for record in units:
            for entry in _z_tables(record, "routes"):
                if (isinstance(entry, dict) and entry.get("path")
                        and entry.get("duty") in ("serves", "uses")):
                    key = _route_key(entry.get("method"), entry.get("path"))
                    slot = routes.setdefault(key, {"serves": set(), "uses": set()})
                    slot[entry.get("duty")].add(_unit_family(record))

        # z3 - prose spelled into the table (staged records: only they can still be edited)
        for record in staged:
            if (str(record.get("project", "")) != slug
                    or int(record.get("stage") or 0) not in (1, 2)):
                continue
            text = " ".join([str(record.get("intent", ""))]
                             + [str(m.get("semantics") or "")
                                for m in (record.get("ast_hints") or {}).get("methods") or []
                                if isinstance(m, dict)])
            own_routes = {_route_key(e.get("method"), e.get("path"))
                          for e in _z_tables(record, "routes") if isinstance(e, dict)}
            for literal in _route_prose(text):
                hit = any(path == literal for _method, path in own_routes)
                if not hit:
                    errors.append(
                        f"{record.get('id')}: its text spells the route '{literal}' but the unit's "
                        "ast_hints.routes does not carry it - a route named in prose is a contract "
                        "the paired tester never receives (the seed-002 test posted "
                        "'/ingress/packets' while every tabled contract said '/telemetry/ingress'): "
                        "add {method, path, duty} to ast_hints.routes (serves for the unit that "
                        "answers it, uses for a guard/caller/slice) or move the sentence out of "
                        "the unit's text (rule (z3))")
            own_meters = {str(e.get("name")) for e in _z_tables(record, "meters")
                          if isinstance(e, dict)}
            for name in sorted(floor):
                if (re.search(rf"(?<![\w.\-]){re.escape(name)}(?![\w\-])", text)
                        and name not in own_meters):
                    errors.append(
                        f"{record.get('id')}: its text spells the floor meter '{name}' but the "
                        "unit's ast_hints.meters does not carry it - the two frozen tests written "
                        "from prose while the table holds silence is how one board froze both "
                        "spellings of one meter: add {name, duty} to ast_hints.meters ('uses' "
                        "when this unit records or asserts it; 'owns' belongs to exactly one "
                        f"unit, the one registering '{name}') or move the name out of the unit's "
                        "text (rule (z3))")

        # z1 - meter ownership and verbatim joins (law armed by the fields)
        if meters:
            for name, slot in sorted(meters.items()):
                owners, users = sorted(slot["owns"]), sorted(slot["uses"])
                if not owners:
                    errors.append(
                        f"{slug}: meter '{name}' is tabled by unit(s) {users} with duty 'uses' "
                        "but OWNED by none - no unit's contract registers that name, so no "
                        "payload can ever make it exist (2026-11-19 R1: the consumer test pinned "
                        "'telemetry.samples.validation_failed'; the delivered facade registered "
                        "'telemetry.validation.failed'; the coder died 3/3 between two frozen "
                        f"spellings): give the registering unit the '{name}' entry with duty "
                        f"'owns' spelled VERBATIM{_closest_spelling(name, set(meters) | floor)} "
                        "- if that unit was delivered before this law, --replan " + slug)
                elif len(owners) > 1:
                    errors.append(
                        f"{slug}: meter '{name}' is OWNED by units {owners} - exactly one unit "
                        "registers a name (rule (l)'s owner, made machine-checkable): the facade/"
                        "instrument that creates it; the others switch to duty 'uses'")
                if floor and name not in floor:
                    errors.append(
                        f"{slug}: meter '{name}' is tabled but the strategy floor "
                        f"(observability.metrics) never planned it - plan it in the strategy or "
                        "drop the claim; an off-plan name is vocabulary the floor cannot serve "
                        "(the step-log doctrine, rule (z1))")
            stage2 = [r for r in units if int(r.get("stage") or 0) == 2]
            if (floor and stage2
                    and all(_z_has_table(r, "meters") for r in stage2)):
                for name in sorted(floor - set(meters)):
                    errors.append(
                        f"{slug}: the strategy floor declares meter '{name}' but no unit tables it "
                        "with duty 'owns' - an unowned meter is a counter that will never exist: "
                        "claim it VERBATIM in the registering unit's ast_hints.meters (rule (z1), "
                        "the completeness half rule (u) could not see: it paired NAMES FUZZILY, "
                        "never VERBATIM)")

        # z2 - route serving and verbatim joins (law armed by the fields)
        for (method, path), slot in sorted(routes.items()):
            servers, users = sorted(slot["serves"]), sorted(slot["uses"])
            if not servers:
                errors.append(
                    f"{slug}: route {method} {path} is tabled by unit(s) {users} with duty "
                    "'uses' but SERVED by none - the deny-by-default chain (or any guard/slice) "
                    "citing a route no inbound unit answers is the seed-002 pair that froze the "
                    "controller against its own test (R2): move the entry to the unit that "
                    "answers it with duty 'serves', or fix the spelling to the served pair "
                    f"VERBATIM{_closest_spelling(path, {p for _m, p in routes})}")
            elif len(servers) > 1:
                errors.append(
                    f"{slug}: route {method} {path} is `serves`ed by units {servers} - exactly "
                    "one inbound unit answers a route; the others switch to duty 'uses'")

        # z5 - property paths: one path, one shape (the binder's record is the shape truth)
        shapes = {}  # canon path -> {kind: {family...}, fields: {tuple: {family...}}}
        for record in units:
            for path, kind, fields in _config_entry_shape(record):
                slot = shapes.setdefault(_config_canon(path),
                                         {"raw": path, "kind": {}, "fields": {}})
                slot["kind"].setdefault(kind, set()).add(_unit_family(record))
                if fields:
                    slot["fields"].setdefault(fields, set()).add(_unit_family(record))
        if shapes:
            for canon, slot in sorted(shapes.items()):
                if len(slot["kind"]) > 1:
                    detail = {k: sorted(v) for k, v in sorted(slot["kind"].items())}
                    errors.append(
                        f"{slug}: property path '{canon}' is tabled in TWO shapes {detail} - one "
                        "path has ONE shape, and it belongs to the unit whose record binds it: "
                        "the reader/writer units cite that shape VERBATIM in their ast_hints.config "
                        "(2026-11-19 R4: the record bound `devices` as a list while the config "
                        "contract seeded `devices.secret-hash` as a scalar - no file satisfies "
                        "both, and no test could see the pair until two contracts froze)")
                if len(slot["fields"]) > 1:
                    detail = {list(k): sorted(v) for k, v in sorted(slot["fields"].items())}
                    errors.append(
                        f"{slug}: property path '{canon}' is tabled with conflicting element "
                        f"fields {detail} - the element shape belongs to the binding record; "
                        "every other unit cites the same `fields` VERBATIM (rule (z5))")
                for other in sorted(shapes):
                    if (other != canon and canon.startswith(other + ".")
                            and "list" in shapes[other]["kind"]):
                        errors.append(
                            f"{slug}: path '{canon}' is tabled as a dotted child while "
                            f"'{other}' is tabled as a LIST - a list binds indexed entries "
                            "(`<path>[i].<field>`), never a dotted child; the element keys belong "
                            "in the list path's `fields` (R4: `devices.secret-hash` next to a "
                            "`devices` list is unreadable by every binder and unmissable by "
                            "every test)")
                        break
            # the config-artifact unit tables every path its document seeds (once the law is armed)
            for record in staged:
                if (str(record.get("project", "")) != slug
                        or int(record.get("stage") or 0) != settings.TDD_STAGE
                        or not tasks._path_is_config_artifact(record.get("path"))):
                    continue
                if not _z_has_table(record, "config"):
                    errors.append(
                        f"{record.get('id')}: the runtime configuration document seeds paths the "
                        "board now tables in `ast_hints.config`, yet this unit carries none - the "
                        "config unit lists EVERY operational path its artifact writes (citing the "
                        "binding units' shapes VERBATIM); an untabled path is a key a later reader "
                        "may reshape without a gate noticing (rule (z5))")

        # z6 - the slice that imports a guard must be able to construct the chain
        by_product = {}
        for record in units:
            if int(record.get("stage") or 0) == settings.TDD_STAGE:
                product = tasks.exported_product(record)
                if product:
                    by_product.setdefault(product.lower(), record)
        served_by_family = {}
        for record in units:
            for entry in _z_tables(record, "routes"):
                if isinstance(entry, dict) and entry.get("duty") == "serves":
                    served_by_family.setdefault(_unit_family(record), set()).add(
                        _route_key(entry.get("method"), entry.get("path")))
        for record in units:
            if (int(record.get("stage") or 0) != settings.TDD_STAGE
                    or _unit_family(record) not in served_by_family
                    or str(record.get("id")) not in staged_ids):
                continue  # only staged surface units can still be edited
            pinned = {str(d.get("type", "")).rsplit(".", 1)[-1].lower()
                      for d in _z_tables(record, "dependencies") if isinstance(d, dict)}
            for guard in units:
                if (guard is record
                        or int(guard.get("stage") or 0) != settings.TDD_STAGE):
                    continue
                guard_cites = {_route_key(e.get("method"), e.get("path"))
                               for e in _z_tables(guard, "routes")
                               if isinstance(e, dict) and e.get("duty") == "uses"}
                if not (guard_cites & served_by_family[_unit_family(record)]):
                    continue
                needed = set()
                for dep in _z_tables(guard, "dependencies"):
                    if isinstance(dep, dict):
                        name = str(dep.get("type", "")).rsplit(".", 1)[-1]
                        if name.lower() in by_product:
                            needed.add(name.lower())
                for member in _z_tables(guard, "methods"):
                    if isinstance(member, dict):
                        for token in tasks.CAMEL_TYPE_RE.findall(
                                _signature_param_text(member.get("signature"))):
                            if token.lower() in by_product:
                                needed.add(token.lower())
                own = (str(tasks.exported_product(record) or "").lower(),
                       str(tasks.exported_product(guard) or "").lower())
                missing = sorted(needed - pinned - set(own))
                if missing:
                    errors.append(
                        f"{record.get('id')}: it serves a route the guard {guard.get('id')} "
                        f"cites, but the guard's own table declares collaborators {missing} "
                        "the record does not pin - a slice importing that chain cannot "
                        "construct it (2026-11-19 R3: the controller test @Imported the chain "
                        "whose concrete manager bean the wiring factory alone registered; the "
                        "context died NoSuchBeanDefinition and the unit burned 3/3 on a gap in "
                        "its CONTRACT, while its sibling slice, which pinned the manager, "
                        "loaded fine). Pin each product the guard needs as a collaborator "
                        "{type, task_id} (doubles come from the table; the test writes only "
                        "against tables) - rule (z6)")
    return errors


# Reserved package/path segments (live 2026-11-16 10:15: the architect planned the driver
# layer as `...intake.interface` - a Java reserved word. The weaver can never render the
# package line, the frozen test can never compile, and every unit in the family bounced
# to quarantine while the coder, correctly, could not change a pinned package. A plan
# segment that is reserved IN THE PLANNED LANGUAGE is an impossible artifact: die at
# emit, at zero sessions. The vocabulary is per-language DATA (stack-neutral engine),
# restricted to unconditional reserved words; contextual ones (Java record/var/yield,
# Python match) stay legal. No strategy or an unknown language -> skip (legacy-safe).
LANGUAGE_RESERVED_SEGMENTS = {
    "java": {"abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
             "class", "const", "continue", "default", "do", "double", "else", "enum",
             "extends", "final", "finally", "float", "for", "goto", "if", "implements",
             "import", "instanceof", "int", "interface", "long", "native", "new",
             "package", "private", "protected", "public", "return", "short", "static",
             "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
             "transient", "try", "void", "volatile", "while"},
    "typescript": {"break", "case", "catch", "class", "const", "continue", "debugger",
                   "default", "delete", "do", "else", "enum", "export", "extends",
                   "false", "finally", "for", "function", "if", "import", "in",
                   "instanceof", "interface", "let", "new", "null", "package", "private",
                   "protected", "public", "return", "super", "switch", "this", "throw",
                   "true", "try", "typeof", "var", "void", "while", "with"},
    "javascript": {"break", "case", "catch", "class", "const", "continue", "debugger",
                   "default", "delete", "do", "else", "export", "extends", "false",
                   "finally", "for", "function", "if", "import", "in", "instanceof",
                   "interface", "let", "new", "null", "package", "private", "protected",
                   "public", "return", "super", "switch", "this", "throw", "true", "try",
                   "typeof", "var", "void", "while", "with"},
    "python": {"False", "None", "True", "and", "as", "assert", "async", "await", "break",
               "class", "continue", "def", "del", "elif", "else", "except", "finally",
               "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
               "not", "or", "pass", "raise", "return", "try", "while", "with"},
    "go": {"break", "case", "chan", "const", "continue", "default", "defer", "else",
           "fallthrough", "for", "func", "go", "goto", "if", "import", "interface",
           "map", "package", "range", "return", "select", "struct", "switch", "type",
           "var"},
}


def _strategy_language(slug):
    # shared with the (k)/(m)/(n) plan rules - one strategy reader, one vocabulary key
    return tasks.strategy_language(slug)


SECURITY_REF_RE = re.compile(r"\b(?:TB|P|DC|AZ|SI|SD|R|AS)-\d{2}\b")
# the performance/AI specs' own id spaces (2026-11-19): WB/PB/PI/PA/R for performance,
# AR/AC/AM/AA/R for AI - a duty's spec_ref must resolve inside its own artifact, and the
# claim gate reads the pair (spec_ref + capability) from the unit's text exactly as (y)
# does for security duties.

SECURITY_TOKEN_SECTIONS = ("trust_boundaries", "principals", "data_classification",
                           "authorization_matrix", "invariants")
SECURITY_TRACE_FIELDS = ("intent",)


def _security_spec(slug):
    """The domain's security spec, or None when the phase never wrote one (legacy board).

    Same literal as `ddd.SECURITY_SPEC_PREFIX`; the pairing is pinned by construction -
    the gauntlet writes the fixture through `ddd.security_spec_path` and this gate must
    read it back, so a rename on one side fails a case instead of quietly blinding the
    claim gate.
    """
    path = settings.COMPLETE_DIR / f"security-spec-{slug}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _security_declared_ids(spec):
    """Every entry id the spec declares (section tables + the secrets inventory)."""
    declared = set()
    for section in SECURITY_TOKEN_SECTIONS:
        for entry in spec.get(section) or []:
            if isinstance(entry, dict) and str(entry.get("id", "")).strip():
                declared.add(str(entry["id"]).strip())
    for entry in _security_secret_inventory(spec):
        if isinstance(entry, dict) and str(entry.get("id", "")).strip():
            declared.add(str(entry["id"]).strip())
    return declared


def _security_secret_inventory(spec):
    """The secrets inventory list, or [] when the section is malformed: a spec the
    security step wrote badly is refused by the step's own gate, never by a crash here."""
    secrets = spec.get("secrets")
    entries = secrets.get("inventory") if isinstance(secrets, dict) else None
    return entries if isinstance(entries, list) else []


CROSS_OWNER_RE = re.compile(r"cross[- ]owner|other tenant|another tenant|foreign (?:tenant|owner)"
                            r"|owned by (?:a |another |someone else)|someone else", re.I)


def _unit_text(record):
    """The fields a stack-neutral gate may read off a unit: its prose and its pinned table -
    never the source it has not written yet."""
    hints = record.get("ast_hints") or {}
    return " ".join([str(record.get(field, "")) for field in SECURITY_TRACE_FIELDS]
                     + [str(value) for value in hints.values() if isinstance(value, str)])


def _inbound_units(units):
    """Stage-2 entry adapters - the same reading rule (p) uses (layer or inbound prose)."""
    return [unit for unit in units if unit.get("stage") == settings.TDD_STAGE
            and (str(unit.get("layer", "")) in ("interface", "api", "entry")
                 or tasks.INBOUND_RE.search(str(unit.get("intent", ""))))]


def _pins(entry_unit, product_unit, by_id):
    """Does the entry unit carry the enforcing unit - by task id or by its exported type -
    in its own collaborator table, or depend on it (directly or through the graph)?
    The drain schedules ONLY on `dependsOn` (tdd_engine: unmet = deps - complete) and the
    tester writes assertions ONLY against pinned tables, so an enforcing unit the entry
    never pulls in can be gated and closed in the same wave as the surface it was meant to
    defend - after that surface's frozen test was written against a constructor with no
    guard in it, and the retrofit arrives too late to change the frozen pair."""
    deps = [dep for dep in (entry_unit.get("ast_hints") or {}).get("dependencies") or []
            if isinstance(dep, dict)]
    product_id = str(product_unit.get("id", ""))
    if product_id in {str(dep.get("task_id", "")) for dep in deps}:
        return True
    pinned_types = {str(dep.get("type", "")).strip().lower() for dep in deps}
    faces = {str(face).strip().lower()
             for face in [tasks.exported_product(product_unit), product_unit.get("export"),
                          *((product_unit.get("ast_hints") or {}).get("implements") or [])]
             if face}
    if faces & pinned_types:
        return True
    return tasks.depends_transitively(str(entry_unit.get("id", "")), product_id, by_id)


def _security_reach_errors(slug, spec, claims, by_id):
    """Gap B (2026-11-18): the claim gate proved a duty was CLAIMED, never that it was claimed
    BY THE UNIT THAT RUNS ON THE DEFENDED PATH. Three refusals, all field comparisons on the
    plan's own vocabulary (no source is read):

    (y1 IMPLANTATION) the claim must sit on a stage-2 unit: a duty named only in a tester's or
        an evaluator's prose is a duty no code ever implements;
    (y2 REACH) the unit that enforces a row must be reachable from the entry adapter that IS
        that row's surface - its collaborator table or its `dependsOn` - so the guard exists
        and is wired BEFORE the surface's frozen test is written and before its own close-out
        (the drain orders units only by `dependsOn`);
    (y3 ASSERTION AT THE SURFACE) that adapter's paired stage-1 test carries the row id and the
        cross-owner case: a permission rule proven only on the predicate's own unit test is a
        rule the request path never exercises (a role check that still fetches another tenant's
        row by id passes it, and that is the IDOR the spec forbids).

    The join key is the row's `surface` text, widened by any strategy surface whose name it
    carries: phase 1's `surfaces[].name` is what the architect is told to copy into both the
    row and the entry unit's intent, so a row matched to no inbound adapter is either a
    consumer/job/cli row (nothing to wire) or a plan that never named its surface. SURFACE
    OWNERSHIP closes that dodge: a declared surface no inbound unit carries is refused - the
    reach law needs the name, and a plan that hides the adapter hides the hole.
    """
    errors = []
    surfaces = [ddd.norm_surface(surface.get("name"))
                for surface in (ddd.strategy_surfaces(slug) or []) if isinstance(surface, dict)]
    rows = {str(row.get("id", "")).strip(): row for row in (spec.get("authorization_matrix")
            or []) if isinstance(row, dict)}
    units = [record for record in by_id.values()
             if str(record.get("project", "")) == slug and int(record.get("stage") or 0) >= 1]
    inbound = _inbound_units(units)
    testers = {}
    for unit in units:
        if int(unit.get("stage") or 0) != settings.TESTER_STAGE:
            continue
        mark = str(unit.get("id", "")).rsplit("-", 1)
        if len(mark) == 2:
            testers.setdefault(mark[1], []).append(unit)
    for name in sorted(n for n in surfaces if n):
        # SURFACE OWNERSHIP: the reach law below needs a join, and a join needs the entry unit
        # to name its surface. A declared surface no inbound unit carries is therefore either
        # an unscheduled adapter or a plan that dodges the join by silence - both are the same
        # hole the step-log claim law killed (a promised boundary with no owner).
        if not any(name in ddd.norm_surface(_unit_text(unit)) for unit in inbound):
            errors.append(
                f"{slug}: surface {name!r} is declared by phase 1 and named by NO inbound unit "
                "of the plan - schedule the adapter that IS this surface (its intent carries the "
                "strategy's `surfaces[].name` verbatim), or the surface ships unwired and "
                "unauthorized while every per-unit gate stays green")
    for rid, row in sorted(rows.items()):
        row_text = ddd.norm_surface(row.get("surface"))
        names = {name for name in (row_text,) if name}
        names |= {name for name in surfaces
                  if name and (name in row_text or row_text in name)}
        if not names:
            continue
        matched = [unit for unit in inbound
                   if any(name in ddd.norm_surface(_unit_text(unit)) for name in names)]
        if not matched:
            continue  # no inbound adapter claims this surface: nothing on the path to wire
        claim = claims.get(rid)
        if not claim:
            continue  # (closure) already refused above
        implementers = [record for record in claim["records"]
                        if int(record.get("stage") or 0) == settings.TDD_STAGE]
        if not implementers:
            errors.append(
                f"{slug}: security duty {rid} is claimed only by "
                f"{sorted(str(record.get('id', '?')) for record in claim['records'])} - a test "
                "or refactor task carries no implementation: name the token in the stage-2 unit "
                "that ENFORCES it, or the duty ships as a comment")
            continue
        wired = [entry for entry in matched if any(_pins(entry, unit, by_id)
                                                   for unit in implementers)]
        for entry in [item for item in matched if item not in wired]:
            errors.append(
                f"{slug}: surface {row.get('surface')!r}: {rid} is enforced by "
                f"{sorted(str(unit.get('id')) for unit in implementers)} but the entry unit "
                f"{entry.get('id')} neither pins that unit in `ast_hints.dependencies` nor "
                "depends on it - the drain orders units ONLY by `dependsOn` and the tester "
                "writes assertions ONLY against pinned tables, so this surface is implemented, "
                "gated and closed with no guard on its path (and the guard arrives, if at all, "
                "as a retrofit that can no longer change the frozen pair). Wire the enforcing "
                "unit into the entry unit's contract, or put the predicate on the unit that "
                "does the lookup")
        for entry in wired:
            mark = str(entry.get("id", "")).rsplit("-", 1)
            pair = testers.get(mark[-1], []) if len(mark) == 2 else []
            if not any(rid in _unit_text(tester)
                       and CROSS_OWNER_RE.search(str(tester.get("intent", "")))
                       for tester in pair):
                errors.append(
                    f"{slug}/{entry.get('id')}: {rid} is enforced on the request path but the "
                    "paired stage-1 test never carries the row and its CROSS-OWNER case (a valid "
                    "identifier owned by someone else, refused) - the spec's `test_duty` is "
                    "asserted AT the lookup: a permission rule proven only on its own unit test "
                    "is a rule no request ever meets")
    return errors


def _security_claim_errors(staged, index):
    """SECURITY DUTY CLAIM COVERAGE - the same completeness hole the step-log gate closed,
    one artifact later. The security spec tables what must hold; if the decomposition never
    claims a duty, that rule exists in no unit, ships in no code, and every per-unit gate
    stays green. An unclaimed authorization rule is an unenforced one.
    Two layers, both stack-neutral token comparisons (no source is ever read):
    (closure) every duty's `spec_ref` must appear as a token in at least one task of that
     domain - naming a duty is what schedules it;
    (mapping) and the claiming task must also carry the duty's `capability` token, because a
     bare `AZ-03` is a citation, not a realization: the requirement and the thing that holds it
     travel together, or the duty is only decorated. The engine never checks WHICH mechanism the
     architect chose - that judgment belongs to the tech-stack skill, and a stack-neutral validator
     naming frameworks would be the leak this whole phase exists to prevent;
    (fabrication) a token shaped like a spec entry that the spec does not declare is refused
     too: one plan, one vocabulary.
    The placement layer that coverage alone cannot see ((y1) implantation, (y2) reach,
    (y3) assertion at the surface) lives in `_security_reach_errors`.
    Three deliberate skips, each blocking a refusal no agent could answer:
    (a) the domain has no spec file - boards that never ran the phase;
    (b) the batch stages no application task - the scaffold and the database step emit
     stage 0 only, and a stage-0 session cannot claim a decomposition duty;
    (c) the project has no stage-2 unit on the board yet - demanding claims before
     decomposition exists is the phase-order hole that burned an architect's whole budget
     on 2026-11-16 09:50.
    """
    errors = []
    projects = {str(t.get("project", "")) for t in staged if t.get("project")}
    if not any(int(record.get("stage") or 0) >= 1 for record in staged):
        return errors  # skip (b): a stage-0 emit answers no decomposition duty
    by_id = {}
    for record in list(index.values()) + list(staged):
        if isinstance(record, dict) and record.get("id"):
            by_id[str(record["id"])] = record
    for slug in sorted(projects):
        spec = _security_spec(slug)
        if spec is None:
            continue  # skip (a)
        declared = _security_declared_ids(spec)
        # spec_ref -> the capability tokens its duties say must hold. A claim without one of
        # them is a token pasted onto a unit: the duty was "covered" and nothing was mapped.
        duty_caps = {}
        for duty in (spec.get("duties") or []):
            if not isinstance(duty, dict):
                continue
            ref = str(duty.get("spec_ref", "")).strip()
            if ref:
                capability = str(duty.get("capability", "")).strip()
                duty_caps.setdefault(ref, set())
                if capability:
                    duty_caps[ref].add(capability)
        if not any(str(record.get("project", "")) == slug
                   and int(record.get("stage") or 0) == settings.TDD_STAGE
                   for record in by_id.values()):
            continue  # skip (c): decomposition has not landed yet (see docstring)
        claims, fabricated = {}, {}
        for record in by_id.values():
            if str(record.get("project", "")) != slug or int(record.get("stage") or 0) < 1:
                continue
            text = _unit_text(record)
            for token in SECURITY_REF_RE.findall(text):
                if token in declared:
                    claim = claims.setdefault(token, {"owners": set(), "mapped": False,
                                                      "records": []})
                    claim["owners"].add(str(record.get("id", "?")))
                    claim["records"].append(record)
                    caps = duty_caps.get(token) or set()
                    if not caps or any(cap in text for cap in caps):
                        claim["mapped"] = True
                else:
                    fabricated.setdefault(token, []).append(str(record.get("id", "?")))
        for token in sorted(set(duty_caps) - set(claims)):
            errors.append(
                f"{slug}: security duty {token} is claimed by NO unit - name the token in the "
                "enforcing unit's intent (the unit that owns its `unit_kind`: see the mechanism "
                "table), and its tester asserts the permitted, denied and cross-owner cases. Where "
                "the stack realizes nothing, the duty still needs its home - the CONFIG unit for "
                "custody/lifetime facts, the store or domain unit for identifier and crypto shapes; "
                "a reported risk never substitutes for a claiming unit (this session has no write "
                "path to the spec: if the spec itself is wrong, stop and re-run the security phase "
                "for this domain with the strategy amended)")
        for token in sorted(claims):
            caps = duty_caps.get(token) or set()
            if caps and not claims[token]["mapped"]:
                errors.append(
                    f"{slug}: security duty {token} is claimed by {sorted(claims[token]['owners'])} "
                    f"without the capability its duty names ({sorted(caps)}) - a bare token is a "
                    f"citation, not a mapping: spell the capability beside the concrete mechanism "
                    f"the active tech-stack skill provides, in that unit's intent")
        for token, owners in sorted(fabricated.items()):
            errors.append(
                f"{slug}: unit(s) {sorted(set(owners))} name security entry {token} the spec never "
                f"declares - fix the plan or the spec, never both silently")
        errors.extend(_security_reach_errors(slug, spec, claims, by_id))
    return errors


def _planning_claim_lines(slug, units):
    """Unclaimed performance/AI duties for one domain, read over `units` (all records of
    the project the caller can see). The claim law is the (y1) FORM - the pair (spec_ref +
    capability) VERBATIM inside one STAGE-2 unit's text - and deliberately not (y2)/(y3):
    a load-shed or a model-port duty has no surface-reach geometry the way an ownership
    predicate does, and inventing one would refuse lawful placements. Phase-order hole
    (V6b doctrine): until the domain has any stage-2 unit, nothing is demanded.
    A spec the phase never wrote is not this gate's subject (the pipeline already stops
    on a missing mandatory spec; an AI spec is optional by directive)."""
    lines = []
    for label, path in (("performance", ddd.performance_spec_path(slug)),
                        ("AI", ddd.ai_spec_path(slug))):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(spec, dict):
            continue
        duties = [duty for duty in (spec.get("duties") or []) if isinstance(duty, dict)]
        stage2 = [u for u in units if int(u.get("stage") or 0) == settings.TDD_STAGE]
        if not duties or not stage2:
            continue
        for duty in duties:
            ref = str(duty.get("spec_ref", "")).strip()
            cap = str(duty.get("capability", "")).strip()
            if not ref or not cap:
                continue
            claimed = any(ref in _unit_text(unit)
                          and re.search(r"\b" + re.escape(cap) + r"\b", _unit_text(unit))
                          for unit in stage2)
            if not claimed:
                lines.append(
                    f"{slug}: {label} duty {ref} ({cap}) is claimed by no stage-2 unit - "
                    "the plan cannot discharge a rule it was never shown: copy spec_ref and "
                    "capability VERBATIM into the intent of the unit that enforces it (the "
                    "claim law of the (y) family; the machine enforces the claim, the "
                    "placement stays the architect's) - if this spec arrived after its "
                    f"decomposition, relaunch with --replan {slug}")
    return lines


def planning_claim_gaps(slug):
    """One domain's unclaimed performance/AI duties OVER THE LIVE BOARD (same reading the
    emit gate applies, same role `security_claim_gaps` plays for the security spec)."""
    index = load_index()
    units = [record for record in index.values()
             if isinstance(record, dict) and str(record.get("project", "")) == slug]
    return _planning_claim_lines(slug, units)


def security_claim_gaps(slug):
    """One domain's security-claim gaps OVER THE LIVE BOARD (queue + complete; quarantined
    records are invisible, exactly as the drain sees them).

    Same reading `_security_claim_errors` applies to an emit batch, so the pipeline can
    answer a question the emit gate structurally cannot: is a spec that arrived AFTER its
    decomposition actually discharged? [] means every duty is claimed, implemented,
    reachable from the surface it defends, and asserted at that surface.
    """
    index = load_index()
    live = [record for record in index.values()
            if isinstance(record, dict) and str(record.get("project", "")) == slug]
    return _security_claim_errors(live, index)


def replan_domain(slug):
    """Archive one domain's PLAN (strategy, security spec, stage 1-3 records) so its phases
    re-run from the top - and only its plan. The board, never the source tree.

    Two states need this and no gate can heal them alone: a strategy that names no inbound
    surface (the security step then tables rows for what it was told about, and nothing
    downstream can see the gap), and a spec written after its decomposition was frozen (the
    emit gate refuses nothing it cannot answer, so its duties stay unclaimed). Moving the
    artifacts to blackboard/archive/ makes each phase see its input as missing and re-run;
    restore by moving them back. Delivered sources are untouched: the fresh units weave
    into them exactly as a repair pass does. Returns {"strategy": bool, "spec": bool,
    "tasks": [ids]}.
    """
    archive = settings.BLACKBOARD / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    moved = {"strategy": False, "spec": False, "performance": False, "ai": False, "tasks": []}
    strategy_file = settings.COMPLETE_DIR / f"execution-strategy-{slug}.json"
    spec_file = settings.COMPLETE_DIR / f"security-spec-{slug}.json"
    performance_file = settings.COMPLETE_DIR / f"performance-spec-{slug}.json"
    ai_file = settings.COMPLETE_DIR / f"ai-spec-{slug}.json"
    for file, key in ((strategy_file, "strategy"), (spec_file, "spec"),
                      (performance_file, "performance"), (ai_file, "ai")):
        if file.is_file():
            shutil.move(str(file), str(archive / file.name))
            moved[key] = True
    for folder in (settings.QUEUE_DIR, settings.COMPLETE_DIR):
        for file in sorted(folder.glob("*.json")):
            try:
                record = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict) or str(record.get("project", "")) != slug:
                continue
            if int(record.get("stage") or 0) not in (1, 2, 3):
                continue
            shutil.move(str(file), str(archive / file.name))
            moved["tasks"].append(str(record.get("id", file.stem)))
    moved["tasks"] = sorted(set(moved["tasks"]))
    # /tmp planning state of the archived plan is stale by definition: drafts, the digest,
    # every per-context slice and every symbol table join the archive decision (the loop
    # rebuilds them; leaving the old bytes would let a next launch's claim step number
    # itself against a plan that no longer exists).
    for stale in (DRAFT_DIR.glob(f"{slug}-*.json"),
                  Path("/tmp").glob(f"phase2-digest-{slug}.json"),
                  Path("/tmp").glob(f"phase2-slice-{slug}-*.json")):
        for file in stale:
            file.unlink(missing_ok=True)
    return moved



# THE WRITABLE CHANNEL (2026-11-19, the prompt-contract trap the operator review caught):
# a stage-1/2 unit's `path` is the file its agent will actually create - and the pipeline
# has exactly two writers: the language weavers (source files) and the text-payload route
# the config units use (.yml/.yaml/.properties full-file writes). Template files -
# prompts/*.st, docs/*.md, fixtures/*.txt - have NO writer on this board: the coder emits a
# payload the dispatcher routes to a weaver that cannot splice a template, the stage-0
# channel belongs to the container/migration authors, and the architect cannot write project
# files at all. A unit planned onto such a path is a duty without a lawful channel (the D4
# class), discovered at its first red gate - so emit refuses it and the plan moves the
# artifact where it can live: a prompt contract becomes a Java TYPE whose tabled members
# carry the contract elements; other facts belong to a source type or the config document.
def _manifest_order_errors(staged, index):
    """BUILD-MANIFEST PRECEDES EVERY RED COMPILE (2026-11-20 root fix - AS15's prose law
    promoted to the machine tier): a stage-0 task whose export is `build-manifest` means
    the plan ADDS coordinates the scaffold build file lacks, and a module's test compile
    pulls the WHOLE module's classpath - the same fact in Maven, Gradle, npm and pip.
    So EVERY stage-1 and stage-2 task of that project must reach the manifest through
    `dependsOn`, transitively: without the edge, the unit's first red gate is the D4
    import storm (live 2026-11-18; repeated on the 2026-11-20 board, where T2-019's
    chain never depended on T0-007). The rule reads ONLY structural board facts - the
    export marker and the dependency closure - never an annotation, artifact or
    framework name: the engine stays stack-agnostic, and the mapping table keeps its
    monopoly on mechanism vocabulary."""
    world = dict(index)
    world.update({str(task.get("id")): task for task in staged
                  if isinstance(task, dict) and task.get("id")})
    manifests = {}
    for tid, task in world.items():
        if not isinstance(task, dict) or int(task.get("stage") or 0) != 0:
            continue
        if str(task.get("export", "")).strip() == BUILD_MANIFEST_EXPORT:
            manifests.setdefault(str(task.get("project", "")), []).append(str(tid))
    errors = []
    for task in staged:
        if not isinstance(task, dict) or int(task.get("stage") or 0) not in (1, 2):
            continue
        targets = manifests.get(str(task.get("project", "")))
        if not targets:
            continue
        seen, stack = set(), [str(task.get("id", ""))]
        reached = None
        while stack:
            for dep in world.get(stack.pop(), {}).get("dependsOn") or []:
                dep = str(dep)
                if dep in targets:
                    reached = dep
                    break
                if dep not in seen:
                    seen.add(dep)
                    stack.append(dep)
            if reached:
                break
        if not reached:
            errors.append(
                f"{task.get('id')}: the project schedules build-manifest {targets} - new "
                "coordinates must be in the build file BEFORE the first compile of the "
                "module its tests build - add the manifest id to `dependsOn` (the pair's "
                "twin then inherits it through the pair)")
    return errors


def _writable_channel_errors(staged):
    errors = []
    for task in staged:
        if int(task.get("stage") or 0) not in (settings.TESTER_STAGE, settings.TDD_STAGE):
            continue
        path = str(task.get("path") or "").replace("\\", "/")
        if not path:
            continue
        suffix = Path(path).suffix.lower()
        if suffix in test_gate.SOURCE_SUFFIXES or suffix in (".yml", ".yaml", ".properties"):
            continue
        errors.append(
            f"{task.get('id')}: its `path` '{path}' ends in {suffix or '(no suffix)'} - the pipeline "
            "writes LANGUAGE SOURCES and configuration documents (.yml/.yaml/.properties) "
            "only; no agent of this board authors template or text files. A unit planned "
            "there is a duty without a lawful channel: move the artifact INTO a source type "
            "the weaver lands (an AI prompt contract is a Java type whose five members are "
            "tabled in ast_hints: version, role identity, input placeholders, output-schema "
            "reference, refusal text), or onto the configuration document that owns the key "
            "- do not re-emit hoping for a writer that does not exist")
    return errors


def _reserved_segment_errors(staged):
    errors = []
    projects = {str(t.get("project", "")) for t in staged if t.get("project")}
    for slug in sorted(projects):
        reserved = LANGUAGE_RESERVED_SEGMENTS.get(_strategy_language(slug))
        if not reserved:
            continue
        for task in staged:
            if str(task.get("project", "")) != slug:
                continue
            candidates = []
            package = str((task.get("ast_hints") or {}).get("package") or "")
            if package.strip():
                candidates.append(("ast_hints.package", package.split("."), package))
            export = str(task.get("export") or "")
            if "." in export:
                candidates.append(("export", export.split("."), export))
            path = str(task.get("path") or "")
            directories = [seg for seg in path.split("/")[:-1] if seg]
            if directories:
                candidates.append(("path", directories, path))
            for field, segments, shown in candidates:
                hits = [seg for seg in segments
                        if str(seg).strip().lower() in reserved
                        or str(seg).strip() in reserved]
                if hits:
                    errors.append(
                        f"{task.get('id')}: {field} '{shown}' uses segment(s) "
                        f"{sorted(set(hits))} - reserved words in {slug}'s planned "
                        f"language: no artifact can ever compile or weave under them. "
                        "Rename the segment (a driver layer is 'api' or 'adapters', "
                        "never 'interface') and re-emit once.")
    return errors


def emit_tasks(paths):
    """Validate a batch of task files against the schema, then write them to the queue.

    A path may hold one task object or an array of them, and several paths may be passed at
    once: the architect drafts one file per bounded context and emits them together, so the whole
    plan is still validated as ONE batch (cross-context pins, provider closure and the security
    reach law each see every file) while no single output turn has to carry a 57-unit document.
    Every validation error is reported in ONE message - stopping at the first error makes the agent
    re-emit, re-fail, re-emit, and every extra turn re-sends the whole transcript. The remedy the
    message asks for is an EDIT pass over the named task objects: a measured 2026-11-18 drain
    rewrote a whole domain plan (10-30k output tokens) where the fix was a few hundred.
    """
    index = load_index()
    staged = []
    errors = []
    with telemetry.span("blackboard.emit", {"tasks.requested": len(paths)}) as current:
        for raw in paths:
            source = Path(raw)
            try:
                loaded = json.loads(source.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                reason = f"{source}: unreadable JSON: {exc}"
                telemetry.mark_error(current, reason)
                return reason
            batch = loaded if isinstance(loaded, list) else [loaded]
            for position, task in enumerate(batch, start=1):
                # The POINTER is the label: a task id where one exists, else file[entry].
                # The LLM does not have to memorize the contract to heal a plan: the
                # refusal names the exact object and the field, and the remedy is an edit
                # (2026-11-20: the profile stopped restating rules (a)-(z) for this).
                label = (task.get("id") if isinstance(task, dict) and task.get("id")
                         else f"{source.name}[{position}]")
                if not isinstance(task, dict):
                    errors.append(f"{label}: task must be a JSON object")
                    continue
                reason = tasks.validate(task, index, planning=True)
                if reason:
                    errors.append(f"{label}: {reason}")
                    if isinstance(task.get("id"), str) and task["id"] not in index:
                        # Still resolve same-batch dependsOn against it: otherwise every sibling
                        # task gets a cascading "not resolvable" error that hides the real one.
                        index[task["id"]] = task
                    continue
                if task["id"] in index:
                    errors.append(f"{task['id']}: id already exists in queue or complete")
                    continue
                index[task["id"]] = task
                staged.append(task)
        # Cross-task completeness: a unit pinned by anyone as a collaborator must spell
        # the surface its consumers touch - an empty method table there forces two
        # consumers to improvise the same type differently (the seed-002 pair-defect root).
        producers: dict = {}
        for source in list(index.values()) + staged:
            if not isinstance(source, dict):
                continue
            for dep in (source.get("ast_hints") or {}).get("dependencies", []):
                if isinstance(dep, dict) and str(dep.get("task_id", "")).strip():
                    producers.setdefault(str(dep["task_id"]), set()).add(
                        f"{source.get('id')}: {dep.get('type')}")
        for producer_id, consumers in producers.items():
            producer = index.get(producer_id)
            if producer is None:
                errors.append(f"{producer_id}: collaborator pin by "
                              f"{sorted(consumers)[:2]} references no task in the batch, "
                              "queue or complete")
                continue
            if int(producer.get("stage") or 0) not in (1, 2):
                continue
            if not (producer.get("ast_hints") or {}).get("methods"):
                errors.append(
                    f"{producer_id}: pinned as a collaborator by "
                    f"{sorted(consumers)[:3]} but its ast_hints.methods is empty - "
                    "spell the surface (accessors included) every consumer touches")
        # Plan validity across units (seed-002 D1..D3): unowned file duties, config-less
        # runtime plans and request-encoding contradictions die here, at zero sessions.
        errors.extend(tasks.plan_consistency(staged, index))
        errors.extend(_steplog_claim_errors(staged, index))
        errors.extend(_shared_literal_errors(staged, index))
        errors.extend(_security_claim_errors(staged, index))
        _claim_index = dict(index)
        _claim_index.update({str(t.get("id")): t for t in staged if t.get("id")})
        for _slug in sorted({str(t.get("project", "")) for t in staged if t.get("project")}):
            errors.extend(_planning_claim_lines(_slug, [
                record for record in _claim_index.values()
                if isinstance(record, dict) and str(record.get("project", "")) == _slug]))
        errors.extend(_reserved_segment_errors(staged))
        errors.extend(_writable_channel_errors(staged))
        errors.extend(_stage0_family_errors([], index))
        errors.extend(_manifest_order_errors(staged, index))
        if errors:
            reason = "\n".join([_format_error(e) for e in errors] + [
                "Fix EVERY error above by EDITING the named task objects in the draft file that "
                "holds them - never re-emit an unchanged file, never regenerate the whole plan "
                "(one rewrite of a domain plan is 10-30k output tokens; the same fix as an edit is "
                "a few hundred) - then re-emit the same files in ONE command."])
            telemetry.mark_error(current, reason)
            return reason
        for task in staged:
            destination = settings.QUEUE_DIR / tasks.task_file_name(task)
            # One id, one record across the whole board. A QUARANTINED sibling of the same
            # id is a zombie: producers keyed with include_error=True would resolve types
            # to a task that is live in the queue, so its payload would be treated as
            # pending-absent and every consumer would defer forever (seed-002 rerun 13:51
            # left error/T4-001 beside the re-emitted queue record; a relaunch would hang
            # the boot contract behind its own zombie). Re-issuing an id supersedes its old
            # quarantine - the fresh record carries the CURRENT tree truth.
            zombie = next(iter(settings.ERROR_DIR.glob(
                f"{task['id']}-*.json")), None)
            if zombie is not None:
                zombie.unlink()
                print(f"[emit  ] {task['id']}: superseded stale quarantine record "
                      f"error/{zombie.name}")
            with telemetry.span("blackboard.queue", {"file": destination.name,
                                                     **telemetry.task_attributes(task)}):
                destination.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
            print(f"[emit] {task['id']} -> queue/{destination.name}")
        if current is not None:
            current.set_attribute("tasks.emitted", len(staged))
    return None


def _format_error(line):
    """One refusal = one `ERR [pointer]: reason` line. A line naming a task id (as its
    first token or as the subject of a batch rule) or a file[entry] gets that text as its
    pointer; multi-line details keep their follow-up lines verbatim (they carry the fix
    instruction, not a new error)."""
    if line.startswith(("ERR ", "Fix EVERY", "DEFERRED", "LINT-CLEAN")):
        return line
    match = re.match(r"^([^\n:]{1,110}):([\s\S]*)$", line)
    if not match:
        return line
    pointer = match.group(1).strip()
    head = pointer.split(".", 1)[0].split("/", 1)[0]
    if (settings.ID_PATTERN.match(head)
            or re.search(r"\bT\d-\d{3}\b", pointer)
            or pointer.endswith("]") or ".json" in pointer):
        return f"ERR [{pointer}]:{match.group(2)}"
    return line


# ---------------------------------------------------------------------------
# PER-CONTEXT PLANNING (2026-11-20 architect split). The planner agent now runs ONE
# session per bounded context: it drafts exactly one file and lints it. The engine
# owns the rest of the lifecycle it used to leave to the session's memory:
#   claim_draft      - id-collision renumbering after each session (deterministic,
#                      so a mis-numbered context never bills a repair turn)
#   draft_symbol_table - the exported surface of the drafted contexts, the only
#                      lawful pin source for the NEXT context's session
#   emit_draft_batch - the SINGLE batch emit, run in-process after every context:
#                      cross-context pins, provider closure and the claim law each
#                      still see every file, and the price is zero sessions.
DRAFT_DIR = Path("/tmp") / "tasks"


def draft_path(slug, context):
    return DRAFT_DIR / f"{slug}-{ddd.context_stem(context)}.json"


def clear_drafts(slug):
    """A stale draft of a previous (aborted) plan must not join this one's batch."""
    removed = []
    for path in sorted(DRAFT_DIR.glob(f"{slug}-*.json")):
        if path.name.startswith(f"T0-{slug}"):
            continue
        path.unlink(missing_ok=True)
        removed.append(path.name)
    return removed


def draft_world(slug, exclude=None):
    """Ids of everything a session may lawfully pin: queue + complete + the drafted
    context files already claimed for this domain (excluding one path when told)."""
    world = load_index()
    for path in sorted(DRAFT_DIR.glob(f"{slug}-*.json")):
        if path == exclude or path.name.startswith(f"T0-{slug}") \
                or path.name.endswith(".gaps.json"):
            continue
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for task in (loaded if isinstance(loaded, list) else [loaded]):
            if isinstance(task, dict) and task.get("id"):
                world[str(task["id"])] = task
    return world


BUILD_MANIFEST_EXPORT = "build-manifest"


def _stage0_family_errors(staged, world=None):
    """ONE scaffold and ONE build-manifest per domain (2026-11-20 split edge): the
    per-context sessions share a single build file, so a coordinate two contexts each
    notice would be scheduled twice and the container would mutate the same file in two
    stage-0 sessions - last writer wins, first duty silently lost. The families are
    keyed by their export marker (never by path shape, the S16 lesson): a second task
    with the same family export in the same project is refused naming the FIRST one,
    because the lawful remedy is to amend that task (a repair pass may edit it; a
    planning session may not touch another context's draft) - or to read the symbol
    table's `build_manifest` before emitting at all."""
    seen = {}
    for record in list(staged) + list((world or {}).values()):
        if not isinstance(record, dict) or int(record.get("stage") or 0) != 0:
            continue
        export = str(record.get("export", "")).strip()
        if export not in (SCAFFOLD_EXPORT, BUILD_MANIFEST_EXPORT):
            continue
        ids = seen.setdefault((str(record.get("project", "")), export), [])
        tid = str(record.get("id", "?"))
        if tid not in ids:
            ids.append(tid)
    problems = []
    for (project, export), ids in sorted(seen.items()):
        if len(ids) > 1:
            problems.append(
                f"ERR [{', '.join(sorted(ids[1:]))}]: a second '{export}' stage-0 task for "
                f"project '{project}' - the domain ships ONE scaffold and ONE build-manifest "
                f"mutation of the build file (the first is {sorted(ids)[0]}); if its intent "
                "lacks a coordinate you need, report the gap and the repair pass amends the "
                "ONE task - never schedule a twin over the same file")
    return problems


def lint_draft(path):
    """The agent-facing single-file check: `python3 <runner> --lint <draft file>`.

    Strict where one file can be judged alone - schema, per-task contract, dangling
    pins (a forward pin into an undrafted context is unlawful: the pin source is the
    symbol table), reserved segments, the writable channel - and explicitly DEFERRED
    where the batch is the unit of truth - duty claims, step-log ownership, the cross-unit
    literal join, provider closure across contexts. The batch emit after the last context
    is the authority; the repair session carries its refusals.
    """
    source = Path(path)
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"ERR [{source.name}]: unreadable JSON: {exc}"
    batch = loaded if isinstance(loaded, list) else [loaded]
    task = batch[0] if isinstance(loaded, dict) else None
    slug = str((task or {}).get("project") or source.name.split("-", 1)[0])
    world = draft_world(slug, exclude=source)
    index = dict(world)
    staged = []
    errors = []
    reasons = {}
    for position, entry in enumerate(batch, start=1):
        label = (entry.get("id") if isinstance(entry, dict) and entry.get("id")
                 else f"{source.name}[{position}]")
        if not isinstance(entry, dict):
            errors.append(f"{label}: task must be a JSON object")
            continue
        reason = tasks.validate(entry, index, planning=True)
        if reason:
            errors.append(f"{label}: {reason}")
        reasons[label] = reason or ""
        if isinstance(entry.get("id"), str) and entry["id"] not in index:
            index[entry["id"]] = entry
        staged.append(entry)
    # Forward pins are the split's one new temptation: name them exactly, with the
    # lawful alternative (the symbol table, or draft the provider first). A dependsOn
    # the per-task validator already called unresolvable is not reported twice - the
    # extra value here is the FIELD pointer and the pin law, not a second refusal.
    for entry in staged:
        if not isinstance(entry, dict):
            continue
        tid = str(entry.get("id") or "?")
        seen = reasons.get(tid, "")
        refs = [(str(d), "dependsOn") for d in (entry.get("dependsOn") or []) if str(d).strip()]
        for dep in (entry.get("ast_hints") or {}).get("dependencies", []) if isinstance(
                entry.get("ast_hints"), dict) else []:
            if isinstance(dep, dict) and str(dep.get("task_id", "")).strip():
                refs.append((str(dep["task_id"]), "ast_hints.dependencies"))
        for ref, field in refs:
            if ref not in index:
                if field == "dependsOn" and f"dependsOn {ref}" in seen:
                    continue
                errors.append(
                    f"{tid}.{field}/{ref}: references no task in the queue, the drafted "
                    "contexts, or this file - a context not yet drafted cannot be pinned; "
                    "pin only through the symbol table, or let the provider context's units "
                    "depend on yours")
    errors.extend(_reserved_segment_errors(staged))
    errors.extend(_writable_channel_errors(staged))
    errors.extend(_stage0_family_errors(staged, world))
    errors.extend(_manifest_order_errors(staged, world))
    if errors:
        return "\n".join([_format_error(e) for e in errors])
    return ("LINT-CLEAN (batch laws DEFERRED to the engine's single --emit after the last "
            "context: duty-claim coverage, step-log ownership, the shared-literal join, "
            "provider closure).")


def claim_draft(slug, context):
    """Engine step after one planning session: the draft file joins the domain's id space.

    An id that collides with the queue, complete, or an already-drafted context is
    RENUMBERED here deterministically (the references inside the same file follow), so a
    session that miscounted never burns a repair turn on arithmetic the machine can do.
    Returns (problems, renames): problems are what the session still owns (malformed JSON,
    dangling pins); renames are reported for the symbol table's sake."""
    path = draft_path(slug, context)
    if not path.is_file():
        return [f"draft file missing: {path}"], {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path.name}: unreadable JSON: {exc}"], {}
    batch = loaded if isinstance(loaded, list) else [loaded]
    if not batch or not all(isinstance(task, dict) for task in batch):
        return [f"{path.name}: must be a JSON array of task objects"], {}
    world = draft_world(slug, exclude=path)
    problems, renames = [], {}
    counters = {}
    originals = []  # (task, old id) recorded BEFORE any rename - the reference pass needs both spaces
    for task in batch:
        stage_match = settings.ID_PATTERN.match(str(task.get("id", "")))
        if not stage_match:
            problems.append(f"ERR [{path.name}]: task without a valid id")
            continue
        stage = int(stage_match.group(1))
        old = task["id"]
        originals.append((task, old))
        if old in world:
            numbers = [int(m.group(2)) for tid in world
                       if (m := settings.ID_PATTERN.match(tid)) and int(m.group(1)) == stage]
            numbers += [int(m.group(2)) for m in (
                settings.ID_PATTERN.match(str(t.get("id", ""))) for t in batch)
                if m and int(m.group(1)) == stage]
            counters.setdefault(stage, max(numbers) + 1)
            new_id = f"T{stage}-{counters[stage]:03d}"
            counters[stage] += 1
            renames[old] = new_id
            task["id"] = new_id
    if renames:
        own_export = {old: str(task.get("export") or "") for task, old in originals
                      if old in renames}
        for task, _old in originals:
            task["dependsOn"] = [renames.get(str(dep), str(dep)) for dep in task["dependsOn"]]
            hints = task.get("ast_hints")
            if isinstance(hints, dict):
                for dep in hints.get("dependencies", []):
                    if not (isinstance(dep, dict) and str(dep.get("task_id", "")) in renames):
                        continue
                    ref = str(dep["task_id"])
                    # A pinned type is attributed by its NAME first: a reference whose type
                    # matches an OWN renamed unit follows the rename; one whose type belongs
                    # to the drafted world (the valid backward pin through the symbol table)
                    # keeps the world id. Only a reference no world task answers stays self.
                    if str(dep.get("type") or "") == own_export.get(ref) or ref not in world:
                        dep["task_id"] = renames[ref]
        path.write_text(json.dumps(batch, indent=1), encoding="utf-8")
    ids_here = {str(task.get("id")) for task in batch if isinstance(task, dict)}
    for task in batch:
        if not isinstance(task, dict):
            continue
        for ref in [str(d) for d in (task.get("dependsOn") or [])]:
            if ref not in world and ref not in ids_here:
                problems.append(f"ERR [{task.get('id')}].dependsOn: dangling reference {ref} "
                                "- not in the queue, the drafted contexts, or this file")
    return problems, renames


def draft_symbol_table(slug, contexts, path):
    """The pin source for the NEXT context's session: every exported unit of the
    already-drafted contexts, plus the next-free ids. Small by construction - ids,
    signatures, and the shared-literal tables (meters/routes/config), never prose.

    The table-pair fold (2026-11-20 context audit: 46K symbols file for one provider
    context, because 57 drafted units meant 57 COPIES of 23 tables): the T1/T2 pair
    carries the IDENTICAL ast_hints by law (z4), so a non-stage-2 unit whose table
    equals its same-suffix stage-2 task's is listed as a POINTER ("table_of"), and the
    tables themselves become lists of strings, not objects. A session still resolves
    every id, export, signature, owned meter, served route and config path it may pin."""
    units, drafted = [], []
    build_manifest, scaffolds = [], []
    drafted_tasks = []
    for context in contexts:
        draft = draft_path(slug, context)
        if not draft.is_file():
            continue
        try:
            loaded = json.loads(draft.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        drafted.append(context)
        for task in (loaded if isinstance(loaded, list) else [loaded]):
            if not isinstance(task, dict):
                continue
            if int(task.get("stage") or 0) == 0:
                export = str(task.get("export", "")).strip()
                if export == BUILD_MANIFEST_EXPORT:
                    build_manifest.append({"id": task.get("id"), "path": task.get("path"),
                                           "intent": task.get("intent")})
                elif export == SCAFFOLD_EXPORT:
                    scaffolds.append(str(task.get("id")))
                # stage-0 tasks join the families above, never the unit list: a
                # drafted scaffold/manifest is not a collaborator pin - it is the
                # duplication risk the two fields exist to kill.
                continue
            drafted_tasks.append((context, task))
    t2_tables = {}
    for _context, task in drafted_tasks:
        if int(task.get("stage") or 0) == 2:
            suffix = str(task.get("id", "")).rsplit("-", 1)[-1]
            t2_tables[suffix] = json.dumps(task.get("ast_hints"), sort_keys=True)
    for context, task in drafted_tasks:
        suffix = str(task.get("id", "")).rsplit("-", 1)[-1]
        hints = task.get("ast_hints") if isinstance(task.get("ast_hints"), dict) else {}
        if int(task.get("stage") or 0) != 2 and t2_tables.get(suffix) == \
                json.dumps(task.get("ast_hints"), sort_keys=True):
            units.append({"id": task.get("id"), "stage": task.get("stage"),
                          "context": context, "export": task.get("export"),
                          "path": task.get("path"), "table_of": f"T2-{suffix}"})
            continue
        units.append({
            "id": task.get("id"),
            "stage": task.get("stage"),
            "context": context,
            "export": task.get("export"),
            "path": task.get("path"),
            "layer": task.get("layer"),
            "package": hints.get("package"),
            "methods": [str(m.get("signature") or "")
                        for m in (hints.get("methods") or []) if isinstance(m, dict)],
            "meters": [str(m.get("name")) for m in (hints.get("meters") or [])
                       if isinstance(m, dict) and m.get("duty") == "owns"],
            "routes": [f"{r.get('method', '')} {r.get('path', '')}".strip()
                       for r in (hints.get("routes") or [])
                       if isinstance(r, dict) and r.get("duty") == "serves"],
            "config": [str(c.get("path")) for c in (hints.get("config") or [])
                       if isinstance(c, dict)],
        })
    stages = {}
    world = draft_world(slug)
    for stage in (1, 2, 3):
        numbers = [int(m.group(2)) for tid in world
                   if (m := settings.ID_PATTERN.match(tid)) and int(m.group(1)) == stage]
        numbers += [int(m.group(2)) for m in (
            settings.ID_PATTERN.match(str(unit["id"])) for unit in units)
            if m and int(m.group(1)) == stage]
        stages[f"T{stage}"] = f"T{stage}-{(max(numbers) + 1 if numbers else 1):03d}"
    payload = {"slug": slug, "drafted_contexts": drafted, "next_free": stages,
               "scaffold": scaffolds, "build_manifest": build_manifest, "units": units}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    except OSError as exc:
        return None, [f"symbol table write failed: {exc}"]
    return path, []


def draft_is_fresh(slug, context):
    """Resume economics (2026-11-20 live): a draft that an aborted session left behind is
    that session's RESULT - kept when it is newer than every input the plan was drafted
    from (the strategy and the specs on disk). Re-spawning a session to re-produce a
    clean, current draft would bill the whole cost again for bytes already on disk.
    Fresh = parses as a non-empty array of task objects AND its mtime is not older than
    any plan input."""
    path = draft_path(slug, context)
    if not path.is_file():
        return False
    try:
        batch = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not (isinstance(batch, list) and batch and all(isinstance(t, dict) for t in batch)):
        return False
    inputs = [ddd.strategy_path(slug)] + \
        [settings.COMPLETE_DIR / f"{prefix}{slug}.json"
         for prefix in ("security-spec-", "performance-spec-", "ai-spec-")]
    # the CONTRACT file: a rewritten task-decomposition-dag SKILL.md (normative law)
    # older-dates every draft written under the previous one - resume then re-plans, and
    # a draft that predates a law fix never survives into the batch (2026-11-20: the
    # killed session's draft was lint-clean AND stage-3-less under the OLD skill lie).
    # The QUICKREF is deliberately NOT an input: it is the derivative MAP (the profile's
    # own hierarchy), and mtime-gating a map rewrite would re-bill a provably compliant
    # draft for wording edits - map drift is caught by the batch laws (lint/emit), the
    # same guarantee that let the (a)-(z) wall leave the profiles: the gate is the law.
    inputs.append(Path(__file__).resolve().parents[1]
                  / ".opencode/skills/architect-practices/task-decomposition-dag/SKILL.md")
    stamps = [f.stat().st_mtime for f in inputs if f.is_file()]
    return bool(stamps) and path.stat().st_mtime >= max(stamps)


def gaps_path(slug, context):
    """The structured gap channel of ONE planning session: the brief names this exact
    path; the session writes only what it may not schedule itself (a coordinate the ONE
    build-manifest task lacks). The engine consumes it BEFORE the batch emit - prose in
    a session transcript is not a hand-off, a validated file is (the board's own law)."""
    return DRAFT_DIR / f"{slug}-{ddd.context_stem(context)}.gaps.json"


def _read_gaps(slug, contexts):
    """Coordinates reported by the drafted contexts, deduped in first-seen order."""
    coordinates, problems = [], []
    for context in contexts:
        gp = gaps_path(slug, context)
        if not gp.is_file():
            continue
        try:
            payload = json.loads(gp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"ERR [{gp.name}]: unreadable gaps file: {exc}")
            continue
        entries = payload if isinstance(payload, list) else \
            ((payload or {}).get("missing_coordinates") or [])
        for entry in (entries if isinstance(entries, list) else []):
            coordinate = str(entry).strip()
            if coordinate and coordinate not in coordinates:
                coordinates.append(coordinate)
    return coordinates, problems


def apply_coordinate_gaps(slug, contexts):
    """X11 (2026-11-20 operator catch): the split's 'report the gap' branch is only honest
    if the report lands somewhere the machine reads. Context B may NOT duplicate or edit
    context A's build-manifest task - so B writes its missing coordinates into its gaps
    file, and THIS step appends them verbatim to the ONE task's intent, idempotently
    (a coordinate the intent already carries is skipped), before the batch emit. A reported
    gap with no build-manifest task to amend is a plan defect at claim grade: the bounded
    repair session schedules the ONE task; the engine never authors planning intent."""
    coordinates, problems = _read_gaps(slug, contexts)
    notes = []
    if not coordinates:
        return problems, notes
    for context in contexts:
        path = draft_path(slug, context)
        if not path.is_file():
            continue
        try:
            batch = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for task in (batch if isinstance(batch, list) else [batch]):
            if not isinstance(task, dict) or int(task.get("stage") or 0) != 0 \
                    or str(task.get("export", "")).strip() != BUILD_MANIFEST_EXPORT:
                continue
            intent = str(task.get("intent") or "")
            missing = [c for c in coordinates if c not in intent]
            if missing:
                task["intent"] = intent.rstrip() + "; also add " + ", ".join(missing)
                path.write_text(json.dumps(batch, indent=1), encoding="utf-8")
                notes.append(f"coordinate(s) {', '.join(missing)} appended to {task.get('id')} "
                             f"({path.name}) - the ONE build-manifest task")
            else:
                notes.append(f"{task.get('id')} already carries every reported coordinate")
            return problems, notes
    problems.append(
        f"ERR [gaps/{slug}]: {len(coordinates)} build coordinate(s) reported missing "
        f"({', '.join(coordinates[:4])}) but the domain schedules NO build-manifest task - "
        "the ONE lawful stage-0 manifest bootstrap task must be scheduled (repair pass: add "
        "it to the drafting context's file with the reported coordinates; never one per context)")
    return problems, notes


def emit_draft_batch(slug, contexts):
    """The ONE batch emit, run by the ENGINE after every context file is drafted:
    cross-context pins, provider closure and the claim law each see every file (the law
    F1 kept), at zero sessions. Returns the emit_tasks reason (None on success)."""
    paths = [draft_path(slug, context) for context in contexts]
    return emit_tasks([str(p) for p in paths if p.is_file()])


class ScaffoldUnresolved(RuntimeError):
    """A queued task depends on a stage-0 task that sits QUARANTINED in error/.

    The scaffold is the root of the whole domain: every tester/coder/evaluator dangles
    behind it, and letting the per-file quarantine loop scatter that fact produced 124
    error records for ONE failed container session. Fail fast with the scaffold's own
    reason instead - it is the only line an operator needs.
    """


def _quarantined_scaffold_reasons():
    reasons = {}
    for file in settings.ERROR_DIR.glob("T0-*.json"):
        try:
            record = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, dict) and record.get("id"):
            reasons[str(record["id"])] = str(record.get("error", ""))[:300]
    return reasons


def load_valid_tasks():
    """Read the queue and quarantine bad files until the remaining set is stable."""
    dead_scaffolds = _quarantined_scaffold_reasons()
    if dead_scaffolds:
        for _, _, task, _ in read_queue():
            if not isinstance(task, dict):
                continue
            deps = task.get("dependsOn")
            for dep in (deps if isinstance(deps, list) else []):
                if str(dep) in dead_scaffolds:
                    raise ScaffoldUnresolved(
                        f"stage-0 scaffold {dep} of '{task.get('project', '?')}' is quarantined: "
                        f"{dead_scaffolds[str(dep)]} - every unit of that domain dangles behind it; "
                        "fix the container stage (skill/environment) and relaunch with --retry")
    while True:
        entries = read_queue()
        if not entries:
            return [], complete_task_ids()
        dirty = False
        found = []
        for _, file, task, reason in entries:
            if reason:
                send_to_error(file, reason, task)
                print(f"[error] {file.name}: {reason}")
                dirty = True
            else:
                found.append((file, task))
        if dirty:
            continue
        index = load_index()
        kept = []
        for file, task in found:
            reason = tasks.validate(task, index)
            if reason:
                send_to_error(file, reason, task)
                print(f"[error] {file.name}: {reason}")
                dirty = True
            else:
                kept.append((file, task))
        if dirty:
            continue
        return kept, complete_task_ids()
