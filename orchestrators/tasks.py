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
        name = export.strip()
        open_generic = name.find("<")  # an export may declare its type parameters; the product is the bare head name
        if open_generic > 0:
            name = name[:open_generic]
        return name.split(".")[-1]
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


def validate_ast_hints(hints):
    """Structural shape of the API contract table. No language grammar: the entries are
    names and the language's own declaration text, treated as opaque strings."""
    if not isinstance(hints, dict) or set(hints) != set(settings.AST_HINT_KEYS):
        return f"ast_hints keys must be exactly {list(settings.AST_HINT_KEYS)}"
    if not (isinstance(hints["package"], str) and hints["package"].strip()):
        return "ast_hints.package must be a non-empty string"
    if not isinstance(hints["implements"], list) \
            or not all(isinstance(s, str) and s.strip() for s in hints["implements"]):
        return "ast_hints.implements must be a list of non-empty strings"
    if not isinstance(hints["dependencies"], list):
        return "ast_hints.dependencies must be a list of {type, task_id} objects"
    for dep in hints["dependencies"]:
        if not (isinstance(dep, dict) and set(dep) == {"type", "task_id"}
                and isinstance(dep["type"], str) and dep["type"].strip()
                and isinstance(dep["task_id"], str) and dep["task_id"].strip()):
            return "each ast_hints.dependencies entry must be {type, task_id}, both non-empty strings"
    if not isinstance(hints["methods"], list):
        return "ast_hints.methods must be a list of {signature, returns} objects"
    for method in hints["methods"]:
        if not (isinstance(method, dict) and set(method) == {"signature", "returns"}
                and isinstance(method["signature"], str) and method["signature"].strip()
                and isinstance(method["returns"], str)):
            return "each ast_hints.methods entry must be {signature, returns} (returns '' for none)"
    return None


def validate(task, index, planning=False):
    """Validate one blackboard task against the evaluator pipeline schema.

    planning=True (task emission) additionally demands the API contract table for
    stages 1-2: those freeze the unit's public surface, and a tester left without the
    table improvises signatures from prose - which froze two contradictory contracts
    against each other in seed 002 and deadlocked the whole domain behind them.
    Resume validation (planning=False) only shape-checks: older boards stay readable.

    Returns a reason string, or None when the task is valid.
    """
    allowed = set(settings.REQUIRED_KEYS) | set(settings.OPTIONAL_KEYS)
    if not set(task) <= allowed or set(settings.REQUIRED_KEYS) - set(task):
        missing = sorted(set(settings.REQUIRED_KEYS) - set(task))
        extra = sorted(set(task) - allowed)
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
    if "ast_hints" in task:
        reason = validate_ast_hints(task["ast_hints"])
        if reason:
            return reason
        hints = task["ast_hints"]
        if hints["implements"] and not hints["methods"]:
            return ("ast_hints.methods must spell the surface of every implemented "
                    "supertype (implements is non-empty but methods is empty)")
    if planning and stage in (1, 2):
        if "ast_hints" not in task:
            return ("stage 1-2 tasks carry ast_hints: the API contract table "
                    "(package, implements, dependencies, methods) the tester and coder "
                    "must not improvise")
    return None
