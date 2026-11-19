"""Blackboard task schema: validation and ordering keys (pure, no I/O state)."""
import json
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
# argument + comparison inside parentheses (or adjacent): "revision (>=1, ...)",
# "window (> 0)", "capacity (<= 1000)" - the invariant-claim surface of an intent.
# INTENT ECONOMY (2026-11-18 token audit of the plan phase): the emitted plan of one domain measured
# 23,585 tokens, of which `intent` prose was 52%; the biggest single assistant output turn on record
# was 40,442 tokens, and half the emit attempts bounced a refusal that used to demand a full rewrite.
# Volume is therefore a plan defect, not a style preference - but the machine rule is a WALL, not a
# target: only a document-sized intent is refused, and only while planning (a resumed board must stay
# readable). What must go instead is the narration `ast_hints` already pins; every token the gates
# demand (spec_ref + capability + mechanism, config literals, both signal branches) still stays.
INTENT_WORD_TARGET = 80
INTENT_WORD_CEILING = 180

CONSTRUCTOR_CLAIM_RE = re.compile(r"\b(\w+)\s*\(\s*(?:>=|<=|>|<)\s*\d")
STREAM_REQUEST_TYPES = ("Flux<", "Observable<", "ReadableStream", "AsyncGenerator",
                        "AsyncIterable", "stream of")
ARRAY_REQUEST_TYPES = ("List<", "Set<", "Collection<", "Iterable<")
ARRAY_BODY_RE = re.compile(r"JSON array|array of\b|single array|array body|array document", re.I)
STREAM_BODY_RE = re.compile(r"streamed (?:JSON )?documents|line[- ]delimited|ndjson|"
                            r"newline[- ]delimited|sequence of (?:JSON )?documents|stream body", re.I)

# --- Mechanized plan rules (o)/(p)/(q): the machine half of the 2026-11-16 SECOND
# drain findings (a mocked substrate hid a NOT NULL PK; a contextLoads-only boot;
# retries minting revisions). Generic vocabulary only: intent phrases and the layer
# field - never compiler output, never source reading.
DML_CLAIM_RE = re.compile(r"\b(?:INSERT INTO|UPDATE\s+\w+\s+SET|DELETE FROM|"
                          r"SELECT\b[^\n]*\bFROM\b)", re.I)
REAL_SUBSTRATE_RE = re.compile(
    r"real (?:embedded )?(?:database|substitute|store|ddl|schema|h2)|"
    r"embedded substitute|against the (?:real |live )?(?:database|substitute|schema|ddl)|"
    r"actual (?:migration|ddl|schema)|(?:executes?|run(?:s|ning)?) (?:the )?(?:real|actual) "
    r"(?:ddl|migration)|migration ddl|real ddl", re.I)
INTEGRATION_MARK_RE = re.compile(r"end[- ]to[- ]end|integration slice|request[- ]path", re.I)
APPEND_CHAIN_RE = re.compile(r"revision|append[- ]only|supersedes", re.I)
INBOUND_RE = re.compile(r"@(?:Post|Get|Put|Request)Mapping|/api/|\broutes?\b.*(?:POST|GET)|"
                        r"POST\b[^\n]*(?:body|endpoint|packet)|inbound (?:http|request)", re.I)
DEDUP_RE = re.compile(r"idempoten|dedup|client[- ]supplied|client[- ]key|natural key|"
                      r"at[- ]most[- ]once|unique business key", re.I)
# (r) migrations must TRAVEL WITH THE ARTIFACT: a config unit that spells a runner
# location CWD-relative (filesystem:/file:) into the project's own tree is refused at
# EMIT - the packaged jar would boot green over an EMPTY schema from any other
# directory. classpath: locations (the packaged form) are the demanded shape. Enforced
# HERE, never at the assembly gate: the config unit's frozen test pins the location
# string, so a delivered-time second opinion demanding another value is an unsatisfiable
# pair (2026-11-16: the assembly-side probe livelocked T4 against its own frozen test).
MIGRATION_SCHEME_RE = re.compile(r"flyway|liquibase|schema-locations|script_location|"
                                 r"version_locations|sql\.init", re.I)
CWD_RELATIVE_LOCATION_RE = re.compile(r"(?:filesystem|file)\s*:[:\w./-]*migrations?/?", re.I)

