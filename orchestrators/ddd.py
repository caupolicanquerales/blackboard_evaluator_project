"""DDD artifact gates: validate discovery files, context maps, strategies, security specs.

The reports themselves are produced by the specialist agents; these gates decide
whether a phase may be skipped and whether one finished cleanly.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

import settings


SECURITY_SPEC_PREFIX = "security-spec-"
STRATEGY_PREFIX = "execution-strategy-"
# Phase 1's inbound-surface table (the security step's join key). The architect writes it,
# the spec copies `name` VERBATIM into `authorization_matrix[].surface`, and the
# decomposition wires the unit that enforces the row to the unit that IS the surface.
# A surface the plan never names cannot get a row, and a row with no surface is invention.
SURFACE_KEYS = ("name", "kind", "context", "operations")
SURFACE_OPTIONAL_KEYS = ("traced_from",)
SURFACE_KINDS = ("http", "consumer", "job", "cli", "internal-call")
# A `principals[].source` may cite an entry of the slice (the law) or, on boards written
# before the trace was machine-checked, the NAME of the section it came from.
SECURITY_SOURCE_SECTIONS = ("actors", "external_systems", "external system", "context-map",
                            "cross_boundary_flows", "principals", "relationships")

# The spec's own key list (the skill's references/security-spec.schema.json is the same
# contract in data form): a missing surface is an unasked question, not an empty table the
# next agent reads as "none needed".
SECURITY_SPEC_KEYS = ("schema_version", "report_type", "slug", "metadata", "assumptions",
                     "trust_boundaries", "principals", "data_classification",
                     "authorization_matrix", "invariants", "secrets", "error_policy",
                     "duties", "risks", "open_questions")
SECURITY_ID_SECTIONS = ("assumptions", "trust_boundaries", "principals", "data_classification",
                        "authorization_matrix", "invariants", "risks")
SECURITY_VISIBILITY_FIELDS = ("log_visibility", "error_visibility", "export_visibility")
SECURITY_CAPABILITY_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+){0,3}$")
SECURITY_LAYER_WORDS = ("interface", "application", "domain", "infrastructure")
SECURITY_UNIT_KINDS = ("policy-port", "policy-adapter", "ownership-predicate", "validator",
                       "redaction", "audit-event", "credential-handling", "key-custody",
                       "classification-rule")
# A risk is discharged by a control this spec declares, OR accepted on the record - never left
# hanging. `RISK_ACCEPTED_PREFIXES` is the explicit form of "we will not mitigate this here": legal,
# but it must state its residual, and the pipeline prints it. An unbacked risk is the one finding a
# green run forgets, because nothing downstream is required to claim it.
RISK_ACCEPTED_PREFIXES = ("accepted", "none", "operator", "out-of-scope", "not-applicable")
# "Stack-agnostic" is only real if something checks it. The words below name a REALIZATION -
# a product, a library, an annotation, a file, a package path, a task id, an engine folder -
# and every one of them belongs to the architect (with the tech-stack skill) or to the
# container, never to this artifact. Ordinary English stays legal, so the list holds
# unambiguous proper nouns only: no "passport" (a traveller's document is PII), no "flask"
# (lab glassware is an asset), no "queue" (a buffer is a domain concept), no "react" or
# "angular" (verbs and adjectives first).
SECURITY_LEAK_WORDS = (
    "spring", "springboot", "spring-security", "springframework", "hibernate", "shiro",
    "keycloak", "passport-jwt", "passport-http", "fastify", "django", "gorilla-mux", "jsonwebtoken",
    "nestjs", "fastapi", "flyway", "liquibase", "logback", "log4j", "slf4j", "micrometer",
    "hashicorp", "istio", "envoy proxy", "tomcat", "undertow", "netty", "okhttp", "axios",
    "jackson", "gson", "serde", "webpack",
    # the performance/AI tiers' vocabularies (2026-11-19): the same law - a spec that names
    # a realization has decided the architect's job. Ambiguous common nouns stay OUT of the
    # list by doctrine (no "celery", no "prometheus", no "transformers").
    "hikaricp", "resilience4j", "langchain", "langgraph", "litellm", "vllm", "ollama",
    "openai", "anthropic", "pgvector", "pinecone", "weaviate", "memcached", "redis",
    "kafka", "rabbitmq", "sidekiq",
)
SECURITY_LEAK_RE = re.compile(
    r"\b(?:" + "|".join(SECURITY_LEAK_WORDS) + r")\b"
    # an annotation or decorator is a realization by shape, wherever it appears
    + r"|(?:^|(?<=\s))@[A-Za-z][\w.]*"
    # a framework-suffixed class name (UserController, BearerTokenFilter)
    + r"|\b[A-Z][A-Za-z0-9]*(?:Controller|Filter|Middleware|Interceptor|Decorator|Provider|"
      r"Guard|Bean|Repository|Strategy)\b"
    # a file name, a package path, a task id, or a board folder
    + r"|\b[\w.-]+\.(?:java|kt|kts|py|ts|tsx|js|jsx|go|rs|ya?ml|properties|toml|ini|sql|xml|json)\b"
    + r"|\b(?:[a-z][a-z0-9]*\.){2,}[a-z][a-z0-9]*\b"
    + r"|\bT[0-4]-\d{3}\b"
    # a stage NUMBER is a scheduling decision; the word "stage" in prose is not
    + r"|\bstage\s*[0-4]\b"
    # an agent name is a handoff to a session, not a requirement (metadata.agent is exempt)
    + r"|\bagent-(?:container|architect|coder|tester|evaluator|assembly|database|security|"
      r"performance|ai)\b"
    + r"|\b(?:blackboard|red-phase|coder-changes|ast-context|gate-cache|weave-results|"
      r"execution-strategy)\b", re.I)


def _security_strings(value, path=""):
    """Every string in a nested artifact, with its JSON path for the refusal message."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _security_strings(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for position, item in enumerate(value):
            yield from _security_strings(item, f"{path}[{position}]")
    elif isinstance(value, str):
        yield path or "$", value


def database_slugs():
    """Slugs of every execution strategy the architect wrote, in stable order."""
    return sorted(
        file.stem.removeprefix("execution-strategy-")
        for file in settings.COMPLETE_DIR.glob("execution-strategy-*.json")
    )


def security_spec_path(slug):
    """Board location of one domain's security spec (the security architect's artifact)."""
    return settings.COMPLETE_DIR / f"{SECURITY_SPEC_PREFIX}{slug}.json"


def strategy_path(slug):
    """Board location of one domain's execution strategy (phase 1's artifact)."""
    return settings.COMPLETE_DIR / f"{STRATEGY_PREFIX}{slug}.json"


def _read_json(path):
    """Parsed JSON object at `path`, or None when absent/unreadable/not an object: a
    missing input makes a cross-artifact check inapplicable, never a false refusal."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def strategy_for(slug):
    """The domain's execution strategy, or None when phase 1 never wrote a readable one."""
    return _read_json(strategy_path(slug))


