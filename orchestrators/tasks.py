"""Blackboard task schema: validation and ordering keys (pure, no I/O state)."""
import re
from pathlib import Path

import settings
import workspace


CAMEL_TYPE_RE = re.compile(r"\b[A-Z][A-Za-z0-9]{2,}\b")

# Plan validity (FINAL-EVALUATION-seed002 §5.1, D1/D2/D3 roots): duties without an
# owning artifact, config-less runtime plans and request-encoding contradictions are
# dead on arrival at the frozen-test gate, so the EMIT refuses them - zero agent
# sessions spent. The tables are STACK-NEUTRAL: they match artifact tails and generic
# type shapes, never a framework name; framework vocabulary lives in the skills.
FILE_ARTIFACT_RE = re.compile(
    r"\b[\w./-]*\w\.(?:ya?ml|properties|sql|json|xml|conf|ini|toml|env)\b", re.I)
CONFIG_ARTIFACT_TAILS = ("application.yml", "application.yaml", "application.properties",
                         "settings.py", "config.py", "config.ts", "config.js",
                         "config.json", "config.yaml", ".env")
CONFIG_TRIGGER_RE = re.compile(
    r"@ConfigurationProperties|application\.(?:ya?ml|properties)|externalized[- ]config", re.I)
NULL_REJECT_RE = re.compile(
    r"rejects?[^.;]*\bnull\b|null[- ]?(?:reject|intoler)|\bnon-null\b", re.I)
STREAM_REQUEST_TYPES = ("Flux<", "Observable<", "ReadableStream", "AsyncGenerator",
                        "AsyncIterable", "stream of")
ARRAY_REQUEST_TYPES = ("List<", "Set<", "Collection<", "Iterable<")
ARRAY_BODY_RE = re.compile(r"JSON array|array of\b|single array|array body|array document", re.I)
STREAM_BODY_RE = re.compile(r"streamed (?:JSON )?documents|line[- ]delimited|ndjson|"
                            r"newline[- ]delimited|sequence of (?:JSON )?documents|stream body", re.I)

# Prose-vs-table shape (seed-002 rerun F2: the T2-014 pair that froze T2-020 and the
# whole deferred cluster behind it). Two deterministic contradiction classes are emit-
# refused because NO payload can ever satisfy both sides of the pair:
#   (1) an intent asserting an UNCONSTRUCTIBLE shape (private constructor / utility
#       class / non-instantiable) while its own table binds INSTANCE members;
#   (2) an intent calling a pinned producer's member in STATIC form (`Type.member(`)
#       while that producer's table binds it as an instance member.
# Both are pure text comparisons of the task records - stack-neutral by construction;
# yesterday's rules made the table win at WRITE time, this refuses the contradiction at
# PLAN time so the two frozen tests of one type can never be written in two shapes again.
UNCONSTRUCTIBLE_RE = re.compile(
    r"private\s+(?:final\s+)?constructor|utility\s+class|non[-\s]instantiable", re.I)
STATIC_CALL_RE = re.compile(r"\b([A-Z][A-Za-z0-9]{2,})\.([a-z][A-Za-z0-9]*)\(")


def _table_signatures(hints):
    for method in (hints or {}).get("methods") or []:
        yield str(method.get("signature", "")) if isinstance(method, dict) else str(method)


def _member_name(signature):
    """The called name of a table signature: 'String headerName()' -> 'headerName';
    'Foo(Bar b)' -> 'Foo' (constructor shape). Grammar-free: split before '(', last token."""
    head = signature.split("(")[0].strip()
    return head.rsplit(" ", 1)[-1] if head else ""


def _is_static(signature):
    return "static" in signature.split("(")[0].split()