# --- Plan rules (s)/(t)/(u): the PART III (2026-11-16 evening) refusal classes.
# (s) CORRECTION VS RETRY IS AN IDENTITY-AXIS DECISION (G2): rule (q) demands a dedup
#     identity; it never demanded saying where the MUTABLE PAYLOAD lives relative to it.
#     A natural identity that excludes the value turns a resent sample with a corrected
#     value into a silent no-op "duplicate" - the seed's "corrections append revisions"
#     dies while (q) is satisfied, every test is green and no gate sees the drop. The
#     refusal is stack-neutral: it demands the plan SAY the axis decision (excluded +
#     discriminator, or included) wherever the dedup sentence is spelled, never which
#     database or schema syntax enforces it.
# (t) A PROMISED MECHANISM IS A SCHEDULED DUTY (G3): the strategy promised correlation
#     "propagated to log lines via <mechanism>"; no unit scheduled the dependency +
#     wiring that INSTALLS that mechanism, so correlation stayed manual discipline and
#     a future line silently loses the key. The rule carries the strategy's OWN token
#     into the plan's duties - the concrete mechanism vocabulary belongs to the active
#     tech-stack skill, never to this validator.
# (u) NO AUDITED OUTCOME UNMETERED (G4): the floor gate checked that PROMISED meters
#     are claimed, not that the floor covers every outcome the plan ACKNOWLEDGES. An
#     error swallowed after a FAILED audit survives in the store but in no counter -
#     ops sees a healthy stream while the pipeline loses events. Layer 1 pairs every
#     step log with a metric (or an explicit uncounted_steps exemption); Layer 2 pairs
#     every failure/drop vocabulary in tabled `semantics` with a counting meter (or a
#     declared uncounted-failures posture). Meter NAMES stay abstract here; the stack
#     skill names the registry.
CORRECTION_RE = re.compile(r"correct\w*|backfill\w*|supersed\w*", re.I)
VALUE_AXIS_RE = re.compile(
    r"(?:value|payload|measurement)\w*[^.;\n]{0,80}(?:part of|inside|outside|excluded?"
    r"|not in|included|covered|discriminat|compared?|dedup\w*|no-op|revision)"
    r"|(?:identity|key)[^.;\n]{0,60}(?:includes?|excludes?|covers)[^.;\n]{0,40}"
    r"(?:value|payload)"
    r"|correction flag|client[- ]supplied (?:version|sequence|counter)"
    r"|value (?:comparison|hash)|compare[sd]? (?:the )?(?:value|payload)"
    r"|payload (?:differs|changed|comparison)", re.I)
MECHANISM_PROMISE_RE = re.compile(r"\bvia\b[^.;\n]{0,80}\bpropagat\w*"
                                  r"|\bpropagat\w*[^.;\n]{0,80}\bvia\b", re.I)
VIA_TOKEN_RE = re.compile(r"\bvia\s+(?:the\s+)?([A-Za-z][\w]*(?:[-\s][A-Za-z][\w]*){0,2})",
                         re.I)
FAIL_OUTCOME_RE = re.compile(r"\b(?:drop\w*|fail\w*|reject\w*|swallow\w*|overflow\w*)\b", re.I)
METER_CLAIM_RE = re.compile(r"(?:counter|meter|gauge|timer)[^.;\n]{0,80}"
                            r"(?:drop|fail|reject|error)|(?:drop|fail|reject|error)"
                            r"[^.;\n]{0,80}(?:counter|meter|gauge|timer)", re.I)
STEP_STOP_TOKENS = {"the", "and", "for", "with", "into", "from", "that", "this", "are",
                    "per", "each", "once", "after", "before", "when", "than", "then",
                    "over", "under", "not", "new", "raw", "all", "same", "every",
                    "their", "there", "which", "being", "was", "were", "been"}


def _step_tokens(text):
    return {w for w in re.findall(r"[a-z]{4,}", str(text or "").lower())
            if w not in STEP_STOP_TOKENS}


def _surface_norm(text):
    return " ".join(str(text or "").strip().lower().rstrip(".").split())


def _meter_pairs(step, metrics):
    st = _step_tokens(step)
    if not st:
        return True
    for entry in metrics:
        if isinstance(entry, str):
            entry = {"name": entry}
        if not isinstance(entry, dict):
            continue
        blob = " ".join([str(entry.get("name", "")), " ".join(map(str, entry.get("tags") or [])),
                         str(entry.get("counts", ""))])
        mt = _step_tokens(blob)
        if any(a == b or a.startswith(b[:5]) or b.startswith(a[:5]) for a in st for b in mt):
            return True
    return False


