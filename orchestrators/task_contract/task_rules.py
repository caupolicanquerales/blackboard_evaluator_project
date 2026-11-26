"""task_rules - the mechanized plan rules (o)/(p)/(q)/(s)/(t)/(u) and
the batch consistency join: integration marks, real substrate, dedup
defences, migration schemes, correction/value-axis, publisher and
self-registration shapes, strategy-language reads. Verdicts are
ERR-pointer texts for the emit tier."""

import json
import workspace
import re
import settings
from task_identity import STATIC_CALL_RE, _instance_members, _returns_publisher, _simple_return_type, exported_product, step_log_entries
from task_signals import CONFIG_TRIGGER_RE, FAIL_OUTCOME_RE, FILE_ARTIFACT_RE, MECHANISM_PROMISE_RE, METER_CLAIM_RE, VIA_TOKEN_RE, _mechanism_claimed, _meter_pairs, _path_is_config_artifact, _signature_parameters, _surface_norm, per_record_signal_problems


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


def _strategy_text(slug):
    file = settings.COMPLETE_DIR / f"execution-strategy-{slug}.json"
    try:
        return file.read_text(encoding="utf-8")
    except OSError:
        return ""


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
        # (b2) BOOT-PATH CONNECTION KEYS (rule (h)'s machine leg, 2026-11-24 seed-002 v3):
        #      a config unit that tables a READER-LOCATION key (a path whose last segment is
        #      "locations"/"location" - Flyway's locations, Alembic's version_locations, a
        #      TypeORM migrations glob: the shape is universal, the gate names no vendor)
        #      enables a runtime reader, but readers migrate what they CONNECT to - if the
        #      same table carries no connection-URL path (last segment "url"), the enabled
        #      reader migrates an auto-detected throwaway store while the app writes
        #      elsewhere: the production schema is fiction and every per-unit gate stays
        #      green (the F5 class). Stack-neutral: property-path segments only.
        for u in units:
            if not isinstance(u, dict) or u.get("stage") != 2 or not _path_is_config_artifact(u.get("path")):
                continue
            cfg_paths = [str(c.get("path", "")) for c in (u.get("ast_hints") or {}).get("config", [])
                         if isinstance(c, dict)]
            segs = [p.split(".")[-1].strip().lower() for p in cfg_paths]
            if any(s in ("locations", "location") or s.endswith("_locations") for s in segs) \
                    and not any(s == "url" or s.endswith("_url") for s in segs):
                errors.append(
                    f"{u.get('id')}: the config table enables a reader with a LOCATIONS key "
                    "but tables NO connection-URL path in the same document (rule (h)): an "
                    "enabled reader without a configured datasource migrates the "
                    "auto-detected embedded store while the runtime writes elsewhere. Table "
                    "each reader form's url key (distinct environment placeholders - never "
                    "one variable feeding two URL schemes), or drop the locations key and "
                    "state the disabled posture")
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
    errors.extend(per_record_signal_problems(staged))
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
                "was a registered island; the seed's core rule never ran). Wrapping the "
                "stream in an envelope (Mono<ResponseEntity<Flux<...>>>) is the same "
                "publisher (2026-11-24: an SSE surface hid behind one to pass this check) "
                "- the honest answers, in order of cheapness: name its "
                "consumer unit in the DAG; route it in the wiring unit's duty list; "
                "spell `out-of-process` / `external subscribers` / `downstream "
                "subscribers` in THIS unit's OWN intent (the gate reads it per source); "
                "or write a boundary sentence naming this source into an EXISTING "
                "strategy text field (operations, traced_from, an assumption - the "
                "gate reads TEXT, never a new key; the strategy schema is phase 1's)")
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
                "entry, the store and the schema agree. Ride the slice where it belongs: "
                "the inbound unit's OWN stage-1 intent names the end-to-end drive against "
                "the embedded substitute with the durable effect asserted (valid AND "
                "invalid payloads), or schedule the FULL triple with its support unit - "
                "never a lone stage-1 task: the triple is atomic (2026-11-24: a repair "
                "pass bought its peace with an unpaired integration test whose red had "
                "no owner until the terminal suite)")
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
        #     The trigger is the migration SCRIPT, not a folder: wherever the tech-stack
        #     skill placed the runner's files, a `V*__*.sql` under the domain root means
        #     the domain has a packaged schema whose location a config unit may misquote
        #     (2026-11-24: the literal `db/migrations` folder test went silently dormant
        #     once the scripts moved into `src/main/resources/db/migration`).
        _proj_root = workspace.project_root_for(project)
        if _proj_root.is_dir() and any(_proj_root.rglob("V*__*.sql")):
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
        steps = step_log_entries((obs or {}).get("step_logs")) if isinstance(obs, dict) else []
        metrics = (obs or {}).get("metrics") if isinstance(obs, dict) else None
        if steps and isinstance(metrics, list) and metrics:
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
