"""task_identity - what a task record IS: ids, file names, exports,
produced types, observability entries, stage-0 family membership, ast_hints
schema, and the type-shape grammar (publisher/signal/simple returns).
The base layer: nothing here references another task_* module."""

import json
import re
import settings


CAMEL_TYPE_RE = re.compile(r"\b[A-Z][A-Za-z0-9]{2,}\b")

# Plan validity (FINAL-EVALUATION-seed002 §5.1, D1/D2/D3 roots): duties without an
# owning artifact, config-less runtime plans and request-encoding contradictions are
# dead on arrival at the frozen-test gate, so the EMIT refuses them - zero agent
# sessions spent. The tables are STACK-NEUTRAL: they match artifact tails and generic
# type shapes, never a framework name; framework vocabulary lives in the skills.


def step_log_entries(value):
    """The strategy spells its step-log floor in EITHER shape - a flat list, or the
    per-context mapping {context: [logs]} the strategy carrier teaches. The claim law
    and the meter pairing flatten BOTH: a dict-shaped floor was silently SKIPPING the
    completeness gate (2026-11-20 board audit: 4 distribution step logs unowned, the
    gate answered CLEAN - the 2026-11-13 class re-born in a new spelling)."""
    if isinstance(value, dict):
        out = []
        for logs in value.values():
            if isinstance(logs, list):
                out.extend(logs)
        return out
    return value if isinstance(value, list) else []
UNCONSTRUCTIBLE_RE = re.compile(
    r"private\s+(?:final\s+)?constructor|utility\s+class|non[-\s]instantiable", re.I)
STATIC_CALL_RE = re.compile(r"\b([A-Z][A-Za-z0-9]{2,})\.([a-z][A-Za-z0-9]*)\(")

# --- Mechanized plan rules (k)/(m)/(n): the machine half of the 2026-11-16 findings.
# (k) SOURCE CLOSURE (F1): a table method that RETURNS a stream/publisher makes its
#     unit an egress source. A source nobody pins is a rule that executes zero times:
#     its own tests are green (they call it directly), the context boots (it resolves),
#     and the business rule never runs. Rule (i) proved streams-ports need consumers;
#     F1 slipped through because the orphan exposed its stream as a plain method.
# (m) SIGNALLING RETURN (F2): a method returning a boolean/status signal forces its
#     `semantics` to state BOTH outcomes - a false the plan never describes is a false
#     the coder will discard (publish() -> silently dropped sample under burst).
# (n) REGISTRATION XOR (F8): a type the plan has a FACTORY produce (it appears as a
#     wiring unit's method return) must not ALSO carry a self-registration duty; two
#     registration claims per product is decided by container precedence, not the plan.
PUBLISHER_FORMS = ("flux<", "observable<", "publisher<", "readablestream", "asyncgenerator",
                   "asynciterable")
SIGNAL_FORMS = {"boolean", "bool", "java.lang.boolean", "mono<boolean>", "flux<boolean>",
                "observable<boolean>", "publisher<boolean>", "task<bool>",
                "promise<boolean>", "mono<java.lang.boolean>", "result<boolean>"}


def _returns_publisher(returns):
    text = str(returns or "").strip().lower().replace(" ", "")
    # SUBSTRING, not startswith (2026-11-24 seed-002): a streaming endpoint wrapped as
    # `Mono<ResponseEntity<Flux<ServerSentEvent<...>>>>` is STILL a publisher; a start-only
    # test let the envelope hide the stream from the unconsumed-source check, so the SSE
    # surface reported green while nothing in-tree subscribed to it. If a stream type
    # appears ANYWHERE in the return, the source publishes and needs a consumer or a
    # tabled out-of-process boundary.
    return any(form in text for form in PUBLISHER_FORMS)


def _returns_signal(returns):
    return str(returns or "").strip().lower().replace(" ", "") in SIGNAL_FORMS


