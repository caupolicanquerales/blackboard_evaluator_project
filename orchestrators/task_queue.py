"""Blackboard queue files: reading, indexing, emitting, and quarantining tasks."""
import json
from pathlib import Path

import settings
import tasks
import telemetry


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

    Database tasks of the domain depend on it, so they cannot run before the
    domain project exists.
    """
    for task_id, task in sorted(load_index().items()):
        if (settings.ID_PATTERN.match(task_id) and task_id.startswith("T0-")
                and task.get("kind") == "bootstrap" and not task.get("dependsOn")
                and task.get("project") == slug
                and "migrations" not in str(task.get("path", "")).split("/")):
            return task_id
    return "T0-000"


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
        entries = obs.get("step_logs") or []
        wanted = {}
        for entry in entries if isinstance(entries, list) else []:
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

    A path may hold one task object or an array of them: the architect drafts its whole
    decomposition in a single file, which keeps its session at two tool calls instead of
    one create per task. Every validation error is reported in ONE message: the agent
    fixes the draft in one rewrite. Stopping at the first error makes the agent edit,
    re-emit, edit again: every extra turn re-sends the whole transcript.
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
                label = f"{source}" if isinstance(loaded, dict) else f"{source}[{position}]"
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
                errors.append(f"collaborator pin {producer_id} (by {sorted(consumers)[:2]}) "
                              "references no task in the batch, queue or complete")
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
        errors.extend(_reserved_segment_errors(staged))
        if errors:
            reason = "\n".join(errors + [
                "Fix EVERY error above with one rewrite of the draft file, then re-emit once."])
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