def norm_surface(text):
    """Comparison form of a surface name: case, punctuation and spacing are not identity."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).split())


def strategy_surfaces(slug):
    """Phase 1's declared inbound surfaces: the list (possibly empty), or None when no
    strategy is readable. `[]` and `None` mean different things to the gates: an empty
    table is a strategy that names no surface (refused at phase 1), an absent strategy is
    a board that never went through phase 1 (judged by what it can answer)."""
    strategy = strategy_for(slug)
    if strategy is None:
        return None
    surfaces = strategy.get("surfaces")
    return surfaces if isinstance(surfaces, list) else []


def _risk_is_accepted(mitigation):
    """True when a risk is closed by an explicit accepted posture rather than by a control."""
    return str(mitigation or "").strip().lower().startswith(RISK_ACCEPTED_PREFIXES)


def security_risks(slug):
    """The spec's risk register, [] when absent or malformed.

    The pipeline prints every entry: a risk that is only WRITTEN DOWN is a risk nobody read, and the
    whole point of the security phase is that nothing lawful in it stays invisible to the phases
    behind it (the same reason `open_questions` now stops the run instead of filing away)."""
    spec = _read_json(security_spec_path(slug))
    if spec is None:
        return []
    risks = spec.get("risks")
    return [entry for entry in risks if isinstance(entry, dict)] if isinstance(risks, list) else []


def _security_risk_errors(spec, declared):
    """Every risk cites a control this spec declares, or owns its exposure out loud.

    `mitigation` is the field that ties a finding back to a rule, and until now nothing resolved it:
    only `duties[].spec_ref` was required to point at a declared entry, so a risk could dangle off
    the edge of the artifact - invisible to duty closure, invisible to the claim gate, invisible to
    the drain. Accepting a risk is legal (it is the posture rule's own "never weaken a control to fit
    an implementation: record the conflict" branch), but it must be marked as accepted and state what
    stays exposed, so the run reports the exposure instead of reading as defended.
    """
    problems = []
    for entry in [risk for risk in (spec.get("risks") or []) if isinstance(risk, dict)]:
        rid = str(entry.get("id", "R-??"))
        mitigation = str(entry.get("mitigation", "")).strip()
        residual = str(entry.get("residual", "")).strip()
        if not mitigation:
            problems.append(f"{rid}: neither a mitigation naming a control in this spec nor an "
                            "accepted posture - a risk with nothing behind it is a finding this run "
                            "will forget")
            continue
        if _risk_is_accepted(mitigation):
            if not residual:
                problems.append(f"{rid}: an accepted posture must state what remains exposed "
                                "(`residual`) - the pipeline prints it; silence is not acceptance")
            continue
        if not any(re.search(r"\b" + re.escape(entry_id) + r"\b", mitigation) for entry_id in declared):
            problems.append(f"{rid}: mitigation {mitigation[:80]!r} cites no entry this spec declares "
                            "and is not an accepted posture (accepted: / none: / operator: with a "
                            "residual) - name the control or own the exposure")
    return problems


def security_open_questions(slug):
    """The spec's unanswered questions. Nothing in the spec author's session can answer
    them (they name an input that was never written), so no gate refuses on them: the
    pipeline routes them back to phase 1 instead of letting them be filed away."""
    spec = _read_json(security_spec_path(slug))
    if spec is None:
        return []
    questions = spec.get("open_questions")
    return [str(question).strip() for question in questions if str(question).strip()] \
        if isinstance(questions, list) else []


def validate_strategy(slug):
    """Gate for one domain's phase-1 strategy - the security step's only INPUT.

    Existence was all the pipeline ever checked here, so an underspecified plan flowed
    straight into the security phase: a strategy whose `modules` name the service and no
    inbound surface leaves the spec nothing to table a permission row from, and rule (y)
    later discharges only the duties that spec happens to contain. The hole is upstream of
    every downstream gate, so it is closed upstream:

    (1) the strategy declares a `surfaces` table - one entry per inbound surface, kind from
        a closed set, operations non-empty; a context that receives nothing from outside is
        declared in `contexts_without_inbound` WITH a reason (the same
        `uncounted_steps` idiom: the decision must be visible, silence is not a decision);
    (2) every surface belongs to a declared bounded context, by exact name;
    (3) every declared bounded context appears in one table or the other - a context that
        is neither surfaced nor exempted is a surface nobody will ever defend.
    """
    path = strategy_path(slug)
    if not path.is_file():
        return None  # phase-1 existence is the caller's post-check; nothing to judge
    strategy = _read_json(path)
    if strategy is None:
        return f"{path.name} is not readable JSON"
    contexts = [str(name).strip() for name in (strategy.get("bounded_contexts") or [])
                if str(name).strip()] if isinstance(strategy.get("bounded_contexts"), list) else []
    surfaces = strategy.get("surfaces")
    exempt = strategy.get("contexts_without_inbound")
    if not isinstance(surfaces, list):
        return (f"{path.name} declares no `surfaces` array: the security step tables ONE "
                "authorization row per inbound surface and classifies what those surfaces "
                "carry, so a strategy that names only modules and packages hides exactly the "
                "surfaces that need permissions - add `surfaces` (name, kind, context, "
                "operations) for every inbound surface, or `contexts_without_inbound` with a "
                "reason for a context that receives nothing from outside")
    problems = []
    if not contexts:
        problems.append(
            f"{path.name} declares no `bounded_contexts`: surfaces, principals and invariant "
            "owners bind to a context by exact name, and without that list the security step "
            "has nothing to attach a permission to (the slice names them - copy them)")
    seen = set()
    for position, surface in enumerate(surfaces, start=1):
        label = f"surfaces[{position}]"
        if not isinstance(surface, dict):
            problems.append(f"{label} must be an object")
            continue
        missing = [key for key in SURFACE_KEYS if not str(surface.get(key) or "").strip()
                   and not (key == "operations" and surface.get("operations"))]
        if missing:
            problems.append(f"{label} is missing or empty: {missing} "
                            f"(required keys {list(SURFACE_KEYS)})")
            continue
        unexpected = sorted(set(surface) - set(SURFACE_KEYS) - set(SURFACE_OPTIONAL_KEYS))
        if unexpected:
            problems.append(f"{label} has unsupported key(s) {unexpected}")
        name = norm_surface(surface["name"])
        if name in seen:
            problems.append(f"{label}: surface name {surface['name']!r} is declared twice - "
                            "one row per inbound surface, so one entry per name")
        seen.add(name)
        if str(surface["kind"]).strip() not in SURFACE_KINDS:
            problems.append(f"{label}: kind {surface['kind']!r} must be one of "
                            f"{list(SURFACE_KINDS)}")
        if contexts and str(surface["context"]).strip() not in contexts:
            problems.append(f"{label}: context {surface['context']!r} is not one of the "
                            f"strategy's bounded_contexts {contexts}")
        if not isinstance(surface["operations"], list) or not surface["operations"]:
            problems.append(f"{label}.operations must be a non-empty list "
                            "(GET, POST, consume, schedule, cli, internal-call, ...)")
    covered = {norm_surface(surface.get("context")) for surface in surfaces
               if isinstance(surface, dict)}
    covered |= {norm_surface((entry or {}).get("context") if isinstance(entry, dict) else entry)
                for entry in (exempt if isinstance(exempt, list) else [])}
    for context in contexts:
        if norm_surface(context) not in covered:
            problems.append(f"bounded context {context!r} declares no inbound surface and no "
                            "`contexts_without_inbound` reason: a context nobody surfaced "
                            "gets no authorization row, and an undefended surface is found "
                            "by its first caller, not by this run")
    if problems:
        return "; ".join(problems)
    return None


def _security_entry_ids(spec):
    """Every id the spec declares, section entries plus the secrets inventory."""
    ids = set()
    for section in SECURITY_ID_SECTIONS:
        for entry in spec.get(section) or []:
            if isinstance(entry, dict) and str(entry.get("id", "")).strip():
                ids.add(str(entry["id"]).strip())
    for entry in _secret_inventory(spec):
        if isinstance(entry, dict) and str(entry.get("id", "")).strip():
            ids.add(str(entry["id"]).strip())
    return ids


def _secret_inventory(spec):
    """The secrets inventory list, or [] when the section is absent or malformed (a
    hostile artifact must never crash the gate that is judging it)."""
    secrets = spec.get("secrets")
    entries = secrets.get("inventory") if isinstance(secrets, dict) else None
    return entries if isinstance(entries, list) else []


def _security_leaks(spec):
    """Realization vocabulary anywhere in the DESIGN content, as (json path, matched token).

    `metadata` is exempt: it is provenance - the timestamp, the authoring agent, and the
    board files that were read. Naming `execution-strategy-<slug>.json` there is a citation,
    not a design decision; the law being enforced is that no REQUIREMENT may name a
    realization (a product, an annotation, a class suffix, a file, a package path, a task id,
    a board folder), and an over-broad scan would refuse honest artifacts while teaching the
    agent to hide its inputs.
    """
    found = []
    for key, section in spec.items():
        if key == "metadata":
            continue
        for location, text in _security_strings(section, key):
            match = SECURITY_LEAK_RE.search(text)
            if match:
                found.append((location, match.group(0)))
    return found


def _security_capability_errors(spec):
    """Every capability token must look like a capability: lowercase kebab, 1-4 words."""
    problems = []
    for duty in (spec.get("duties") or []):
        if not isinstance(duty, dict):
            continue
        token = str(duty.get("capability", "")).strip()
        if not SECURITY_CAPABILITY_RE.match(token):
            problems.append(f"duty {duty.get('spec_ref', '?')}: capability {token!r} is not an "
                            f"abstract token (lowercase kebab, one to four words)")
        kind = str(duty.get("unit_kind", "")).strip()
        if kind not in SECURITY_UNIT_KINDS:
            problems.append(f"duty {duty.get('spec_ref', '?')}: unit_kind {kind!r} must be one of "
                            f"{list(SECURITY_UNIT_KINDS)}")
    for entry in (spec.get("invariants") or []):
        if isinstance(entry, dict):
            token = str(entry.get("capability", "")).strip()
            if not SECURITY_CAPABILITY_RE.match(token):
                problems.append(f"invariant {entry.get('id', '?')}: capability {token!r} is not an "
                                "abstract token (lowercase kebab, one to four words)")
    return problems


def _security_strategy_errors(slug, spec, rows):
    """Spec-vs-strategy completeness (Gap A, 2026-11-18): the spec gate used to judge its
    artifact in isolation, so a lawful table could cover a fraction of the plan.

    `validate_security_spec` refused an EMPTY matrix, which is not the same law as the
    skill's ("One matrix row each, no row omitted"): a domain with four inbound surfaces
    and one row passed, the decomposition discharged the one row's duty, and the other
    three surfaces shipped with no permission table at all. Every check below is a join
    against phase 1's `surfaces` table, and every check is skipped when the strategy is
    absent (a board that never ran phase 1 cannot be demanded to have surfaced anything).
    """
    surfaces = strategy_surfaces(slug)
    if not surfaces:
        return []
    strategy = strategy_for(slug) or {}
    problems = []
    row_texts = [norm_surface(row.get("surface")) for row in rows]
    for position, surface in enumerate(surfaces, start=1):
        if not isinstance(surface, dict):
            continue
        name = norm_surface(surface.get("name"))
        if not name:
            continue
        if not any(name in text or text in name for text in row_texts if text):
            problems.append(
                f"surfaces[{position}] {surface.get('name')!r} is an inbound surface phase 1 "
                "declared and the authorization_matrix tables NO row for it - copy the "
                "strategy's surface name into a row's `surface` and give it its own "
                "principal, ownership rule, decision point, effect and test duty: a surface "
                "with no row has no rule, and no rule means the default is whatever the "
                "framework does when nobody configured it")
    contexts = [str(name).strip() for name in (strategy.get("bounded_contexts") or [])
                if str(name).strip()] if isinstance(strategy.get("bounded_contexts"), list) else []
    if contexts:
        for entry in [e for e in (spec.get("invariants") or []) if isinstance(e, dict)]:
            owner = str(entry.get("owner_context") or "").strip()
            if owner and owner not in contexts:
                problems.append(f"{entry.get('id', 'SI-??')}: owner_context {owner!r} is not one "
                                f"of the strategy's bounded_contexts {contexts} - a rule owned "
                                "by no context is enforced by no module")
    slice_report = _read_json(settings.DOMAIN_DIR / f"domain-boundary-{slug}.json")
    if slice_report is not None:
        haystack = norm_surface(json.dumps(slice_report))
        for entry in [e for e in (spec.get("principals") or []) if isinstance(e, dict)]:
            source = str(entry.get("source") or "").strip()
            if not source or source.lower() in SECURITY_SOURCE_SECTIONS:
                continue
            if norm_surface(source) not in haystack:
                problems.append(
                    f"{entry.get('id', 'P-??')}: principal source {source!r} traces to no "
                    "entry of the domain slice - an entrant the inputs never declared is an "
                    "invention; name the `actors`/`external_systems` entry verbatim or move "
                    "the question to `open_questions`")
    persistence = strategy.get("persistence")
    data_model = persistence.get("data_model") if isinstance(persistence, dict) else None
    if str(data_model or "").strip() and not (spec.get("data_classification") or []):
        problems.append(
            "data_classification is empty while the strategy's `persistence.data_model` "
            "declares persisted concepts - nothing in the plan is then classified, so log "
            "redaction, error bodies and exports have no rule to follow and every field is "
            "public by default")
    return problems


def validate_security_spec(slug):
    """Gate for one domain's security spec. None when the artifact is parseable and lawful.

    Six laws live here: four the artifact must satisfy ALONE (no later per-unit gate can
    see them), one that joins it back to phase 1, and one that closes the risk register:
    (1) LANGUAGE SEPARATION - the artifact states requirements, never realizations. A
        framework or library name, an annotation, a framework-suffixed class, a file name, a
        package path, a task id or a board folder in any string means the security step
        decided the architect's job; the leak is reported at its exact JSON path;
    (2) DUTY CLOSURE - every authorization row and every invariant is discharged by at least
        one duty, and every duty `spec_ref` resolves. A rule with no owning unit is prose,
        the same failure class the step-log claim gate killed for observability;
    (3) the IDOR law - a row addressed by client-supplied identifiers states an ownership
        predicate or declares the resource public;
    (4) the disclosure law - `restricted` data is forbidden in logs, errors and exports.
    An absent file is a reason, never a pass: the pipeline asks this gate whether the
    security phase ran at all.
    """
    path = security_spec_path(slug)
    if not path.is_file():
        # str(path) when the board is patched outside the repository root (gauntlet
        # fixtures): relative_to would raise, and a gate that crashes is not a gate.
        try:
            shown = str(path.relative_to(settings.ROOT))
        except ValueError:
            shown = str(path)
        return f"security spec not found: {shown}"
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"{path.name} is not valid JSON: {exc}"
    if not isinstance(spec, dict):
        return f"{path.name} must be a JSON object"
    problems = []
    if spec.get("report_type") != "security-spec":
        problems.append(f"report_type must be 'security-spec', found {spec.get('report_type')!r}")
    if spec.get("slug") != slug:
        problems.append(f"slug must be {slug!r}, found {spec.get('slug')!r}")
    missing = [key for key in SECURITY_SPEC_KEYS if key not in spec]
    if missing:
        problems.append(f"missing keys {missing}")
    leaks = _security_leaks(spec)
    if leaks:
        for location, token in leaks[:6]:
            problems.append(f"{location}: names {token!r}, a REALIZATION - keep the requirement "
                            "and its capability token; the architect maps tokens to mechanisms "
                            "with the tech-stack skill")
        if len(leaks) > 6:
            problems.append(f"... and {len(leaks) - 6} more realization names")
    rows = [row for row in (spec.get("authorization_matrix") or []) if isinstance(row, dict)]
    if not rows:
        problems.append("authorization_matrix is empty: every inbound surface needs exactly one row")
    principals = {str(entry.get("id")).strip() for entry in (spec.get("principals") or [])
                  if isinstance(entry, dict) and str(entry.get("id", "")).strip()}
    for row in rows:
        rid = str(row.get("id", "?"))
        if row.get("default") != "deny":
            problems.append(f"{rid}: default must be 'deny' (deny-by-default is the posture, not a choice)")
        if not str(row.get("test_duty", "")).strip():
            problems.append(f"{rid}: no test_duty - an untested permission rule is a rule nobody proves")
        point = row.get("decision_point")
        if not isinstance(point, dict) or not point:
            problems.append(f"{rid}: no decision_point naming the layer and component that enforce it")
        elif str(point.get("layer", "")).strip() not in SECURITY_LAYER_WORDS:
            problems.append(f"{rid}: decision_point.layer {point.get('layer')!r} must be one of "
                            f"{list(SECURITY_LAYER_WORDS)} (an architectural layer, never a file)")
        clients = row.get("client_supplied_ids") or []
        if clients and str(row.get("ownership_rule", "none")) == "none":
            problems.append(f"{rid}: addresses client-supplied ids {clients} with ownership_rule 'none' "
                            "- the IDOR hole: name the tenant/owner predicate or declare the resource public")
        for pid in row.get("principal_ids") or []:
            if str(pid).strip() not in principals:
                problems.append(f"{rid}: principal {pid!r} is declared by no principals entry")
    for entry in [e for e in (spec.get("data_classification") or []) if isinstance(e, dict)]:
        if entry.get("class") == "restricted":
            loose = [field for field in SECURITY_VISIBILITY_FIELDS
                     if entry.get(field) != "forbidden"]
            if loose:
                problems.append(f"{entry.get('id', '?')}: class 'restricted' but {loose} are not "
                                "'forbidden' - a secret in a log line or error body is a disclosure")
    problems.extend(_security_capability_errors(spec))
    declared = _security_entry_ids(spec)
    claimed = set()
    duties = [duty for duty in (spec.get("duties") or []) if isinstance(duty, dict)]
    if not duties:
        problems.append("duties is empty: nothing in the spec reaches a scheduled unit")
    for duty in duties:
        ref = str(duty.get("spec_ref", "")).strip()
        if ref not in declared:
            problems.append(f"duty {ref or '?'}: spec_ref resolves to no entry in this spec")
        claimed.add(ref)
    for rule in rows + [e for e in (spec.get("invariants") or []) if isinstance(e, dict)]:
        rid = str(rule.get("id", "")).strip()
        if rid and rid not in claimed:
            problems.append(f"{rid}: rule with no owning duty - a rule nobody schedules is prose, "
                            "and the decomposition is refused until one unit claims it")
    problems.extend(_security_risk_errors(spec, declared))
    problems.extend(_security_strategy_errors(slug, spec, rows))
    if problems:
        return "; ".join(problems)
    return None


# The duties handoff is read where it is acted on: `task_queue.security_claim_gaps` reports the
# spec duties no live unit claims (the emit gate's own reading), so the pipeline can stop on a
# plan that predates its spec instead of hinting over it. No second duty reader exists.

def security_spec_slugs():
    """Every domain that already has a security spec, in stable order."""
    return sorted(path.name.removeprefix(SECURITY_SPEC_PREFIX).removesuffix(".json")
                  for path in settings.COMPLETE_DIR.glob(f"{SECURITY_SPEC_PREFIX}*.json"))


# =====================================================================================
# THE PERFORMANCE AND AI SPECS (2026-11-19). Two more stack-agnostic planning phases
# between the strategy and the decomposition, cloned from the security step's contract
# because that contract is what keeps a specialist honest: abstract capability tokens
# keyed VERBATIM to phase 1's tables; every rule discharged by a duty; realization
# vocabulary refused at the gate; open questions stop the run; the author never grades
# itself - the engine does. Where they differ from security is decided BY THE DOMAIN:
#   * performance is the unconditional floor (every executable context has a load side,
#     like the observability floor: silence is not a decision, an exemption is);
#   * the AI phase runs only on a VERBATIM directive in the business description (an
#     AI capability is a product decision the discovery step transcribes and the engine
#     re-reads against the description file - never an agent's inference);
#   * BOTH carry a measurement law (the R5 lesson): a duty that can only be proven by a
#     wall clock or a live external call is not a stage-1 contract. The closed
#     measurement-kind enums are the machine form of "deterministic or unclaimed".
PERFORMANCE_SPEC_PREFIX = "performance-spec-"
AI_SPEC_PREFIX = "ai-spec-"
PERFORMANCE_SPEC_KEYS = ("schema_version", "report_type", "slug", "metadata", "assumptions",
                         "workload", "budgets", "invariants", "duties", "risks",
                         "open_questions")
AI_SPEC_KEYS = ("schema_version", "report_type", "slug", "metadata", "assumptions",
                "model_roles", "capabilities", "invariants", "duties", "risks",
                "open_questions")
# Deterministic proof surfaces only: every kind names something a stage-1 test can count
# or read without a clock. A limit that survives only as "must be fast" is the wall-clock
# flake waiting to happen in CI - the enum has NO timing member, and the refusal says so.
PERFORMANCE_MEASUREMENT_KINDS = ("query-count", "config-key", "status-code", "payload-size",
                                 "queue-depth", "deterministic-count")
AI_MEASUREMENT_KINDS = ("stub-call-count", "schema-validation", "config-key", "status-code",
                        "payload-size", "deterministic-count")
PERFORMANCE_UNIT_KINDS = ("admission-control", "rate-limit-policy", "concurrency-guard",
                          "cache-policy", "retry-policy", "pagination-rule",
                          "resource-ceiling", "batch-policy", "timeout-policy",
                          "budget-observer")
AI_UNIT_KINDS = ("model-port-adapter", "prompt-contract", "output-validator",
                 "context-budget", "fallback-policy", "retrieval-adapter", "tool-guard",
                 "eval-harness", "memory-adapter", "offline-stub",
                 # homes for the multi-agent trio and the delivery shape:
                 "orchestration-router", "loop-governor", "approval-gate", "stream-delivery")
# The AI capability vocabulary is CLOSED on purpose (the user's base set): an invented
# token is a capability no stack table can map, and the mapping tables carry rows for
# exactly these - a token outside the set means the spec decided something the architect
# has no lawful channel to realize.
AI_CAPABILITY_TOKENS = ("prompt-contract", "structured-output-guard", "context-budget-cap",
                        "fallback-model-route", "retrieval-scope-guard", "tool-call-guard",
                        "eval-golden-set", "memory-boundary", "offline-model-port",
                        "token-cost-cap",
                        # the multi-agent trio (2026-11-19 operator review): a single-agent
                        # vocabulary silently permits an unbounded autonomous loop - each
                        # call valid and small, the cycle infinite. Delegation, termination
                        # and human custody are separate closed duties, not folklore:
                        "agent-handoff", "loop-budget-cap", "human-approval-gate",
                        # the DELIVERY-SHAPE token (2026-11-19 operator review): whether a flow
                        # holds a request-response connection or pushes incremental events is an
                        # architecture decision the spec must make visible to phase 2 - named
                        # transport-free (SSE/WebSockets/queues are the stack table's choice):
                        "incremental-progress-stream")
AI_STATEFULNESS = ("none", "session", "durable")
# Memory TECHNIQUE (2026-11-19 operator review): statefulness names the tier, the technique
# names how history is kept under the tier - window, compaction, or semantic recall. A
# memory decision without a technique leaves context-budget-cap unpairable (what gets
# truncated?) and phase 2 recalling a class name. Kept as a field on model_roles, NOT a
# 15th capability token: the token vocabulary is what duties claim and tables map; the
# technique refines one existing token's (memory-boundary) obligation, and keeping it out
# of the closed set holds PF12 parity stable.
AI_MEMORY_TECHNIQUES = ("sliding-window", "rolling-summary", "semantic-episodic")
# The AI law no spec may omit: model access is a PORT with an offline stand-in, and no
# gate may reach a live endpoint. An AI plan without this invariant can always be built
# to call the world from a unit test - which is how a drain bills real tokens on CI.
AI_REQUIRED_INVARIANT = "offline-model-port"


def performance_spec_path(slug):
    return settings.COMPLETE_DIR / f"{PERFORMANCE_SPEC_PREFIX}{slug}.json"


def ai_spec_path(slug):
    return settings.COMPLETE_DIR / f"{AI_SPEC_PREFIX}{slug}.json"


def _spec_open_questions(path):
    spec = _read_json(path)
    if spec is None:
        return []
    questions = spec.get("open_questions")
    return [str(question).strip() for question in questions if str(question).strip()] \
        if isinstance(questions, list) else []


def performance_open_questions(slug):
    return _spec_open_questions(performance_spec_path(slug))


def ai_open_questions(slug):
    return _spec_open_questions(ai_spec_path(slug))


def _spec_risks(path):
    spec = _read_json(path)
    if spec is None:
        return []
    risks = spec.get("risks")
    return [entry for entry in risks if isinstance(entry, dict)] if isinstance(risks, list) else []


def performance_risks(slug):
    return _spec_risks(performance_spec_path(slug))


def ai_risks(slug):
    return _spec_risks(ai_spec_path(slug))


def _spec_shell_errors(spec, slug, expect_type, keys):
    problems = []
    if spec.get("report_type") != expect_type:
        problems.append(f"report_type must be {expect_type!r}, found {spec.get('report_type')!r}")
    if spec.get("slug") != slug:
        problems.append(f"slug must be {slug!r}, found {spec.get('slug')!r}")
    missing = [key for key in keys if key not in spec]
    if missing:
        problems.append(f"missing keys {missing}")
    for location, token in _security_leaks(spec)[:6]:
        problems.append(f"{location}: names {token!r}, a REALIZATION - keep the requirement "
                        "and its capability token; the architect maps tokens to mechanisms "
                        "with the tech-stack skill")
    return problems


def _duty_closure_errors(spec, declared):
    problems = []
    duties = [duty for duty in (spec.get("duties") or []) if isinstance(duty, dict)]
    if not duties:
        problems.append("duties is empty: nothing in the spec reaches a scheduled unit")
    claimed = set()
    for duty in duties:
        ref = str(duty.get("spec_ref", "")).strip()
        if ref not in declared:
            problems.append(f"duty {ref or '?'}: spec_ref resolves to no entry in this spec")
        claimed.add(ref)
        token = str(duty.get("capability", "")).strip()
        if not SECURITY_CAPABILITY_RE.match(token):
            problems.append(f"duty {ref or '?'}: capability {token!r} is not an abstract token "
                            "(lowercase kebab, one to four words)")
    return problems, claimed


def _measurement_errors(entries, kinds, what):
    problems = []
    for entry in entries:
        eid = str(entry.get("id", "?"))
        measurement = entry.get("measurement")
        kind = str((measurement or {}).get("kind") or "").strip() if isinstance(measurement, dict) else ""
        assertion = str((measurement or {}).get("assertion") or "").strip() if isinstance(measurement, dict) else ""
        if not kind or not assertion:
            problems.append(f"{eid}: {what} needs a measurement {{kind, assertion}} - a rule "
                            "with no deterministic proof is a wish, not a contract")
            continue
        if kind not in kinds:
            timing = re.search(r"(ms|millis|second|latency|p9[59]|wall|duration|slow|fast)",
                               kind, re.I)
            problems.append(
                f"{eid}: measurement.kind {kind!r} is not one of {list(kinds)}"
                + (" - and no clock kind exists ON PURPOSE: a wall-clock assertion flakes in "
                   "CI and proves nothing a stage-1 gate can enforce; express the limit as a "
                   "count, a bounded config key, a rejection status or a payload size"
                   if timing else ""))
    return problems


def _spec_absent(path, phase):
    try:
        shown = str(path.relative_to(settings.ROOT))
    except ValueError:
        shown = str(path)
    return f"{phase} spec not found: {shown}"


def validate_performance_spec(slug):
    """Gate for the performance spec: the load model, the budgets and their DETERMINISTIC
    proofs. Keyed VERBATIM to phase 1's `surfaces` table (the same join key the security
    row uses), with an exemption channel - a surface with no load duty is declared with a
    reason, never left silent."""
    path = performance_spec_path(slug)
    if not path.is_file():
        return _spec_absent(path, "performance")
    spec = _read_json(path)
    if spec is None:
        return f"{path.name} is not a readable JSON object"
    problems = _spec_shell_errors(spec, slug, "performance-spec", PERFORMANCE_SPEC_KEYS)
    surfaces = strategy_surfaces(slug) or []
    declared_names = {norm_surface(s.get("name")) for s in surfaces if isinstance(s, dict)}
    declared_names.discard("")
    workload = spec.get("workload") if isinstance(spec.get("workload"), dict) else {}
    entries = [e for e in (workload.get("entries") or []) if isinstance(e, dict)]
    exempt = [e for e in (workload.get("surfaces_exempt") or []) if isinstance(e, dict)]
    covered = set()
    for entry in entries + exempt:
        name = norm_surface(entry.get("surface"))
        if name and name not in declared_names:
            problems.append(f"workload {entry.get('id', entry.get('surface', '?'))}: surface "
                            f"{entry.get('surface')!r} is not a strategy `surfaces[].name` "
                            "- copy the declared name VERBATIM, or an undeclared load source "
                            "goes to open_questions (phase 1 owns the surface table)")
        covered.add(name)
    for entry in exempt:
        if not str(entry.get("reason", "")).strip():
            problems.append(f"surfaces_exempt {entry.get('surface', '?')}: an exemption with no "
                            "reason is silence wearing a table row")
    for surface in sorted(declared_names - covered):
        if surface:
            problems.append(
                f"surface {surface!r} carries NO workload entry and NO exemption - every "
                "inbound surface the strategy declares is either load-modeled or exempt on "
                "the record (the contexts_without_inbound idiom: a boundary nobody sized is "
                "sized by whatever the framework defaults to)")
    budgets = [b for b in (spec.get("budgets") or []) if isinstance(b, dict)]
    if not budgets:
        problems.append("budgets is empty: an unbounded plan is a plan that has not decided "
                        "what enough is")
    problems.extend(_measurement_errors(budgets, PERFORMANCE_MEASUREMENT_KINDS, "budget"))
    invariants = [e for e in (spec.get("invariants") or []) if isinstance(e, dict)]
    if not invariants:
        problems.append("invariants is empty: at least one load-side rule must hold ALWAYS "
                        "(e.g. no unbounded queue on any path) - budgets bound the expected, "
                        "invariants bound the worst case")
    for entry in invariants:
        token = str(entry.get("capability", "")).strip()
        if not SECURITY_CAPABILITY_RE.match(token):
            problems.append(f"invariant {entry.get('id', '?')}: capability {token!r} is not an "
                            "abstract token (lowercase kebab, one to four words)")
    declared = {str(entry.get("id")).strip()
                for section in (workload.get("entries"), budgets, invariants,
                                spec.get("assumptions"))
                for entry in (section or [])
                if isinstance(entry, dict) and str(entry.get("id", "")).strip()}
    duty_problems, claimed = _duty_closure_errors(spec, declared)
    problems.extend(duty_problems)
    for duty in (d for d in (spec.get("duties") or []) if isinstance(d, dict)):
        kind = str(duty.get("unit_kind", "")).strip()
        if kind not in PERFORMANCE_UNIT_KINDS:
            problems.append(f"duty {duty.get('spec_ref', '?')}: unit_kind {kind!r} must be "
                            f"one of {list(PERFORMANCE_UNIT_KINDS)}")
    for entry in invariants:
        rid = str(entry.get("id", "")).strip()
        if rid and rid not in claimed:
            problems.append(f"{rid}: rule with no owning duty - a load rule nobody schedules "
                            "is prose until a budget pays for it")
    for budget in budgets:
        rid = str(budget.get("id", "")).strip()
        if rid and rid not in claimed:
            problems.append(f"{rid}: budget with no owning duty - an unenforced ceiling is a "
                            "number in a document")
    problems.extend(_security_risk_errors(spec, declared))
    return "; ".join(problems) if problems else None


def validate_ai_spec(slug):
    """Gate for the AI spec: roles, capabilities and their DETERMINISTIC proofs, keyed
    VERBATIM to phase 1's surfaces / the context map's flows. Two laws security does not
    need: the capability vocabulary is CLOSED (each token has a stack-table row or the
    plan has no lawful realization), and the offline-port invariant is MANDATORY (no gate
    may ever reach a live model endpoint - a drain that bills real tokens on CI is a
    design defect, not a cost)."""
    path = ai_spec_path(slug)
    if not path.is_file():
        return _spec_absent(path, "AI")
    spec = _read_json(path)
    if spec is None:
        return f"{path.name} is not a readable JSON object"
    problems = _spec_shell_errors(spec, slug, "ai-spec", AI_SPEC_KEYS)
    surfaces = {norm_surface(s.get("name")) for s in (strategy_surfaces(slug) or [])
                if isinstance(s, dict) and str(s.get("name") or "").strip()}
    map_report = _read_json(settings.CONTEXT_MAP_DIR / f"context-map-{slug}.json")
    flows = norm_surface(json.dumps((map_report or {}).get("cross_boundary_flows") or {}))
    capabilities = [e for e in (spec.get("capabilities") or []) if isinstance(e, dict)]
    if not capabilities:
        problems.append("capabilities is empty: an AI capability no unit holds is a feature "
                        "request, not a plan")
    for entry in capabilities:
        cid = str(entry.get("id", "AC-??"))
        token = str(entry.get("capability", "")).strip()
        if token not in AI_CAPABILITY_TOKENS:
            problems.append(f"{cid}: capability {token!r} is outside the closed AI vocabulary "
                            f"{list(AI_CAPABILITY_TOKENS)} - an unmappable token has no "
                            "realization channel; describe the requirement with one of these "
                            "or move the undecided part to open_questions")
        key = norm_surface(entry.get("surface_or_flow"))
        if not key:
            problems.append(f"{cid}: surface_or_flow must name a strategy surface or a "
                            "context-map flow VERBATIM - a floating capability is claimed by no unit")
        elif key not in surfaces and key not in flows and flows.find(key) < 0:
            problems.append(f"{cid}: {entry.get('surface_or_flow')!r} matches no declared "
                            "surface and no context-map flow - name the input's entry "
                            "verbatim, or an AI behavior no input declared goes to "
                            "open_questions, never invented")
    problems.extend(_measurement_errors(capabilities, AI_MEASUREMENT_KINDS, "capability"))
    invariants = [e for e in (spec.get("invariants") or []) if isinstance(e, dict)]
    # transport-free law (2026-11-19 operator review): the DELIVERY SHAPE belongs to the
    # spec (incremental events + terminal completion, non-blocking); the TRANSPORT (SSE,
    # websockets, gRPC streams, queues) is phase 2's mapping onto the concrete surface -
    # naming it here would decide an entry adapter's protocol from the requirements tier.
    for entry in capabilities + invariants:
        text = " ".join(str(entry.get(field, "")) for field in
                        ("requirement", "rule", "measurement"))
        hit = re.search(r"\b(SSE|server[- ]sent events?|websocket\(s\)?|web socket|grpc"
                        r"|long[- ]polling|websocket)\b", text, re.I)
        if hit:
            problems.append(
                f"{entry.get('id', '?')}: names {hit.group(0)!r}, a TRANSPORT - state the "
                "delivery SHAPE (incremental events then a terminal completion, or a declared "
                "polled-completion posture); the surface's protocol is the architect's "
                "mapping-table choice, not a spec requirement")
    # roles bound to rules: AC/AM rows may name the AR ids they involve; a dangling
    # binding is the floating capability in another dress.
    role_ids = {str(e.get("id")).strip() for e in (spec.get("model_roles") or [])
                if isinstance(e, dict) and str(e.get("id", "")).strip()}
    for entry in capabilities + invariants:
        for rid in (entry.get("roles") or []):
            if str(rid).strip() not in role_ids:
                problems.append(f"{entry.get('id', '?')}: roles binds {rid!r}, which no "
                                "model_roles entry declares - an agent in the topology that "
                                "is no agent in the plan")
    # TOPOLOGY TERMINATION (2026-11-19 operator review): delegation without a cycle budget
    # is the AI class of the unbounded queue - every hop valid, the loop infinite, no
    # deterministic test that could ever catch it. A handoff edge ARMS the duty; the proof
    # channel already exists (stub-call-count).
    if any(str(e.get("capability", "")).strip() == "agent-handoff" for e in capabilities):
        if not any(str(e.get("capability", "")).strip() == "loop-budget-cap"
                   for e in invariants):
            problems.append(
                "the topology delegates (an agent-handoff capability) but NO invariant "
                "carries loop-budget-cap - a multi-agent flow without a max-turns/"
                "cycle-break bound can spin forever on individually-valid calls; declare "
                "the termination bound (measured by stub-call-count) or remove the edge")
    if any(str(e.get("capability", "")).strip() == "human-approval-gate" for e in capabilities):
        if not any(str(e.get("capability", "")).strip() == "tool-call-guard"
                   for e in capabilities):
            problems.append(
                "a human-approval-gate exists but no tool-call-guard is declared - an "
                "approval gate around nothing is ceremony: the gate guards the high-impact "
                "tools; bind them (the guarded tool is what splits into propose/execute)")
    roles = [e for e in (spec.get("model_roles") or []) if isinstance(e, dict)]
    if not roles:
        problems.append("model_roles is empty: name each model/embedding role, its "
                        "statefulness, and the data classes it may touch")
    # MEMORY TIER & TECHNIQUE laws (2026-11-19 operator review). Three of the four
    # "durable is mandatory" triggers are decidable from the artifact itself and enforced
    # here; cross-session continuity stays an author decision, made visible by the field
    # the three decidable laws read.
    role_by_id = {str(e.get("id", "")).strip(): e for e in roles}
    _approval = [e for e in capabilities
                 if str(e.get("capability", "")).strip() == "human-approval-gate"]
    for entry in _approval:
        for rid in (entry.get("roles") or []):
            role = role_by_id.get(str(rid).strip())
            if role is not None and str(role.get("statefulness", "")).strip() != "durable":
                problems.append(
                    f"{entry.get('id', 'AC-??')}: the approval gate binds {rid}, whose "
                    f"statefulness is {role.get('statefulness')!r} - an `awaiting_approval` "
                    "pause that resumes through an inbound surface must outlive the process "
                    "that made it (in-memory state dies on restart or rebalancing): the "
                    "waiting role is durable by law")
    if any(str(e.get("memory_technique") or "").strip() == "semantic-episodic"
           for e in roles):
        if not any(str(e.get("capability", "")).strip() == "retrieval-scope-guard"
                   for e in capabilities):
            problems.append(
                "a role remembers semantically (semantic-episodic) but no retrieval-scope-"
                "guard capability is declared - embedded recall reaches across sessions by "
                "design; unscoped it reaches across tenants: bind every semantic memory read "
                "behind the same predicate the human path carries (or choose another "
                "technique)")

    strategy_mem = strategy_for(slug) or {}
    persistence = strategy_mem.get("persistence") if isinstance(strategy_mem, dict) else None
    data_model = str((persistence or {}).get("data_model") or "") if isinstance(persistence, dict) else ""
    for entry in roles:
        rid = str(entry.get("id", "AR-??"))
        state = str(entry.get("statefulness", "")).strip()
        tech = str(entry.get("memory_technique") or "").strip()
        if state in ("session", "durable") and tech not in AI_MEMORY_TECHNIQUES:
            problems.append(
                f"{rid}: statefulness {state!r} without a memory_technique - a tier with no "
                "compaction/retrieval rule leaves context-budget-cap unpaired (what is "
                "truncated?) and phase 2 naming a store from memory: declare one of "
                f"{list(AI_MEMORY_TECHNIQUES)}")
        if state == "none" and tech:
            problems.append(f"{rid}: statelessness declares no memory to manage - drop "
                            "memory_technique (an isolated worker receives its whole context "
                            "in the task envelope)")
        if state == "durable" and data_model.strip():
            classes = [norm_surface(d) for d in (entry.get("data_classes") or [])
                       if str(d).strip()]
            if classes and not any(c in norm_surface(data_model) for c in classes):
                problems.append(
                    f"{rid}: durable memory touches {entry.get('data_classes')}, but the "
                    "strategy's `persistence.data_model` declares no such concept - history "
                    "that must outlive the process needs a persisted concept (or the "
                    "decision goes to open_questions for phase 1 / the database step to "
                    "own: the shared-blackboard and auditability triggers both land here)")
    for entry in roles:
        state = str(entry.get("statefulness", "")).strip()
        if state not in AI_STATEFULNESS:
            problems.append(f"model role {entry.get('id', 'AR-??')}: statefulness {state!r} "
                            f"must be one of {list(AI_STATEFULNESS)} - where a model may "
                            "remember is a memory-boundary decision, never an accident")
        if not [d for d in (entry.get("data_classes") or []) if str(d).strip()]:
            problems.append(f"model role {entry.get('id', 'AR-??')}: no data_classes - a role "
                            "that may touch unnamed data touches all of it")
    if not any(str(e.get("capability", "")).strip() == AI_REQUIRED_INVARIANT
               for e in invariants):
        problems.append(
            f"no invariant carries the {AI_REQUIRED_INVARIANT!r} capability: every model/"
            "embedding access is a PORT with an offline stand-in, and no unit gate or slice "
            "may reach a live endpoint - the drain runs without network truth, and a plan "
            "that can call the world from a test will (2026-11-19 design law)")
    rule_ids = {str(entry.get("id")).strip()
                for entry in (capabilities + invariants)
                if str(entry.get("id", "")).strip()}
    context_ids = {(str(entry.get("id")).strip())
                   for entry in (roles + [e for e in (spec.get("assumptions") or [])
                                          if isinstance(e, dict)])
                   if str(entry.get("id", "")).strip()}
    # spec_ref law (the schema's "SAME closed token as the rule it discharges" made this
    # necessary): only rows that CARRY a capability - AC/AM - can be discharged. A model
    # role is a SUBJECT realized through the capabilities that bind it; an assumption is
    # the record of a decision. A duty citing them leaves "the same token" undefined, so
    # the reference space is the rule rows; roles/assumptions are cited inside the
    # obligation text, never as the duty's target.
    for duty in (d for d in (spec.get("duties") or []) if isinstance(d, dict)):
        ref = str(duty.get("spec_ref", "")).strip()
        if ref in context_ids:
            problems.append(
                f"duty {ref}: cites a model role / assumption - not a dischargeable rule "
                "(only AC-/AM- rows carry a capability to match); the role is realized by "
                "the capabilities that bind it via `roles`: name the rule that does the "
                "work and cite this context inside its obligation")
    declared = rule_ids | context_ids
    duty_problems, claimed = _duty_closure_errors(spec, rule_ids)
    problems.extend(duty_problems)
    for duty in (d for d in (spec.get("duties") or []) if isinstance(d, dict)):
        kind = str(duty.get("unit_kind", "")).strip()
        if kind not in AI_UNIT_KINDS:
            problems.append(f"duty {duty.get('spec_ref', '?')}: unit_kind {kind!r} must be "
                            f"one of {list(AI_UNIT_KINDS)}")
    for entry in capabilities + invariants:
        rid = str(entry.get("id", "")).strip()
        if rid and rid not in claimed:
            problems.append(f"{rid}: rule with no owning duty - an AI capability nobody "
                            "schedules ships as prose in a README")
    problems.extend(_security_risk_errors(spec, declared))
    return "; ".join(problems) if problems else None


# --- the AI directive: the ONE lawful trigger for the AI phase ------------------------
# Mirror of the security waiver with the polarity flipped (opt-in, not exemption) and the
# SAME witness law: the description file is the only evidence. Discovery transcribes; the
# engine re-reads; no later phase may infer "the user obviously wanted AI".

def ai_directive(slug):
    """The slice's recorded AI directive, or None (= no AI capability; the phase skips)."""
    slice_report = _read_json(settings.DOMAIN_DIR / f"domain-boundary-{slug}.json")
    if slice_report is None:
        return None
    directive = slice_report.get("ai_directive")
    return directive if isinstance(directive, dict) else None