def _simple_return_type(returns):
    """The bare type name of a return spelling (generics/arrays/package stripped):
    `Mono<Event>`, `Event[]`, `com.x.Event` -> Mono/Event/event."""
    text = str(returns or "").strip()
    text = re.sub(r"<.*>", "", text).replace("[]", "").strip()
    return text.rsplit(".", 1)[-1]


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
    if not isinstance(hints, dict):
        return "ast_hints must be an object"
    if set(settings.AST_HINT_KEYS) - set(hints):
        return f"ast_hints keys must contain {list(settings.AST_HINT_KEYS)}"
    extra = sorted(set(hints) - set(settings.AST_HINT_KEYS) - set(settings.AST_HINT_OPTIONAL_KEYS))
    if extra:
        return f"ast_hints keys must be from {list(settings.AST_HINT_KEYS) + list(settings.AST_HINT_OPTIONAL_KEYS)}, got {extra}"
    if not (isinstance(hints["package"], str) and hints["package"].strip()):
        return "ast_hints.package must be a non-empty string"
    if not isinstance(hints["implements"], list) \
            or not all(isinstance(s, str) and s.strip() for s in hints["implements"]):
        return "ast_hints.implements must be a list of non-empty strings"
    if not isinstance(hints["dependencies"], list):
        return "ast_hints.dependencies must be a list of {type, task_id} or {type, context} objects"
    for dep in hints["dependencies"]:
        # (2026-11-26 parallel plan) two lawful shapes: {type, task_id} pins a KNOWN id
        # (root/queued/own-file/symbol-table), {type, context} pins a PARALLEL SIBLING by
        # the context name - ids are renumbered at claim, so no drafting session can know
        # a sibling's id; plan_wiring.resolve_sibling_anchors binds the anchor to the real
        # id after every claim, before the batch emit. An anchor whose context never
        # exports that type is refused as an unresolvable pin, never passed through.
        if not isinstance(dep, dict) or not isinstance(dep.get("type"), str) \
                or not dep["type"].strip():
            return ("each ast_hints.dependencies entry must be {type, task_id} or "
                    "{type, context}, the type non-empty")
        if set(dep) not in ({"type", "task_id"}, {"type", "context"}):
            return ("each ast_hints.dependencies entry must carry EXACTLY task_id or "
                    "context beside its type - never both, never neither")
        for key in ("task_id", "context"):
            if key in dep and (not isinstance(dep[key], str) or not dep[key].strip()):
                return f"ast_hints.dependencies {key} must be a non-empty string"
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
    if "meters" in hints:
        if not isinstance(hints["meters"], list):
            return "ast_hints.meters must be a list of {name, duty} objects (rule (z))"
        for entry in hints["meters"]:
            if not (isinstance(entry, dict) and set(entry) == {"name", "duty"}
                    and isinstance(entry["name"], str) and entry["name"].strip()
                    and entry["duty"] in settings.METER_DUTIES):
                return ("each ast_hints.meters entry must be {name, duty} with a non-empty "
                        f"name and duty in {list(settings.METER_DUTIES)} - the owning unit "
                        "spells `owns`, every unit whose contract records the meter spells `uses`")
    if "routes" in hints:
        if not isinstance(hints["routes"], list):
            return "ast_hints.routes must be a list of {method, path, duty} objects (rule (z))"
        for entry in hints["routes"]:
            if not (isinstance(entry, dict) and set(entry) == {"method", "path", "duty"}
                    and isinstance(entry["method"], str) and entry["method"].strip()
                    and isinstance(entry["path"], str) and entry["path"].strip().startswith("/")
                    and entry["duty"] in settings.ROUTE_DUTIES):
                return ("each ast_hints.routes entry must be {method, path, duty} with a non-empty "
                        "method, a path starting with '/', and duty in "
                        f"{list(settings.ROUTE_DUTIES)} - the inbound unit that answers the route "
                        "spells `serves`; guards, callers and slices spell `uses`")
    if "config" in hints:
        if not isinstance(hints["config"], list):
            return "ast_hints.config must be a list of {path, kind[, fields]} objects (rule (z5))"
        for entry in hints["config"]:
            if not (isinstance(entry, dict)
                    and {"path", "kind"} <= set(entry) <= {"path", "kind", "fields", "value"}
                    and isinstance(entry["path"], str) and entry["path"].strip()
                    and "/" not in entry["path"]
                    and entry["kind"] in settings.CONFIG_KINDS
                    and ("fields" not in entry
                         or (isinstance(entry["fields"], list) and entry["fields"]
                             and all(isinstance(f, str) and f.strip()
                                     for f in entry["fields"])))):
                return ("each ast_hints.config entry must be {path, kind} (a dotted property "
                        f"path, kind in {list(settings.CONFIG_KINDS)}) plus optional non-empty "
                        "`fields` (the element keys of a structured path) plus optional `value` "
                        "(the DEFAULT the document seeds, spelled from the strategy rules - "
                        "the coverage wire copies the binder's entry to the ONE config unit) "
                        "- the binding unit tables the shape its record declares and the "
                        "config unit cites it VERBATIM (rule (z5))")
    return None


MIGRATION_SCRIPT_NAME_RE = re.compile(r"^V\d+__[^/\\]+$", re.I)


def is_database_task(task, index=None):
    """STAGE-0 DATABASE FAMILY membership (2026-11-24, seed-002 second run; third-run
    revision): keyed on the runner's OWN vocabulary - a `migration`/`migrations` path
    segment ANYWHERE in the tree (the packaged `src/main/resources/db/migration` and the
    module-root `db/migrations` are both that word; the active tech-stack skill names
    which), a versioned runner script name (`V<n>__description.ext`), OR the STRUCTURAL
    hang: a stage-0 bootstrap task whose `dependsOn` names this domain's scaffold/manifest
    (export-keyed, S16's law: families are keyed by export marker, never by path shape).
    The path-only test refused the database phase's OWN configuration-profile and backup
    concerns when they landed outside the runner folder (2026-11-24 third run: the
    application.yml task's scaffold edge was refused, the agent left the concern unqueued,
    and the config-file bytes sat on disk with no owning task). NEVER a fixed folder
    LOCATION: a literal folder check quietly refuses a correctly packaged schema - the
    gate-vs-skill twin of the N8/S16 pair this codebase keeps relearning."""
    path = str((task or {}).get("path", "")).replace("\\", "/")
    parts = tuple(p.lower() for p in path.split("/") if p)
    if "migration" in parts or "migrations" in parts:
        return True
    if bool(parts) and MIGRATION_SCRIPT_NAME_RE.match(parts[-1]) is not None:
        return True
    if int((task or {}).get("stage") or 0) == 0 and str(task.get("kind") or "") == "bootstrap":
        export = str(task.get("export") or "").strip()
        if export not in (settings.SCAFFOLD_EXPORT, settings.BUILD_MANIFEST_EXPORT):
            for dep in (task.get("dependsOn") or []):
                ref = (index or {}).get(str(dep))
                if isinstance(ref, dict) and str(ref.get("export") or "").strip() in (
                        settings.SCAFFOLD_EXPORT, settings.BUILD_MANIFEST_EXPORT):
                    return True
    return False
