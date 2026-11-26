"""plan_board - queue-record layer: the blackboard's index, ids, quarantine,
retry, stage-0 (scaffold/manifest) discovery and recovery, replan, symbol table,
and the drafting "world" (queue + claimed drafts) every law joins against."""

import json
import re
import shutil
from pathlib import Path
import settings
import ddd
import tasks
import telemetry
from plan_drafts import DRAFT_DIR, draft_path


SCAFFOLD_EXPORT = settings.SCAFFOLD_EXPORT
BUILD_MANIFEST_EXPORT = settings.BUILD_MANIFEST_EXPORT


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
        if not task.get("dependsOn") and not tasks.is_database_task(task) \
                and str(task.get("export", "")).strip() != BUILD_MANIFEST_EXPORT:
            dependency_free.append(task_id)
    return dependency_free[0] if dependency_free else "T0-000"


def recover_lost_scaffold(slug):
    """Heal a manifest-without-scaffold stage-0 board from the phase-1 draft, zero sessions
    (2026-11-26: the manifest prepass had an id-collision bug - it built its `used` set
    from raw numbers while comparing full ids, never advanced past T0-001, and OVERWROTE
    the strategy's scaffold task with the manifest record. A board whose manifest is on
    disk, whose scaffold marker is gone, and whose scaffold draft the phase-1 session
    emitted is exactly that damage). The draft is the agent's own record, restored with a
    direct renumbered queue write and the manifest re-pointed behind it; a board this
    cannot heal returns None and the gap gate re-runs phase 1 as always - recovery never
    guesses."""
    manifest = ddd.build_manifest_state(slug)
    if not manifest or not manifest.get("id"):
        return None  # no manifest yet: the prepass will queue behind the existing scaffold
    for folder in (settings.QUEUE_DIR, settings.COMPLETE_DIR, settings.ERROR_DIR):
        for file in folder.glob(f"T0-*-{slug}.json"):
            try:
                task = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (isinstance(task, dict) and str(task.get("project", "")) == slug
                    and str(task.get("export", "")).strip() == SCAFFOLD_EXPORT):
                return None  # board intact
    draft = DRAFT_DIR / f"T0-{slug}.json"
    if not draft.is_file():
        return None
    try:
        record = json.loads(draft.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict) or not record.get("id") \
            or str(record.get("export", "")).strip() != SCAFFOLD_EXPORT:
        return None
    # Stage-0 identity is the export marker; the record is a simple bootstrap row, so it
    # is restored with a direct queue write (the same shape the manifest prepass uses),
    # NOT through emit_tasks: the board is mid-repair here and a scaffold-only emit would
    # run whole-plan joins that have no other stage-1..3 task to join against yet.
    used = {f"T0-{f.name.split('-')[1]}" for folder in
            (settings.QUEUE_DIR, settings.COMPLETE_DIR, settings.ERROR_DIR)
            for f in folder.glob(f"T0-*-{slug}.json")}
    number = 1
    while f"T0-{number:03d}" in used:
        number += 1
    tid = f"T0-{number:03d}"
    record["id"] = tid
    record["project"] = slug
    record["export"] = SCAFFOLD_EXPORT
    record["dependsOn"] = []
    destination = settings.QUEUE_DIR / f"{tid}-{slug}.json"
    if destination.is_file():
        return None
    destination.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    manifest_file = None
    for folder in (settings.QUEUE_DIR, settings.COMPLETE_DIR, settings.ERROR_DIR):
        candidate = next((f for f in folder.glob(f"{manifest['id']}-{slug}.json") if f.is_file()), None)
        if candidate:
            manifest_file = candidate
            break
    if manifest_file is not None:
        mrec = json.loads(manifest_file.read_text(encoding="utf-8"))
        if tid not in (mrec.get("dependsOn") or []):
            mrec["dependsOn"] = sorted({*(mrec.get("dependsOn") or []), tid})
            manifest_file.write_text(json.dumps(mrec, indent=2) + "\n", encoding="utf-8")
    return tid


def database_task_ids(slug):
    """Ids of the database tasks already queued or complete for one domain project.

    Used to keep the database phase idempotent: re-running it would emit duplicates.
    """
    found = []
    board = load_index()
    for task_id, task in sorted(board.items()):
        if (task.get("project") == slug and task_id.startswith("T0-")
                and tasks.is_database_task(task, board)):
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


def draft_world(slug, exclude=None):
    """Ids of everything a session may lawfully pin: queue + complete + the drafted
    context files already claimed for this domain (excluding one path when told)."""
    world = load_index()
    for path in sorted(DRAFT_DIR.glob(f"{slug}-*.json")):
        if path == exclude or path.name.startswith(f"T0-{slug}") \
                or path.name.endswith((".gaps.json", DB_TASKS_SUFFIX)):
            continue
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for task in (loaded if isinstance(loaded, list) else [loaded]):
            if isinstance(task, dict) and task.get("id"):
                world[str(task["id"])] = task
    return world


BUILD_MANIFEST_EXPORT = settings.BUILD_MANIFEST_EXPORT
DB_TASKS_SUFFIX = "-db-tasks.json"  # the database architect's CHANNEL file (the database


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
            # 2026-11-25 hydration facts the NEXT context must be able to reference:
            # which floor strings this unit already claims, and whether a root gate
            # exists (a later context pins it - never marks a second one)
            "steps": [str(s) for s in
                      ((task.get("observability") or {}).get("step_logs") or [])
                      if isinstance(s, str)],
            **({"root_gate": True} if task.get("root_gate") else {}),
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


# ---------------------------------------------------------------------------
# THE TASK-CREATION CONTRACT (2026-11-26): three axes, one state machine.
#
#   FACT   - strategy + specs. Hashed into the sidecar. A draft whose FACTS moved
#            is invalid BY NATURE: only a session can produce units for a plan
#            that changed -> re-draft (billed).
#   LAW    - the enforcement code in THIS module and tasks.py. LAW_VERSION below is
#            its explicit fingerprint. A law change re-VALIDATES drafts for free
#            (claim re-runs the checks; the batch stays the authority) and only
#            escalates to repair/re-draft when the new law ACTUALLY refuses the
#            bytes. SKILL.md is NOT hashed and never was law: prose edit cost, real
#            law change was free - inverted; that coupling re-billed whole planning
#            passes on documentation days (live 2026-11-26, twice) and hid nothing
#            when the checks themselves changed. Bump LAW_VERSION whenever a law
#            check's VERDICTS change (new refusal, removed refusal, tier move);
#            never for wording, comments, or skill prose.
#   VERDICT- claim records what the gate concluded about THESE bytes (clean /
#            rejected / broken) plus re-draft attempts. The ladder:
#            unjudged -> claim -> (refused) bounded repair -> (exhausted) rejected
#            -> one re-draft -> ... -> MAX_REDRAFTS -> loud operator stop. Every rung
#            is bounded; the queue can no longer replay a refusal storm across
#            launches, and no relaunch can launder a rejected draft as fresh.
# ---------------------------------------------------------------------------


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