def _mechanism_claimed(token, texts):
    """The strategy's mechanism phrase must appear as an INSTALL duty, adjacent and
    unnegated: 'no context-propagation library is used' is a divergence, not a duty -
    the refusal class G3 was born from (the plan quietly un-promised the strategy)."""
    norm = _surface_norm(token).replace("_", "-")
    if not norm:
        return True
    words = [w for w in re.split(r"[-\s]+", norm) if w]
    joined = r"[-\s]+".join(map(re.escape, words))
    alt = r"[-\s]+".join(map(re.escape, reversed(words))) if len(words) > 1 else joined
    finder = re.compile(f"(?:{joined}|{alt})", re.I)
    negated = re.compile(r"\b(?:no|not|without|never|avoid\w*|skip\w*|exclude\w*|"
                         r"drop\w*|remov\w*|abandon\w*)\b[^,.;]{0,24}$", re.I)
    for text in texts:
        for match in finder.finditer(text):
            if negated.search(text[:match.start()][-28:]):
                continue
            return True
    return False

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
BOUNDARY_MARKER_RE = re.compile(r"out-of-process|external subscribers|"
                                r"downstream subscribers", re.I)
SELF_REGISTRATION_RES = {
    "java": re.compile(r"@(?:Component|Service|Repository|RestController|Controller)\b|"
                       r"self[- ]?registers?", re.I),
    "typescript": re.compile(r"@Injectable\b|module provider|provided by\b|self[- ]?registers?", re.I),
    "javascript": re.compile(r"@Injectable\b|module provider|provided by\b|self[- ]?registers?", re.I),
    "python": re.compile(r"router registration|registered dependency|self[- ]?registers?", re.I),
    "go": re.compile(r"self[- ]?registers?", re.I),
}
# Any language's generic stereotype vocabulary: used when the strategy names an
# unknown stack - catches the plan's own words ("registers itself") without vocab.
GENERIC_SELF_REGISTRATION_RE = re.compile(r"self[- ]?registers?|registers? itself", re.I)


def strategy_language(slug):
    """Lowercase first token of the strategy's planned language ("" with no strategy
    file or unknown shape - language-keyed rules then skip, legacy-safe)."""
    file = settings.COMPLETE_DIR / f"execution-strategy-{slug}.json"
    try:
        strategy = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    stack = strategy.get("tech_stack") or strategy.get("tech stack") or {}
    language = str(stack.get("language") or strategy.get("language") or "").strip().lower()
    return language.split()[0] if language else ""


def _returns_publisher(returns):
    text = str(returns or "").strip().lower().replace(" ", "")
    return any(text.startswith(form) for form in PUBLISHER_FORMS)


def _returns_signal(returns):
    return str(returns or "").strip().lower().replace(" ", "") in SIGNAL_FORMS


def _simple_return_type(returns):
    """The bare type name of a return spelling (generics/arrays/package stripped):
    `Mono<Event>`, `Event[]`, `com.x.Event` -> Mono/Event/event."""
    text = str(returns or "").strip()
    text = re.sub(r"<.*>", "", text).replace("[]", "").strip()
    return text.rsplit(".", 1)[-1]


