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


def load_index():
    index = {}
    for folder in (settings.QUEUE_DIR, settings.COMPLETE_DIR):
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
        file.unlink()


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
                reason = tasks.validate(task, index)
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
        if errors:
            reason = "\n".join(errors + [
                "Fix EVERY error above with one rewrite of the draft file, then re-emit once."])
            telemetry.mark_error(current, reason)
            return reason
        for task in staged:
            destination = settings.QUEUE_DIR / tasks.task_file_name(task)
            with telemetry.span("blackboard.queue", {"file": destination.name,
                                                     **telemetry.task_attributes(task)}):
                destination.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
            print(f"[emit] {task['id']} -> queue/{destination.name}")
        if current is not None:
            current.set_attribute("tasks.emitted", len(staged))
    return None


def load_valid_tasks():
    """Read the queue and quarantine bad files until the remaining set is stable."""
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