def _instance_members(hints, product):
    """Non-constructor, non-static members the table binds as instance."""
    names = []
    for signature in _table_signatures(hints):
        if "(" not in signature:
            continue
        name = _member_name(signature)
        if name and name != product and not _is_static(signature):
            names.append(name)
    return names


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
        return "ast_hints.methods must be a list of {signature, returns[, semantics]} objects"
    for method in hints["methods"]:
        if not (isinstance(method, dict)
                and {"signature", "returns"} <= set(method) <= {"signature", "returns", "semantics"}
                and isinstance(method["signature"], str) and method["signature"].strip()
                and isinstance(method["returns"], str)
                and all(isinstance(v, str) and v.strip()
                        for k, v in method.items() if k == "semantics")):
            return ("each ast_hints.methods entry must be {signature, returns} plus optional "
                    "non-empty `semantics` (returns '' for none)")
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
    if "observability" in task:
        obs = task["observability"]
        if (not isinstance(obs, dict) or set(obs) != {"step_logs"}
                or not isinstance(obs["step_logs"], list) or not obs["step_logs"]
                or not all(isinstance(s, str) and s.strip() for s in obs["step_logs"])):
            return ('observability must be exactly {"step_logs": [non-empty strings]}: the '
                    "verbatim execution-strategy entries this unit owns and its stage-1 "
                    "test must assert (the claim is the machine surface, never prose)")
    if planning and stage in (1, 2):
        if "ast_hints" not in task:
            return ("stage 1-2 tasks carry ast_hints: the API contract table "
                    "(package, implements, dependencies, methods) the tester and coder "
                    "must not improvise")
        if NULL_REJECT_RE.search(str(task["intent"])):
            methods = (task["ast_hints"] or {}).get("methods") or []
            unmarked = [m for m in methods if not str(m.get("semantics") or "").strip()]
            if unmarked:
                return ("intent pins a null-rejecting surface but "
                        f"{len(unmarked)}/{len(methods)} ast_hints.methods entries carry no "
                        "`semantics` note: state the initial-state encoding (a named constant "
                        "the producing unit ships, or the nullable alternative) - a mandatory "
                        "field that rejects null with no legal way to represent its pre-use "
                        "state froze two contradictory contracts (seed-002 D1)")
        if (task["ast_hints"] or {}).get("methods") and \
                UNCONSTRUCTIBLE_RE.search(str(task["intent"])) and \
                _instance_members(task["ast_hints"], exported_product(task) or ""):
            return ("intent asserts an UNCONSTRUCTIBLE shape (private constructor / utility "
                    "class / non-instantiable) while ast_hints.methods binds INSTANCE members: "
                    "no caller can ever reach them and no payload satisfies both - bind the "
                    "members `static` in the table, or drop the constructor claim and let the "
                    "unit be instantiated/injected (seed-002 rerun F2 froze the whole domain "
                    "behind exactly this pair)")
    return None


def _path_is_config_artifact(path):
    p = str(path or "").replace("\\", "/").lower()
    return any(p.endswith(tail) for tail in CONFIG_ARTIFACT_TAILS)


def _signature_parameters(hints):
    """The parameter text of every pinned signature - request bindings live there."""
    for method in (hints or {}).get("methods", []) or []:
        signature = str(method.get("signature", "")) if isinstance(method, dict) else str(method)
        if "(" in signature:
            yield signature[signature.index("("):]


