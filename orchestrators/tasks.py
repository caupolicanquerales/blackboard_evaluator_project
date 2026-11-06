"""Blackboard task schema: validation and ordering keys (pure, no I/O state)."""
import re
from pathlib import Path

import settings
import workspace


CAMEL_TYPE_RE = re.compile(r"\b[A-Z][A-Za-z0-9]{2,}\b")


def is_type_shape(name):
    """A Java type is CamelCase; an ALL-CAPS token in an intent is a constant or a unit (BPM, RPM)."""
    return bool(name) and not name.isupper()


def exported_product(task):
    """The single type a stage-2 task actually writes: its export, simple name.

    Scheduling truth: a task writes ONE file (its `path`). The names its `intent`
    mentions are NOT producers — treating them as such hid real decomposition gaps
    and livelocked the whole domain behind symbols nobody ever writes.
    """
    export = task.get("export")
    if isinstance(export, str) and export.strip():
        return export.strip().split(".")[-1]
    return None


def produced_types(task):
    """Types a task's text NAMES (export + CamelCase words of the intent).

    Advisory only (unit briefs). Never use this to decide that a type has a producer:
    use exported_product — a task creates exactly one file.
    """
    names = set()
    export = task.get("export")
    if isinstance(export, str) and export.strip():
        names.add(export.strip().split(".")[-1])
    names.update(name for name in CAMEL_TYPE_RE.findall(str(task.get("intent", "")))
                 if is_type_shape(name))
    return names


def task_sort_key(task):
    return (task["stage"], task["project"], task["path"])


def task_file_name(task):
    """File name for a queued task: <id>-<domain>.json."""
    return f"{task['id']}-{task['project']}.json"


def depends_transitively(start, target, index, seen=None):
    """True if `start` (directly or indirectly) depends on `target`."""
    seen = set() if seen is None else seen
    if start == target:
        return True
    if start in seen:
        return False
    seen.add(start)
    node = index.get(start)
    if not node or not isinstance(node.get("dependsOn"), list):
        return False
    return any(depends_transitively(dep, target, index, seen) for dep in node["dependsOn"])


def validate(task, index):
    """Validate one blackboard task against the evaluator pipeline schema.

    Returns a reason string, or None when the task is valid.
    """
    if set(task) != set(settings.REQUIRED_KEYS):
        missing = sorted(set(settings.REQUIRED_KEYS) - set(task))
        extra = sorted(set(task) - set(settings.REQUIRED_KEYS))
        return f"schema mismatch, missing={missing} extra={extra}"
    stage = task["stage"]
    if not isinstance(stage, int) or stage not in settings.STAGE_AGENTS:
        return f"stage must be one of {sorted(settings.STAGE_AGENTS)}"
    match = settings.ID_PATTERN.match(str(task["id"]))
    if not match:
        return f"id must match {settings.ID_PATTERN.pattern}"
    if int(match.group(1)) != stage:
        return "id stage suffix differs from stage"
    if task["targetAgent"] != settings.STAGE_AGENTS[stage]:
        return f"targetAgent must be {settings.STAGE_AGENTS[stage]!r} for stage {stage}"
    if task["kind"] not in settings.STAGE_KINDS[stage]:
        return f"kind must be one of {list(settings.STAGE_KINDS[stage])} for stage {stage}"
    if not isinstance(task["path"], str) or not task["path"].strip():
        return "path must be a non-empty string"
    if not isinstance(task["export"], str) or not task["export"].strip():
        return "export must be a non-empty string"
    if not isinstance(task["intent"], str) or not task["intent"].strip():
        return "intent must be a non-empty string"
    if (not isinstance(task["project"], str) or not task["project"].strip()
            or task["project"] != workspace.slugify(task["project"])):
        return "project must be a domain slug"

    if stage == 0:
        if task["layer"] != "root":
            return "stage 0 layer must be root"
        if task["feature"] is not None:
            return "stage 0 feature must be null"
        if task["dependsOn"] and "migrations" not in Path(str(task["path"])).parts:
            return "stage 0 dependsOn must be empty except for database tasks"
        return None

    if task["layer"] not in settings.LAYERS:
        return f"layer must be one of {list(settings.LAYERS)}"
    has_feature = isinstance(task["feature"], str) and bool(task["feature"])
    if task["layer"] == "features" and not has_feature:
        return "feature required when layer is features"
    if task["layer"] != "features" and has_feature:
        return "feature must be null unless layer is features"
    if not isinstance(task["dependsOn"], list):
        return "dependsOn must be a list"

    for dep in task["dependsOn"]:
        if not isinstance(dep, str) or not settings.ID_PATTERN.match(dep):
            return f"dependsOn id invalid: {dep!r}"
        dep_task = index.get(dep)
        if (dep_task is None or not isinstance(dep_task.get("stage"), int)
                or not isinstance(dep_task.get("path"), str)):
            return f"dependsOn {dep} not resolvable in queue or complete"
        if dep_task["stage"] > stage:
            return f"dependsOn {dep} is in a later stage than this task"
        if depends_transitively(dep, task["id"], index):
            return f"dependsOn {dep} creates a dependency cycle"
    return None