def _strategy_text(slug):
    file = settings.COMPLETE_DIR / f"execution-strategy-{slug}.json"
    try:
        return file.read_text(encoding="utf-8")
    except OSError:
        return ""


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
                    and {"path", "kind"} <= set(entry) <= {"path", "kind", "fields"}
                    and isinstance(entry["path"], str) and entry["path"].strip()
                    and "/" not in entry["path"]
                    and entry["kind"] in settings.CONFIG_KINDS
                    and ("fields" not in entry
                         or (isinstance(entry["fields"], list) and entry["fields"]
                             and all(isinstance(f, str) and f.strip()
                                     for f in entry["fields"])))):
                return ("each ast_hints.config entry must be {path, kind} (a dotted property "
                        f"path, kind in {list(settings.CONFIG_KINDS)}) plus optional non-empty "
                        "`fields` (the element keys of a structured path) - the binding unit "
                        "tables the shape its record declares and the config unit cites it "
                        "VERBATIM (rule (z5))")
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
        words = len(str(task["intent"]).split())
        if words > INTENT_WORD_CEILING:
            return (f"intent runs to {words} words (target {INTENT_WORD_TARGET}, ceiling "
                    f"{INTENT_WORD_CEILING}): the plan of one domain is emitted in a single turn and "
                    "re-sent on every later one, so prose volume is paid twice. Move what "
                    "`ast_hints` already pins (signatures, types, collaborators) out of the sentence, "
                    "and split any unit whose contract genuinely needs more: one unit that must "
                    "explain itself at length is usually two units. Keep every token the gates demand "
                    "in prose - the security spec_ref + capability + mechanism, the config literals, "
                    "the both-branch semantics - but meter names and request paths are NOT prose: they "
                    "belong in ast_hints.meters / ast_hints.routes (rule (z))")
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
        # RANGE-CLAIM -> CONSTRUCTOR SEMANTICS (2026-11-16): an intent that states a
        # numeric/argument invariant ("revision (>=1, else ...)") must carry it in the
        # constructor's table entry. The consumer units' testers see the injected
        # collaborator TABLE, never this unit's prose; a prose-only invariant let four
        # units' frozen fixtures construct revision=0 against a domain that rejects it,
        # and those units died 3/3 on tests they cannot edit.
        claims = CONSTRUCTOR_CLAIM_RE.findall(str(task["intent"]))
        if claims and task.get("stage") in (1, 2):
            product = (exported_product(task) or "").strip()
            ctor = next((m for m in ((task.get("ast_hints") or {}).get("methods") or [])
                         if isinstance(m, dict)
                         and str(m.get("signature", "")).startswith(product + "(")), None)
            if ctor is not None and not str(ctor.get("semantics") or "").strip():
                return (f"intent states constructor invariants on {sorted(set(claims))} but "
                        f"the '{product}' constructor table entry carries no `semantics`: "
                        "consumer units' testers receive ONLY the collaborator table - spell "
                        "the valid-argument ranges and the sanctioned construction (factory, "
                        "initial value) into that entry's `semantics`, or the next unit's "
                        "fixture guesses an illegal literal and dies on this record "
                        "(seed-002 2026-11-16: revision (>=1) lived only in prose; four "
                        "consumer tests fabricated 0)")
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
    # (w) a stage-1 TEST task owns a TEST artifact, NEVER the file under test
    #     (2026-11-17 drain: the architect emitted every tester task with the paired
    #     production unit's path - the tester writes its test AT `path`, so @Test
    #     classes landed under the main source root, test-scoped dependencies were
    #     invisible to their compile classpath, and the import-closure guard killed
    #     the drain on the first red close-out). One path cannot hold both the frozen
    #     test and the woven implementation; the pair is refused at emit. Stage 3 may
    #     share stage 2's path: the refactor targets the implementation file.
    code_paths = {}
    for record in list(index.values()) + list(staged):
        if (isinstance(record, dict) and record.get("stage") in (2, 3)
                and isinstance(record.get("path"), str)):
            code_paths.setdefault(str(record.get("project", "")), set()).add(
                str(record["path"]).replace("\\", "/").lower())
    for task in staged:
        if task.get("stage") != settings.TESTER_STAGE:
            continue
        own = str(task.get("path", "")).replace("\\", "/").lower()
        if own and own in code_paths.get(str(task.get("project", "")), set()):
            errors.append(
                f"{task['id']}: stage-1 test path equals an implementation task's path "
                f"({task['path']}) - the tester writes the frozen test AT `path` and the "
                "coder weaves the unit into that same file: point the test task at its own "
                "test artifact (every stack keeps tests in a separate file from the unit, "
                "visible only to the test classpath)")
    # (x) a handler unit that forbids its stack's handler marker can never serve a
    #     request (2026-11-17 drain: the controller's intent pinned "no scanning-
    #     registration annotation: it is registered only by the wiring factory" -
    #     WebFlux's RequestMappingHandlerMapping.isHandler accepts ONLY classes
    #     annotated @Controller (verified against the framework bytecode), so the
    #     factory bean was constructed, the context booted green... and every request
    #     got 404). Refused at emit, gated on the strategy's planned language; the
    #     concrete marker/mechanism names come from the tech-stack skill.
    no_marker_re = re.compile(
        r"no\s+(?:class\s+)?(?:stereotype|scanning[- ]registration|registration "
        r"annotation)|never\s+(?:annotated|self-?regist)|not\s+annotated\s+with|"
        r"registered\s+only\s+by\s+the\s+wiring", re.I)
    for task in staged:
        if task.get("stage") != settings.TDD_STAGE:
            continue
        if str(task.get("project", "")) and strategy_language(str(task.get("project", ""))) != "java":
            continue
        intent = str(task.get("intent", ""))
        surface = intent + " " + str(task.get("export", "")) + " " + str(task.get("path", ""))
        if not re.search(r"\bcontroller\b|@RequestMapping|@PostMapping|endpoint handler",
                         surface, re.I):
            continue  # mapped handlers only: factory-built WebFilter components are legal
        if INBOUND_RE.search(intent) and no_marker_re.search(intent):
            errors.append(
                f"{task['id']}: an inbound handler unit whose intent FORBIDS the stack's "
                "handler marker can never serve - WebFlux maps only classes carrying the "
                "controller annotation (a factory-produced unmarked POJO boots green and "
                "answers 404 on its own endpoints, 2026-11-17). Name ONE mechanism at plan "
                "time: the handler carries the stack skill's controller marker (wiring still "
                "supplies its collaborators), or the route is a functional router bean owned "
                "by the wiring unit")
    # (k)/(m)/(n): the machine half of the 2026-11-16 findings - see the vocabulary
    # block above for what each refusal class means and why the per-unit gates
    # structurally cannot see them.
    universe = {}
    for record in list(index.values()) + list(staged):
        if isinstance(record, dict) and record.get("id"):
            universe.setdefault(str(record.get("project", "")), []).append(record)
    for task in staged:
        if task.get("stage") not in (1, 2):
            continue
        for member in (task.get("ast_hints") or {}).get("methods") or []:
            if (isinstance(member, dict) and _returns_signal(member.get("returns"))
                    and not str(member.get("semantics") or "").strip()):
                errors.append(
                    f"{task['id']}: tabled method '{member.get('signature')}' returns a "
                    "SIGNAL but carries no `semantics` - spell what TRUE and what FALSE "
                    "mean to the caller (accepted/rejected, inserted/duplicate, "
                    "written/dropped): a false the plan never describes is a false the "
                    "coder discards, and the caller answers success anyway (2026-11-16: "
                    "publish()->false silently dropped samples under burst, API lied 202)")
    for project, units in sorted(universe.items()):
        live = [u for u in units if isinstance(u, dict)]
        by_product = {}
        for u in live:
            name = exported_product(u)
            if name:
                by_product.setdefault(name.lower(), u)
        pinned_ids, pinned_types = set(), set()
        by_id = {str(u.get("id", "")): u for u in live}
        for u in live:
            if u.get("stage") not in (1, 2):
                continue
            # a pin from a unit whose OWN table returns that type is a PRODUCTION edge
            # (wiring/factory), not a consumer: 2026-11-16's orphaned reordering service
            # was exactly "registered by the config unit, called by nobody" - counting
            # the factory's pin as consumption lets the F1 shape pass this gate.
            own_returns = {(_simple_return_type(m.get("returns")) or "").lower()
                           for m in ((u.get("ast_hints") or {}).get("methods") or [])
                           if isinstance(m, dict)}
            for dep in (u.get("ast_hints") or {}).get("dependencies") or []:
                if not isinstance(dep, dict):
                    continue
                dep_type = str(dep.get("type") or "").lower()
                dep_id = str(dep.get("task_id") or "")
                dep_owner = by_id.get(dep_id) or by_product.get(dep_type)
                dep_product = str(exported_product(dep_owner) or "").lower() if dep_owner else ""
                if dep_type in own_returns or (dep_product and dep_product in own_returns):
                    continue  # this unit FACTORIES the type - not its consumer
                pinned_ids.add(dep_id)
                pinned_types.add(dep_type)
                if dep_product:
                    pinned_types.add(dep_product)

        def boundary_named(*names):
            """out-of-process exemption is PER SOURCE: a strategy segment must name
            THIS unit's product next to the marker (coarse whole-strategy markers
            would exempt every island in the plan)."""
            text = _strategy_text(project)
            candidates = [n for n in names if n]
            for segment in re.split(r"[;\n]|\|\", \"", text):
                if BOUNDARY_MARKER_RE.search(segment) and any(
                        c.lower() in segment.lower() for c in candidates):
                    return True
            return False
        self_reg = SELF_REGISTRATION_RES.get(strategy_language(project),
                                             GENERIC_SELF_REGISTRATION_RE)
        factory_claims, source_claims = {}, {}
        for u in live:
            if u.get("stage") != 2:
                continue  # the SOURCE/factory duty lives in the implementation unit;
                          # the stage-1 twin mirrors the table to assert it
            hints = u.get("ast_hints") or {}
            for member in hints.get("methods") or []:
                if not isinstance(member, dict):
                    continue
                if _returns_publisher(member.get("returns")):
                    source_claims.setdefault(str(u.get("id")), (u, member))
                ret = _simple_return_type(member.get("returns"))
                owner = by_product.get(ret.lower()) if ret else None
                if owner is not None and str(owner.get("id")) != str(u.get("id")):
                    factory_claims.setdefault(ret.lower(), []).append(u)
        for uid, (unit, member) in sorted(source_claims.items()):
            faces = {str(exported_product(unit) or "").lower()}
            faces |= {str(s).lower() for s in (unit.get("ast_hints") or {}).get("implements") or []}
            faces.discard("")
            if (uid in pinned_ids or (pinned_types & faces)
                    or BOUNDARY_MARKER_RE.search(str(unit.get("intent", "")))
                    or boundary_named(*faces)):
                continue
            errors.append(
                f"{uid}: tabled method '{member.get('signature')}' PUBLISHES a stream "
                f"({member.get('returns')}) but no unit pins this type as a collaborator - "
                "the rule behind an unconsumed source executes zero times while its unit "
                "tests and the boot gate stay green (2026-11-16: the reordering service "
                "was a registered island; the seed's core rule never ran). Name its "
                "consumer unit in the DAG, route it in the wiring unit's duty list, or "
                "declare the out-of-process boundary in the strategy")
        for ret, producers in sorted(factory_claims.items()):
            owner = by_product.get(ret)
            if owner is None or owner.get("stage") not in (1, 2):
                continue
            if not self_reg.search(str(owner.get("intent", ""))):
                continue
            for producer in producers:
                errors.append(
                    f"{producer.get('id')}/{owner.get('id')}: type '{ret}' is claimed by "
                    "TWO registration duties - a factory method in the wiring unit AND a "
                    "self-registration stereotype in its own intent. One mechanism per "
                    "product (factory XOR self-register): the container's precedence, not "
                    "the plan, currently decides which definition survives")
        # (o) PERSISTENCE ADAPTERS ARE TESTED AGAINST THE REAL SUBSTRATE, never a mock
        #     of the database client: the mock proves call SHAPE, never schema FIT -
        #     NOT NULL floors, CHECK bounds and PK population stay unproven until the
        #     first production request (2026-11-16: mocked DatabaseClient hid an
        #     unpopulated NOT NULL audit_id; EVERY audit write failed on the live path
        #     while 186 tests stayed green).
        by_num = {}
        for u in live:
            ident = str(u.get("id", ""))
            mark = ident.rsplit("-", 1)
            if len(mark) == 2 and mark[1].isdigit():
                by_num.setdefault(mark[1], {})[mark[0]] = u
        for u in live:
            if u.get("stage") != 2 or not DML_CLAIM_RE.search(str(u.get("intent", ""))):
                continue
            pair = by_num.get(str(u.get("id", "")).rsplit("-", 1)[-1], {}).get("T1")
            if pair is None:
                continue
            pair_intent = str(pair.get("intent", ""))
            if not REAL_SUBSTRATE_RE.search(pair_intent):
                errors.append(
                    f"{u['id']}/{pair['id']}: the unit executes SQL/DML against a schema, "
                    "but its paired test intent never demands a REAL-SUBSTRATE run "
                    "(the embedded substitute executing the actual migration DDL) - a "
                    "client-mocked slice verifies call SHAPE, never schema fit: NOT NULL "
                    "floors, CHECK bounds and PK population stay unproven until the "
                    "first production request (2026-11-16: mocked DatabaseClient hid an "
                    "unpopulated NOT NULL audit_id; every audit write failed live with "
                    "the whole suite green). Rewrite the test intent to run the real "
                    "DDL against the substitute and assert the durable row; a mocked "
                    "client case may be EXTRA, never the only substrate test")
        # (p) INBOUND SURFACES SHIP A REQUEST-PATH SLICE: an entry adapter's unit tests
        #     construct the use case with `new`; the boot smoke loads a context without
        #     sending a request. Only an end-to-end slice - drive the entry, assert the
        #     durable rows - makes the components agree with the real schema (2026-11-16
        #     PART II N1: contextLoads passed over an adapter that failed every write).
        inbound = [u for u in live if u.get("stage") == 2
                   and (str(u.get("layer", "")) in ("interface", "api", "entry")
                        or INBOUND_RE.search(str(u.get("intent", ""))))]
        if inbound and not any(
                u.get("stage") == 1 and INTEGRATION_MARK_RE.search(str(u.get("intent", "")))
                for u in list(index.values()) + list(staged)
                if str(u.get("project", "")) == project):
            errors.append(
                f"{project}: {len(inbound)} inbound adapter unit(s) but NO end-to-end "
                "request-path slice scheduled: unit tests build the use case with new, "
                "the smoke test loads a context without a request - neither proves the "
                "entry, the store and the schema agree. Add one integration test task "
                "that drives the entry surface against the embedded substitute and "
                "asserts the durable effect (valid AND invalid payloads)")
        # (q) RETRYABLE INBOUND + APPEND-ONLY CHAIN = IDEMPOTENCY DUTY or an explicit
        #     at-most-once declaration: with a server-minted identity, a network retry
        #     is indistinguishable from a correction and becomes a domain revision
        #     (2026-11-16 PART II N4: overflow-then-retry minted spurious revisions).
        #     The duty must live ON THE INGRESS CHAIN - the same units that receive and
        #     append - not merely somewhere in the plan (an unrelated resubscribe
        #     idempotency note must not excuse a non-idempotent POST).
        chain_ids = {str(u.get("id")) for u in inbound}
        frontier = list(chain_ids)
        by_id_all = {str(u.get("id")): u for u in live}
        while frontier:
            fid = frontier.pop()
            for dep in by_id_all.get(fid, {}).get("dependsOn") or []:
                dep = str(dep)
                if dep not in chain_ids and dep in by_id_all:
                    chain_ids.add(dep)
                    frontier.append(dep)
        chain_text = " ".join(str(by_id_all[i].get("intent", "")) for i in chain_ids)
        strategy_exempt = False
        for segment in re.split(r"[.;\n]", _strategy_text(project)):
            if DEDUP_RE.search(segment) and re.search(r"ingress|inbound|post|http|request",
                                                      segment, re.I):
                strategy_exempt = True
                break
        if (APPEND_CHAIN_RE.search(chain_text) and INBOUND_RE.search(chain_text)
                and not DEDUP_RE.search(chain_text) and not strategy_exempt):
            errors.append(
                f"{project}: the ingress chain ({', '.join(sorted(chain_ids)[:5])}) is "
                "at-least-once inbound over an append-only revision chain with NO "
                "idempotency duty ON THE CHAIN: name the client-supplied dedup key (or "
                "natural identity) in the receiving use-case/store contracts, or declare "
                "the at-most-once posture in the strategy - otherwise every network "
                "retry mints a revision the device never sent twice")
        # (r) migration locations must be the PACKAGED (classpath) form - enforced at
        #     emit, where the architect can still fix it; see the vocabulary note above.
        if (workspace.project_root_for(project) / "db" / "migrations").is_dir():
            for u in live:
                if u.get("stage") != 2 or not _path_is_config_artifact(u.get("path")):
                    continue
                cfg_intent = str(u.get("intent", ""))
                if (MIGRATION_SCHEME_RE.search(cfg_intent)
                        and CWD_RELATIVE_LOCATION_RE.search(cfg_intent)
                        and "classpath:" not in cfg_intent):
                    errors.append(
                        f"{u['id']}: the runtime configuration pins migration locations "
                        "CWD-relative (filesystem:/file: into the project tree): the "
                        "packaged jar boots green over an EMPTY schema from any other "
                        "directory. Spell the runner location as the PACKAGED form "
                        "(classpath:<dir>) and have the scripts live under the stack's "
                        "packaged resources root - the DB handoff names that directory")
        # (s) CORRECTION VS RETRY ON A DEDUPED, APPEND-ONLY CHAIN: once rule (q) is
        #     satisfied the plan HAS an identity - the silent failure moved one level
        #     in: if the identity excludes the mutable payload and no discriminator
        #     separates a retry from a correction, the seed's corrections resolve as
        #     no-op duplicates (2026-11-16 PART III G2: UNIQUE(device, metric, t_device)
        #     swallowed a resent sample with a corrected value; the dedup rule stayed
        #     honored, the correction rule died undisclosed and untested).
        stext = _strategy_text(project)
        axis_corpus = " ".join([chain_text, stext])
        if (inbound and (DEDUP_RE.search(chain_text) or strategy_exempt)
                and APPEND_CHAIN_RE.search(axis_corpus)
                and CORRECTION_RE.search(axis_corpus)
                and not any(VALUE_AXIS_RE.search(seg)
                            for seg in re.split(r"[.;\n]", axis_corpus))):
            errors.append(
                f"{project}: the chain dedups an at-least-once inbound over an append-only "
                "history that SPEAKS of corrections/backfills, but no contract states the "
                "VALUE-AXIS decision: is the mutable payload part of the dedup identity, or "
                "excluded - and if excluded, what separates a retry (no-op) from a correction "
                "(revision appended)? A dedup identity that never names what it dedups drops "
                "every value-correction as a 'duplicate' while rule (q) stays satisfied. "
                "Spell the axis decision beside the identity in the receiving contracts and "
                "table BOTH resend classes as test duties (same-payload -> no-op; "
                "changed-value -> revision)")
        # (t) PROMISED MECHANISM -> SCHEDULED INSTALL DUTY: carry the strategy's own
        #     vocabulary into the plan (2026-11-16 PART III G3: 'propagated to log lines
        #     via context-propagation' stayed a promise - no unit scheduled the
        #     dependency + boot wiring, correlation survived only as hand-passed
        #     arguments, and every gate stayed green because prose and code never get
        #     compared).
        if stext:
            duty_texts = [str(u.get("intent", "")) for u in live if u.get("stage") == 2]
            for seg in re.split(r"[.;\n]", stext):
                if not MECHANISM_PROMISE_RE.search(seg):
                    continue
                tok = VIA_TOKEN_RE.search(seg)
                token = tok.group(1).strip() if tok else ""
                if not token or _mechanism_claimed(token, duty_texts):
                    continue
                errors.append(
                    f"{project}: the strategy promises "
                    f"\"{seg.strip().strip('\",[]{} ')[:140]}\" but NO unit "
                    f"schedules the duty that INSTALLS the mechanism '{token}' (declare it "
                    "as a dependency + boot/wiring duty of the correlation, wiring or "
                    "config unit - the mechanism's concrete shape comes from the active "
                    "tech-stack skill). Manual discipline is not the promised mechanism: "
                    "a future line that forgets the hand-pass silently loses it. If the "
                    "plan will not install it, amend the promise to what the plan actually "
                    "ships instead of emitting the mismatch")
        # (u) THE FLOOR MUST COVER EVERY ACKNOWLEDGED OUTCOME: step logs pair with a
        #     metric (or an explicit uncounted_steps exemption), and failure/drop
        #     vocabulary tabled in `semantics` pairs with a counting meter (or a
        #     declared uncounted-failures posture) - 2026-11-16 PART III G4: the
        #     subscriber swallowed per-event errors after the FAILED audit; the failures
        #     were durable in the store, invisible in the counters, and the floor was
        #     'complete' because it only checked that promised meters were claimed.
        try:
            strat = json.loads(stext) if stext else {}
        except json.JSONDecodeError:
            strat = {}
        obs = strat.get("observability") if isinstance(strat, dict) else None
        steps = (obs or {}).get("step_logs") if isinstance(obs, dict) else None
        metrics = (obs or {}).get("metrics") if isinstance(obs, dict) else None
        if isinstance(steps, list) and isinstance(metrics, list) and steps and metrics:
            exempt = set()
            for entry in (obs.get("uncounted_steps") or []):
                exempt.add(_surface_norm(entry if isinstance(entry, str)
                                         else (entry or {}).get("step")))
            for step in steps:
                if (isinstance(step, str) and step.strip()
                        and _surface_norm(step) not in exempt
                        and not _meter_pairs(step, metrics)):
                    errors.append(
                        f"{project}: strategy step log '{step}' marks a boundary nobody "
                        "counts - no metric name or tag pairs with it. Add a meter for "
                        "that step (or group it under one that counts it) or record an "
                        "explicit `uncounted_steps` entry with its reason: an uncounted "
                        "outcome is visible only to whoever queries the store by hand "
                        "(2026-11-16 G4: broadcast/windowed steps promised, never metered)")
        # Layer 2: failure vocabulary TABLED IN `semantics` (the (m) contract surface)
        # must be answered by the floor: a metric entry whose name/tags spell the
        # failure class, an owning unit intent claiming the paired meter, or a declared
        # `uncounted_failures` posture. Intents alone never TRIGGER (their operational
        # prose mentions errors constantly); the trigger is the contracted outcome.
        if isinstance(metrics, list) and metrics:
            sem_texts = []
            for u in live:
                if u.get("stage") not in (1, 2):
                    continue
                for member in (u.get("ast_hints") or {}).get("methods") or []:
                    if isinstance(member, dict) and member.get("semantics"):
                        sem_texts.append(str(member["semantics"]))
            if (any(FAIL_OUTCOME_RE.search(s) for s in sem_texts)
                    and not FAIL_OUTCOME_RE.search(
                        json.dumps(metrics) + str(obs.get("uncounted_failures", "")))
                    and not any(METER_CLAIM_RE.search(str(u.get("intent", "")))
                                for u in live if u.get("stage") == 2)):
                errors.append(
                    f"{project}: the plan contracts failure/drop outcomes in tabled "
                    "`semantics` (dropped, failed, rejected, swallowed, overflowed paths) "
                    "but NO meter in the strategy floor counts them, no unit claims the "
                    "paired counter, and no posture declares failures intentionally "
                    "uncounted: an audited failure without a paired counter shows in the "
                    "store yet stays invisible on every operational surface (2026-11-16 "
                    "G4: the subscriber swallowed per-event errors after the FAILED audit "
                    "- zero counters, a healthy-looking dashboard). Add a drop/rejection "
                    "counter to the floor and claim it in the owning unit, or record "
                    "`uncounted_failures` with its reason")
    return errors