def plan_consistency(staged, index):
    """Cross-unit emit checks (FINAL-EVALUATION-seed002 §6 items 1a/1b/1c).

    Returns [error line]s; every rule is grounded in task records only - file
    artifacts, config duties, and the pinned request-parameter shape versus the
    body encoding the paired test intent mandates. Stack-neutral by construction.
    """
    errors = []
    by_project = {}
    for record in index.values():
        if isinstance(record, dict):
            by_project.setdefault(str(record.get("project", "")), []).append(record)
    touched = {str(t.get("project", "")) for t in staged}
    for project in sorted(touched):
        units = by_project.get(project, [])
        owned_paths = [str(u.get("path", "")).replace("\\", "/").lower()
                       for u in units if isinstance(u.get("path"), str)]
        for task in staged:
            if str(task.get("project", "")) != project:
                continue
            own = str(task.get("path", "")).replace("\\", "/").lower()
            # (a) every duty an intent assigns must be executable through an OWNED
            #     artifact: a named file that no task's path carries is unschedulable
            #     prose (seed-002 D3: "Also provide application.yml entries" inside a
            #     one-java-file unit).
            for match in FILE_ARTIFACT_RE.finditer(str(task.get("intent", ""))):
                token = match.group(0).lstrip("./")
                if any(token == own or token in p or p.endswith(token) for p in owned_paths):
                    continue
                errors.append(
                    f"{task['id']}: intent assigns the file artifact '{match.group(0)}' but no "
                    "task path owns it - move the duty to the unit that writes that file or "
                    "schedule a unit for it (duty without an owner is prose, not a plan)")
        # (b) a plan that speaks of externalized configuration must SCHEDULE the
        #     config unit (seed-002 L1-L3: operational values with nothing to bind).
        if any(CONFIG_TRIGGER_RE.search(str(u.get("intent", ""))) for u in units):
            if not any(_path_is_config_artifact(u.get("path")) for u in units):
                errors.append(
                    f"project {project or '?'}: an intent assigns operational configuration "
                    "(@ConfigurationProperties / runtime config file / externalized-config) but "
                    "no unit targets a runtime configuration artifact (application.yml, "
                    "config.ts, settings.py per stack): schedule the config unit carrying the "
                    "seed's literal values")
    # (c) request-encoding alignment on each test+impl pair (seed-002 D2: a pinned
    #     Flux<Dto> request can never receive the "JSON array" its test mandates).
    by_id = {str(u.get("id")): u for u in index.values() if isinstance(u, dict)}
    for task in staged:
        if task.get("stage") != settings.TDD_STAGE:
            continue
        tester = next((by_id.get(str(dep)) for dep in task.get("dependsOn", [])
                       if str(dep).startswith("T1-")), None)
        if not isinstance(tester, dict):
            continue
        params = " ".join(_signature_parameters(task.get("ast_hints")))
        test_intent = str(tester.get("intent", ""))
        if any(t in params for t in STREAM_REQUEST_TYPES) and ARRAY_BODY_RE.search(test_intent):
            errors.append(
                f"{task['id']}/{tester['id']}: pinned request parameter is a streamed "
                "collection while the test intent mandates an array body - pair Flux/stream "
                "types with streamed-document wording, or pin a List/array type (a decoder "
                "can never satisfy both)")
        elif any(t in params for t in ARRAY_REQUEST_TYPES) and STREAM_BODY_RE.search(test_intent):
            errors.append(
                f"{task['id']}/{tester['id']}: pinned request parameter is an array/collection "
                "while the test intent mandates streamed documents - swap the parameter type or "
                "the body encoding; they contradict at the decoder")
    # (d) prose-vs-table CALL-SHAPE contradiction across the pair (seed-002 rerun F2,
    #     second half): a unit's intent pins `Provider.member(` in static form while the
    #     producer task's OWN table binds that member as an instance one. Each side's
    #     tester writes what the text it reads says; the frozen pair then hangs the domain
    #     on a type no payload can satisfy in both shapes. Refused at emit: zero sessions.
    by_product = {}
    for record in list(index.values()) + list(staged):
        if isinstance(record, dict) and (product := exported_product(record)):
            by_product.setdefault((str(record.get("project", "")), product), record)
    for task in staged:
        if task.get("stage") not in (1, 2):
            continue
        project = str(task.get("project", ""))
        for receiver, member in STATIC_CALL_RE.findall(str(task.get("intent", ""))):
            producer = by_product.get((project, receiver))
            if producer is None or str(producer.get("id", "")) == str(task.get("id", "")):
                continue
            if member in _instance_members(producer.get("ast_hints"), receiver):
                errors.append(
                    f"{task['id']}: intent calls '{receiver}.{member}()' in STATIC form while "
                    f"{producer.get('id')}'s own table binds it as an INSTANCE member - one "
                    "shape must win at plan time: rewrite the prose against the injected "
                    f"collaborator, or bind `static` in {producer.get('id')}'s table; two "
                    "frozen tests written from the two shapes can never both pass (F2)")
    return errors