def ai_required(slug):
    """(required, note): true only when the business description itself states the AI
    capability and the quote is found VERBATIM in the cited description file."""
    slice_report = _read_json(settings.DOMAIN_DIR / f"domain-boundary-{slug}.json")
    directive = (slice_report or {}).get("ai_directive")
    if not isinstance(directive, dict) or directive.get("required") is not True:
        return False, ""
    quote = str(directive.get("quote", "")).strip()
    source = str(((slice_report or {}).get("metadata") or {}).get("source_description", "")).strip()
    if not source:
        return False, (f"{slug}: ai_directive claims the description but metadata."
                       "source_description was not recorded - an unverifiable claim is no trigger")
    path = Path(source)
    if not path.is_absolute():
        path = settings.ROOT / path
    if not path.is_file():
        return False, f"{slug}: ai_directive cites a description that cannot be read: {source}"
    try:
        text = _norm_text(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        return False, f"{slug}: ai_directive description unreadable: {exc}"
    if _norm_text(quote) not in text:
        return False, (f"{slug}: ai_directive.quote is not a sentence of {source} - the AI "
                       "trigger must be copied VERBATIM from the business description, never "
                       "paraphrased or inferred")
    return True, f'"{quote}" ({source})'


def validate_ai_directives():
    """Every recorded AI directive must survive the verbatim check (a claim about the
    user's words that cannot be verified is a discovery defect: fatal, with the fix -
    the AI phase must not silently run on an invented trigger, and must not silently
    skip because a real one was mis-copied)."""
    problems = []
    for path in sorted(settings.DOMAIN_DIR.glob("domain-boundary-*.json")):
        slug = path.stem.removeprefix("domain-boundary-")
        directive = ai_directive(slug)
        if not directive:
            continue
        if directive.get("required") is True:
            verified, note = ai_required(slug)
            if not verified:
                problems.append(note)
    return "; ".join(problems) if problems else None



def validate_report(path, expect):
    """Validate a DDD report with the shared reader script."""
    path = Path(path)
    if not path.is_file():
        return f"report not found: {path}"
    command = [
        sys.executable,
        str(settings.READER_SCRIPT),
        "--report",
        str(path),
        "--expect",
        expect,
        "--validate-only",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(settings.ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        return f"cannot run report validator: {exc}"
    if result.returncode != 0:
        return (result.stdout or "").strip() or f"report validator exited {result.returncode}"
    return None


def _norm_text(text):
    """Whitespace/case-normalized form of a passage, for verbatim-quote checks."""
    return " ".join(str(text or "").replace("\u2019", "'").strip().lower().split())


def security_directive(slug):
    """The slice's recorded security directive, or None when the domain declares none (= required)."""
    slice_report = _read_json(settings.DOMAIN_DIR / f"domain-boundary-{slug}.json")
    if slice_report is None:
        return None
    directive = slice_report.get("security_directive")
    return directive if isinstance(directive, dict) else None


def _waiver_note(slug):
    """The engine-checked waiver: (waived, note). A directive waives ONLY when its quote is found,
    word for word, in the description file the slice itself names - discovery is the single agent that
    reads the seed, and this is what stops any later phase from inferring, paraphrasing or inventing
    "the user did not ask for security"."""
    slice_report = _read_json(settings.DOMAIN_DIR / f"domain-boundary-{slug}.json")
    directive = (slice_report or {}).get("security_directive")
    if not isinstance(directive, dict) or directive.get("required") is not False:
        return False, ""
    quote = str(directive.get("quote", "")).strip()
    source = str(((slice_report or {}).get("metadata") or {}).get("source_description", "")).strip()
    if not source:
        return False, (f"{slug}: security_directive waives the phase but metadata.source_description "
                       "was not recorded - an unverifiable waiver is no waiver")
    path = Path(source)
    if not path.is_absolute():
        path = settings.ROOT / path
    if not path.is_file():
        return False, f"{slug}: security_directive cites a description that cannot be read: {source}"
    try:
        text = _norm_text(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        return False, f"{slug}: security_directive description unreadable: {exc}"
    if _norm_text(quote) not in text:
        return False, (f"{slug}: security_directive.quote is not a sentence of {source} - the waiver "
                       "must be copied VERBATIM from the business description, never paraphrased or "
                       "inferred")
    return True, f'"{quote}" ({source})'


def security_waived(slug):
    """True only when the business description itself waived this domain's security phase."""
    waived, _note = _waiver_note(slug)
    return waived


def validate_security_directives():
    """Every recorded waiver must survive the verbatim check; nothing else is refused.

    An absent directive is the default and means SECURITY REQUIRED. A present one is a claim about the
    user's own words, so the only witness is the description file - the same no-self-witness rule the
    rest of the board runs on."""
    problems = []
    for path in sorted(settings.DOMAIN_DIR.glob("domain-boundary-*.json")):
        slug = path.stem.removeprefix("domain-boundary-")
        directive = security_directive(slug)
        if not directive:
            continue
        if directive.get("required") is False:
            waived, note = _waiver_note(slug)
            if not waived:
                problems.append(note)
    return "; ".join(problems) if problems else None


def validate_strategy_coverage():
    """Every discovered domain must reach the plan: the phases that follow iterate STRATEGY slugs, so
    a missing strategy silently cancels that domain's database, SECURITY and decomposition phases.

    `validate_context_maps` already demands a map per slice; `database_slugs()` is derived from
    `execution-strategy-*.json`, so until now a board with 4 slices and 3 strategies drained green with
    one domain unplanned and its surfaces undefended - the escape hatch was never the waiver, it was a
    phase that quietly wrote nothing."""
    missing = []
    for path in sorted(settings.DOMAIN_DIR.glob("domain-boundary-*.json")):
        slug = path.stem.removeprefix("domain-boundary-")
        if not strategy_path(slug).is_file():
            missing.append(slug)
    if missing:
        return ("no execution strategy for " + ", ".join(missing)
                + " - every discovered domain is planned, secured and decomposed; a domain without a "
                "strategy receives no security spec and no tasks at all (re-run the architect's "
                "strategy phase for: " + ", ".join(missing) + ")")
    return None


def validate_domain_files():
    """Gate for the per-domain discovery files in blackboard/domain/.

    Returns None when at least one file exists and every file parses as a JSON object.
    Otherwise returns the reason string.
    """
    if not settings.DOMAIN_DIR.is_dir():
        return f"discovery did not create {settings.DOMAIN_DIR.relative_to(settings.ROOT)}/"
    files = sorted(settings.DOMAIN_DIR.glob("domain-boundary-*.json"))
    if not files:
        return f"no domain-boundary-*.json files in {settings.DOMAIN_DIR.relative_to(settings.ROOT)}/"
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return f"{path.name} is not valid JSON: {exc}"
        if not isinstance(payload, dict):
            return f"{path.name} must be a JSON object"
    return validate_security_directives()


def validate_context_maps():
    """Gate for the per-domain context maps in blackboard/context-map/.

    Every slice in blackboard/domain/ needs a valid context-map-<slug>.json.
    Returns None when all are valid, otherwise the reason string.
    """
    reason = validate_domain_files()
    if reason:
        return reason
    for domain_file in sorted(settings.DOMAIN_DIR.glob("domain-boundary-*.json")):
        slug = domain_file.stem.removeprefix("domain-boundary-")
        map_file = settings.CONTEXT_MAP_DIR / f"context-map-{slug}.json"
        reason = validate_report(map_file, "any")
        if reason:
            return f"{map_file.relative_to(settings.ROOT)}: {reason}"
    return None
