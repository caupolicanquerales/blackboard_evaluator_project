"""plan_laws - every plan-time law check, as pure verdict functions.

Each returns ERR-pointer texts; the tiers (claim / lint / emit batch) decide
where a law runs. One body per law, several tiers (the 2026-11-26 split rule):
a law that lives in two copies drifts - the lint slug bug proved it."""

import json
import re
from pathlib import Path
import settings
import ddd
import tasks
import telemetry
import test_gate
from plan_board import BUILD_MANIFEST_EXPORT, SCAFFOLD_EXPORT, load_index
from plan_wiring import OBSERVABILITY_SURFACES, _claim_norm, _closest_spelling, _config_canon, _config_entry_shape, _route_key, _route_prose, _signature_param_text, _unit_family, _z_has_table, _z_tables, enforcers_text




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
        # BOTH strategy spellings flatten (tasks.step_log_entries): the per-context
        # dict is what agent-strategy-architect actually writes - the list-only reader
        # let a dict floor skip the whole completeness law (2026-11-20, V9)
        entries = tasks.step_log_entries(obs.get("step_logs"))
        wanted = {}
        for entry in entries:
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


# --- RULE (z): SHARED LITERALS ARE TABLED, NOT PROSE (2026-11-19, the R1/R2 roots of the
# 2026-11-18 drain). Meter names and request-path routes are literals used by >= 2 contracts
# (the registering unit, the recording units, the frozen test pair). While they lived only in
# intent prose, one board carried BOTH spellings as frozen law: the metrics facade's delivered
# names (`telemetry.validation.failed`) and the plan + consumer test names
# (`telemetry.samples.validation_failed`) - and the controller's test posting `/ingress/packets`
# against a chain, an intent and a slice all spelling `/telemetry/ingress`. No payload satisfies
# such a pair: the use case can only reach the collaborator's frozen API, and a deny-by-default
# chain never answers 202 on an unmapped route - the coder dies 3/3 on an unsatisfiable contract
# while every per-unit gate stayed green. Rule (l) named this class and admitted structure could
# not see it; the two `ast_hints` fields make the vocabulary visible and this gate joins it:
#   z1 every meter name is `owns`ed by exactly one unit; every `uses` names that owner
#      VERBATIM (a near-miss spelling is refused naming the closest tabled name); when the
#      whole domain is decomposed under the law, every strategy-floor metric has an owner;
#   z2 every (method, path) is `serves`d by exactly one unit; every `uses` names it verbatim;
#   z3 a literal spelled in a staged unit's own text (intent or a tabled `semantics`) must sit
#      in that unit's table - prose is never the only home of a shared literal;
#   z4 one unit, one table: its stage-1 and stage-2 twins carry IDENTICAL ast_hints when both
#      are staged; against a twin already on the board, every key present on both must match
#      (a regen cannot contradict the delivered table; either side may still ADD the
#      vocabulary keys).
# Duty words are stack-neutral; counting is per UNIT FAMILY (the T1/T2 pair of one number is
# one owner, not two). Boards that carry neither field and never spell a literal in prose skip
# the whole law - legacy readability (the F3 doctrine).
#   z5 a PROPERTY PATH is a shared literal too: units that bind or seed one table it in
#      `ast_hints.config` as {path, kind: value|list|map[, fields]} - the BINDING unit's
#      record declares the shape, the CONFIG unit cites it VERBATIM; the same path tabled
#      in two kinds (or two field sets), or a `value`/`map` child under a tabled `list`
#      prefix, is the impossible pair 2026-11-19 R4 froze (the record bound devices as a
#      LIST of (id, secret-hash, scope); the config contract seeded devices.secret-hash as
#      a SCALAR - no file satisfies both readers);
#   z6 the slice that imports a guard must be able to CONSTRUCT the chain: a surface unit
#      that pins a guard citing its served route must also table, among its own
#      collaborators, every PROJECT product the guard's table declares (its dependencies
#      and its method parameters). An untabled product is a bean the slice cannot supply -
#      R3: the controller test imported the chain whose concrete manager bean the wiring
#      factory (the plan's "sole registration mechanism") keeps out of every slice, and
#      the context died NoSuchBeanDefinition while its sibling test, which pinned the
#      manager, loaded fine.


def _z3_prose_problems(records, floor):
    """(z3) prose-vs-own-table, a PER-RECORD join (route-shaped and floor-meter
    literals a unit spells but its own table omits). Extracted 2026-11-25 so LINT says
    it inside the session's budget; the batch keeps calling it (one body, two tiers).

    (2026-11-25 cold5 livelaw fix) For a STAGE-1 record the remedy points at the
    code-side twin, never the record's own table: mirror_pair_tables rewrites every
    test-side table from the code side at claim AND at every emit revalidation - an
    edit typed onto T1 is deleted before the repair sees the next verdict, so the
    refusal looped until the no-op guard fatals a healthy board (cold5: the repair
    DID table 'telemetry.ingest.samples' on T1-025 and the mirror ate it). The
    repairable home of a stage-1 table is its stage-2 twin."""
    twins = {}
    for rec in records:
        if isinstance(rec, dict) and int(rec.get("stage") or 0) in (1, 2):
            twins.setdefault(_unit_family(rec), {})[int(rec["stage"])] = rec
    errors = []
    for record in records:
        if (not isinstance(record, dict)
                or int(record.get("stage") or 0) not in (1, 2)):
            continue
        home = f"{record.get('id')}'s own"
        if int(record.get("stage") or 0) == 1:
            t2 = twins.get(_unit_family(record), {}).get(2)
            if isinstance(t2, dict) and t2.get("id"):
                home = (f"{t2['id']}'s (the CODE-side twin of {record.get('id')} - a "
                        f"table typed on {record.get('id')} is mirrored away at the "
                        "next validation; the code side owns the interface)")
        text = " ".join([str(record.get("intent", ""))]
                         + [str(m.get("semantics") or "")
                            for m in (record.get("ast_hints") or {}).get("methods") or []
                            if isinstance(m, dict)])
        own_routes = {_route_key(e.get("method"), e.get("path"))
                      for e in _z_tables(record, "routes") if isinstance(e, dict)}
        for literal in _route_prose(text):
            hit = any(path == literal for _method, path in own_routes)
            if not hit:
                errors.append(
                    f"{record.get('id')}: its text spells the route '{literal}' but the unit's "
                    "ast_hints.routes does not carry it - a route named in prose is a contract "
                    "the paired tester never receives (the seed-002 test posted "
                    "'/ingress/packets' while every tabled contract said '/telemetry/ingress'): "
                    f"add {{method, path, duty}} to {home} ast_hints.routes (serves for the unit that "
                    "answers it, uses for a guard/caller/slice) or move the sentence out of "
                    "the unit's text (rule (z3))")
        own_meters = {str(e.get("name")) for e in _z_tables(record, "meters")
                      if isinstance(e, dict)}
        for name in sorted(floor):
            if (re.search(rf"(?<![\w.\-]){re.escape(name)}(?![\w\-])", text)
                    and name not in own_meters):
                errors.append(
                    f"{record.get('id')}: its text spells the floor meter '{name}' but the "
                    "unit's ast_hints.meters does not carry it - the two frozen tests written "
                    "from prose while the table holds silence is how one board froze both "
                    f"spellings of one meter: add {{name, duty}} to {home} ast_hints.meters ('uses' "
                    "when this unit records or asserts it; 'owns' belongs to exactly one "
                    f"unit, the one registering '{name}') or move the name out of the unit's "
                    "text (rule (z3))")
        # NO floor-STEP prose check here (removed same day it was added, 2026-11-26):
        # a meter may be 'used' by many units, but a floor step is a SINGLE-OWNER claim -
        # a per-file rule cannot know the lawful owner, so its remedy ("add it to
        # claims_steps") pushes consumers into claiming their sibling's step. Live: the
        # rule manufactured a 3-way 'turn completed' collision that refused the batch.
        # Step accounting stays where all owners are visible: _slice_coverage_errors
        # (per-file, this context's floor only) and the batch one-owner join.
    return errors


def _shared_literal_errors(staged, index):
    errors = []
    universe = {}
    for record in list(index.values()) + list(staged):
        if isinstance(record, dict) and record.get("id"):
            universe[str(record["id"])] = record
    staged_ids = {str(t.get("id")) for t in staged}
    projects = {str(t.get("project", "")) for t in staged if t.get("project")}
    for slug in sorted(projects):
        units = [r for r in universe.values()
                 if str(r.get("project", "")) == slug
                 and int(r.get("stage") or 0) in (1, 2)]
        strategy = {}
        file = settings.COMPLETE_DIR / f"execution-strategy-{slug}.json"
        try:
            strategy = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            strategy = {}
        obs = strategy.get("observability") if isinstance(strategy, dict) else {}
        floor = set()
        for entry in (obs or {}).get("metrics") or []:
            name = str((entry or {}).get("name") if isinstance(entry, dict) else entry).strip()
            if name:
                floor.add(name)

        # z4 - one unit, one table.
        by_family = {}
        for record in units:
            if isinstance(record.get("ast_hints"), dict):
                by_family.setdefault(_unit_family(record), []).append(record)
        for members in by_family.values():
            if len(members) < 2:
                continue
            by_stage = {int(m.get("stage") or 0): m for m in members}
            twin_a, twin_b = by_stage.get(1), by_stage.get(2)
            if twin_a is None or twin_b is None:
                continue
            hints_a, hints_b = twin_a["ast_hints"], twin_b["ast_hints"]
            both_new = (str(twin_a.get("id")) in staged_ids
                        and str(twin_b.get("id")) in staged_ids)
            if both_new:
                if hints_a != hints_b:
                    differ = sorted(k for k in set(hints_a) | set(hints_b)
                                    if hints_a.get(k) != hints_b.get(k))
                    errors.append(
                        f"{twin_a.get('id')}/{twin_b.get('id')}: the test task and the code task of "
                        f"one unit carry DIFFERENT ast_hints in {differ} - the tester asserts the "
                        "table it is given and the coder implements the table it is given; two "
                        "tables are two contracts and no payload satisfies both (rule (z4): the "
                        "pair must carry IDENTICAL tables - mirror the table VERBATIM into the twin)")
            else:
                for key in sorted(set(hints_a) & set(hints_b)):
                    if hints_a[key] != hints_b[key]:
                        staged_side = twin_a if str(twin_a.get("id")) in staged_ids else twin_b
                        delivered = twin_b if staged_side is twin_a else twin_a
                        errors.append(
                            f"{staged_side.get('id')}: its ast_hints.{key} disagrees with the "
                            f"table its unit twin {delivered.get('id')} carries on the board - "
                            "the frozen artifact already asserts/writes the delivered table; fix "
                            "this draft to match it, or move the change to the domain's replan "
                            f"(--replan {slug}) (rule (z4))")

        # collect the declared vocabulary (owner counts are per unit family)
        meters = {}
        for record in units:
            for entry in _z_tables(record, "meters"):
                if (isinstance(entry, dict) and entry.get("name")
                        and entry.get("duty") in ("owns", "uses")):
                    slot = meters.setdefault(str(entry["name"]),
                                             {"owns": set(), "uses": set()})
                    slot[entry.get("duty")].add(_unit_family(record))
        routes = {}
        for record in units:
            for entry in _z_tables(record, "routes"):
                if (isinstance(entry, dict) and entry.get("path")
                        and entry.get("duty") in ("serves", "uses")):
                    key = _route_key(entry.get("method"), entry.get("path"))
                    slot = routes.setdefault(key, {"serves": set(), "uses": set()})
                    slot[entry.get("duty")].add(_unit_family(record))

        errors.extend(_z3_prose_problems([r for r in staged if str(r.get("project", "")) == slug],
                                         floor))
        errors.extend(_perf_budget_closure_errors(slug, staged, index))

        # z1 - meter ownership and verbatim joins (law armed by the fields)
        if meters:
            for name, slot in sorted(meters.items()):
                owners, users = sorted(slot["owns"]), sorted(slot["uses"])
                if not owners:
                    errors.append(
                        f"{slug}: meter '{name}' is tabled by unit(s) {users} with duty 'uses' "
                        "but OWNED by none - no unit's contract registers that name, so no "
                        "payload can ever make it exist (2026-11-19 R1: the consumer test pinned "
                        "'telemetry.samples.validation_failed'; the delivered facade registered "
                        "'telemetry.validation.failed'; the coder died 3/3 between two frozen "
                        f"spellings): give the registering unit the '{name}' entry with duty "
                        f"'owns' spelled VERBATIM{_closest_spelling(name, set(meters) | floor)} "
                        "- if that unit was delivered before this law, --replan " + slug)
                elif len(owners) > 1:
                    errors.append(
                        f"{slug}: meter '{name}' is OWNED by units {owners} - exactly one unit "
                        "registers a name (rule (l)'s owner, made machine-checkable): the facade/"
                        "instrument that creates it; the others switch to duty 'uses'")
                if floor and name not in floor:
                    errors.append(
                        f"{slug}: meter '{name}' is tabled but the strategy floor "
                        f"(observability.metrics) never planned it - plan it in the strategy or "
                        "drop the claim; an off-plan name is vocabulary the floor cannot serve "
                        "(the step-log doctrine, rule (z1))")
            stage2 = [r for r in units if int(r.get("stage") or 0) == 2]
            if (floor and stage2
                    and all(_z_has_table(r, "meters") for r in stage2)):
                for name in sorted(floor - set(meters)):
                    errors.append(
                        f"{slug}: the strategy floor declares meter '{name}' but no unit tables it "
                        "with duty 'owns' - an unowned meter is a counter that will never exist: "
                        "claim it VERBATIM in the registering unit's ast_hints.meters (rule (z1), "
                        "the completeness half rule (u) could not see: it paired NAMES FUZZILY, "
                        "never VERBATIM)")

        # z2 - route serving and verbatim joins (law armed by the fields)
        for (method, path), slot in sorted(routes.items()):
            servers, users = sorted(slot["serves"]), sorted(slot["uses"])
            if not servers:
                errors.append(
                    f"{slug}: route {method} {path} is tabled by unit(s) {users} with duty "
                    "'uses' but SERVED by none - the deny-by-default chain (or any guard/slice) "
                    "citing a route no inbound unit answers is the seed-002 pair that froze the "
                    "controller against its own test (R2): move the entry to the unit that "
                    "answers it with duty 'serves', or fix the spelling to the served pair "
                    f"VERBATIM{_closest_spelling(path, {p for _m, p in routes})}")
            elif len(servers) > 1:
                errors.append(
                    f"{slug}: route {method} {path} is `serves`ed by units {servers} - exactly "
                    "one inbound unit answers a route; the others switch to duty 'uses'")

        # z5 - property paths: one path, one shape (the binder's record is the shape truth)
        shapes = {}  # canon path -> {kind: {family...}, fields: {tuple: {family...}}}
        for record in units:
            for path, kind, fields, value in _config_entry_shape(record):
                slot = shapes.setdefault(_config_canon(path),
                                         {"raw": path, "kind": {}, "fields": {}, "value": {}})
                slot["kind"].setdefault(kind, set()).add(_unit_family(record))
                if fields:
                    slot["fields"].setdefault(fields, set()).add(_unit_family(record))
                if value:
                    slot.setdefault("value", {}).setdefault(value, set()).add(
                        _unit_family(record))
        if shapes:
            for canon, slot in sorted(shapes.items()):
                if len(slot["kind"]) > 1:
                    detail = {k: sorted(v) for k, v in sorted(slot["kind"].items())}
                    errors.append(
                        f"{slug}: property path '{canon}' is tabled in TWO shapes {detail} - one "
                        "path has ONE shape, and it belongs to the unit whose record binds it: "
                        "the reader/writer units cite that shape VERBATIM in their ast_hints.config "
                        "(2026-11-19 R4: the record bound `devices` as a list while the config "
                        "contract seeded `devices.secret-hash` as a scalar - no file satisfies "
                        "both, and no test could see the pair until two contracts froze)")
                if len(slot["fields"]) > 1:
                    detail = {list(k): sorted(v) for k, v in sorted(slot["fields"].items())}
                    errors.append(
                        f"{slug}: property path '{canon}' is tabled with conflicting element "
                        f"fields {detail} - the element shape belongs to the binding record; "
                        "every other unit cites the same `fields` VERBATIM (rule (z5))")
                if len(slot.get("value", {})) > 1:
                    detail = {k: sorted(v) for k, v in sorted(slot["value"].items())}
                    errors.append(
                        f"{slug}: property path '{canon}' is tabled with conflicting seeded "
                        f"VALUES {detail} - one operational path, one default (rule (l)'s "
                        "impossible pair made machine-visible by (z5)'s value field): pick "
                        "the owner's value and cite it VERBATIM, or split DISTINCT keys per "
                        "reader form")
                for other in sorted(shapes):
                    if (other != canon and canon.startswith(other + ".")
                            and "list" in shapes[other]["kind"]):
                        errors.append(
                            f"{slug}: path '{canon}' is tabled as a dotted child while "
                            f"'{other}' is tabled as a LIST - a list binds indexed entries "
                            "(`<path>[i].<field>`), never a dotted child; the element keys belong "
                            "in the list path's `fields` (R4: `devices.secret-hash` next to a "
                            "`devices` list is unreadable by every binder and unmissable by "
                            "every test)")
                        break
            # (b) host leg (2026-11-25 root restructure): coverage is a WIRE
            # (wire_config_coverage ran before this join and copied every tabled path
            # into the ONE config unit); what remains refused here is the shape the
            # wire cannot invent for the plan: a domain that tables operational paths
            # with no configuration-artifact unit anywhere - the ROOT pass owes it.
            config_units = [record for record in units
                            if str(record.get("project", "")) == slug
                            and int(record.get("stage") or 0) == settings.TDD_STAGE
                            and tasks._path_is_config_artifact(record.get("path"))]
            bound = {}
            for record in units:
                if (str(record.get("project", "")) != slug
                        or int(record.get("stage") or 0) != settings.TDD_STAGE):
                    continue
                for path, _kind, _fields, _value in _config_entry_shape(record):
                    bound.setdefault(_config_canon(path), set()).add(str(record.get("id")))
            if bound and not config_units:
                sample = ", ".join(f"'{p}'" for p in sorted(bound)[:8])
                errors.append(
                    f"{slug}: {len(bound)} property path(s) are bound by stage-2 units "
                    f"({sample}...) but the domain has NO stage-2 configuration-artifact "
                    "unit - rule (b): the ROOT pass schedules the ONE config unit; until "
                    "it exists, every runtime default is a number the coder invents. The "
                    "coverage itself is NOT your typing job: once the unit exists the "
                    "engine wires every tabled path into its ast_hints.config table")
            elif bound and config_units:
                seeded = set()
                for record in config_units:
                    for path, _kind, _fields, _value in _config_entry_shape(record):
                        seeded.add(_config_canon(path))
                missing = sorted(p for p in bound if p not in seeded)
                if missing and not any(str(r.get("id")) in staged_ids
                                       for cu in config_units for r in [cu]):
                    errors.append(
                        f"{slug}: {len(missing)} property path(s) tabled by the board are "
                        "not seeded in the DELIVERED config unit - the frozen artifact "
                        "cannot be rewritten by a later batch; relaunch with --replan "
                        + slug + " so the ROOT pass re-plans the full surface")

        # z6 - the slice that imports a guard must be able to construct the chain
        by_product = {}
        for record in units:
            if int(record.get("stage") or 0) == settings.TDD_STAGE:
                product = tasks.exported_product(record)
                if product:
                    by_product.setdefault(product.lower(), record)
        served_by_family = {}
        for record in units:
            for entry in _z_tables(record, "routes"):
                if isinstance(entry, dict) and entry.get("duty") == "serves":
                    served_by_family.setdefault(_unit_family(record), set()).add(
                        _route_key(entry.get("method"), entry.get("path")))
        for record in units:
            if (int(record.get("stage") or 0) != settings.TDD_STAGE
                    or _unit_family(record) not in served_by_family
                    or str(record.get("id")) not in staged_ids):
                continue  # only staged surface units can still be edited
            pinned = {str(d.get("type", "")).rsplit(".", 1)[-1].lower()
                      for d in _z_tables(record, "dependencies") if isinstance(d, dict)}
            for guard in units:
                if (guard is record
                        or int(guard.get("stage") or 0) != settings.TDD_STAGE):
                    continue
                guard_cites = {_route_key(e.get("method"), e.get("path"))
                               for e in _z_tables(guard, "routes")
                               if isinstance(e, dict) and e.get("duty") == "uses"}
                if not (guard_cites & served_by_family[_unit_family(record)]):
                    continue
                needed = set()
                for dep in _z_tables(guard, "dependencies"):
                    if isinstance(dep, dict):
                        name = str(dep.get("type", "")).rsplit(".", 1)[-1]
                        if name.lower() in by_product:
                            needed.add(name.lower())
                for member in _z_tables(guard, "methods"):
                    if isinstance(member, dict):
                        for token in tasks.CAMEL_TYPE_RE.findall(
                                _signature_param_text(member.get("signature"))):
                            if token.lower() in by_product:
                                needed.add(token.lower())
                own = (str(tasks.exported_product(record) or "").lower(),
                       str(tasks.exported_product(guard) or "").lower())
                missing = sorted(needed - pinned - set(own))
                if missing:
                    errors.append(
                        f"{record.get('id')}: it serves a route the guard {guard.get('id')} "
                        f"cites, but the guard's own table declares collaborators {missing} "
                        "the record does not pin - a slice importing that chain cannot "
                        "construct it (2026-11-19 R3: the controller test @Imported the chain "
                        "whose concrete manager bean the wiring factory alone registered; the "
                        "context died NoSuchBeanDefinition and the unit burned 3/3 on a gap in "
                        "its CONTRACT, while its sibling slice, which pinned the manager, "
                        "loaded fine). Pin each product the guard needs as a collaborator "
                        "{type, task_id} (doubles come from the table; the test writes only "
                        "against tables) - rule (z6)")
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


SECURITY_REF_RE = re.compile(r"\b(?:TB|P|DC|AZ|SI|SD|R|AS)-\d{2}\b")
# the performance/AI specs' own id spaces (2026-11-19): WB/PB/PI/PA/R for performance,
# AR/AC/AM/AA/R for AI - a duty's spec_ref must resolve inside its own artifact, and the
# claim gate reads the pair (spec_ref + capability) from the unit's text exactly as (y)
# does for security duties.

SECURITY_TOKEN_SECTIONS = ("trust_boundaries", "principals", "data_classification",
                           "authorization_matrix", "invariants")
SECURITY_TRACE_FIELDS = ("intent",)


def _security_spec(slug):
    """The domain's security spec, or None when the phase never wrote one (legacy board).

    Same literal as `ddd.SECURITY_SPEC_PREFIX`; the pairing is pinned by construction -
    the gauntlet writes the fixture through `ddd.security_spec_path` and this gate must
    read it back, so a rename on one side fails a case instead of quietly blinding the
    claim gate.
    """
    path = settings.COMPLETE_DIR / f"security-spec-{slug}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _security_declared_ids(spec):
    """Every entry id the spec declares (section tables + the secrets inventory)."""
    declared = set()
    for section in SECURITY_TOKEN_SECTIONS:
        for entry in spec.get(section) or []:
            if isinstance(entry, dict) and str(entry.get("id", "")).strip():
                declared.add(str(entry["id"]).strip())
    for entry in _security_secret_inventory(spec):
        if isinstance(entry, dict) and str(entry.get("id", "")).strip():
            declared.add(str(entry["id"]).strip())
    return declared


def _security_secret_inventory(spec):
    """The secrets inventory list, or [] when the section is malformed: a spec the
    security step wrote badly is refused by the step's own gate, never by a crash here."""
    secrets = spec.get("secrets")
    entries = secrets.get("inventory") if isinstance(secrets, dict) else None
    return entries if isinstance(entries, list) else []


CROSS_OWNER_RE = re.compile(r"cross[- ]owner|other tenant|another tenant|foreign (?:tenant|owner)"
                            r"|owned by (?:a |another |someone else)|someone else", re.I)


def _unit_text(record):
    """The fields a stack-neutral gate may read off a unit: its prose and its pinned table -
    never the source it has not written yet."""
    hints = record.get("ast_hints") or {}
    return " ".join([str(record.get(field, "")) for field in SECURITY_TRACE_FIELDS]
                     + [str(value) for value in hints.values() if isinstance(value, str)])


def _inbound_units(units, surface_names=()):
    """Stage-2 entry adapters - the same reading rule (p) uses (layer or inbound prose),
    widened by y5 (2026-11-24 v4 live): an internal-call surface's consuming adapter IS the
    entry even at application layer - a law that only recognizes HTTP controllers gets
    layer-hacked around (the repair relabeled a consumer 'interface' while its package
    stayed /application/). y2 already makes the unit that NAMES a surface the entry; the
    detector follows the law it enforces."""
    return [unit for unit in units if unit.get("stage") == settings.TDD_STAGE
            and (str(unit.get("layer", "")) in ("interface", "api", "entry")
                 or tasks.INBOUND_RE.search(str(unit.get("intent", "")))
                 or any(n and n in ddd.norm_surface(str(unit.get("intent", "")))
                        for n in surface_names))]


def _pins(entry_unit, product_unit, by_id):
    """Does the entry unit carry the enforcing unit - by task id or by its exported type -
    in its own collaborator table, or depend on it (directly or through the graph)?
    The drain schedules ONLY on `dependsOn` (tdd_engine: unmet = deps - complete) and the
    tester writes assertions ONLY against pinned tables, so an enforcing unit the entry
    never pulls in can be gated and closed in the same wave as the surface it was meant to
    defend - after that surface's frozen test was written against a constructor with no
    guard in it, and the retrofit arrives too late to change the frozen pair."""
    deps = [dep for dep in (entry_unit.get("ast_hints") or {}).get("dependencies") or []
            if isinstance(dep, dict)]
    product_id = str(product_unit.get("id", ""))
    if product_id in {str(dep.get("task_id", "")) for dep in deps}:
        return True
    pinned_types = {str(dep.get("type", "")).strip().lower() for dep in deps}
    faces = {str(face).strip().lower()
             for face in [tasks.exported_product(product_unit), product_unit.get("export"),
                          *((product_unit.get("ast_hints") or {}).get("implements") or [])]
             if face}
    if faces & pinned_types:
        return True
    return tasks.depends_transitively(str(entry_unit.get("id", "")), product_id, by_id)


def _security_reach_errors(slug, spec, claims, by_id):
    """Gap B (2026-11-18): the claim gate proved a duty was CLAIMED, never that it was claimed
    BY THE UNIT THAT RUNS ON THE DEFENDED PATH. Three refusals, all field comparisons on the
    plan's own vocabulary (no source is read):

    (y1 IMPLANTATION) the claim must sit on a stage-2 unit: a duty named only in a tester's or
        an evaluator's prose is a duty no code ever implements;
    (y2 REACH) the unit that enforces a row must be reachable from the entry adapter that IS
        that row's surface - its collaborator table or its `dependsOn` - so the guard exists
        and is wired BEFORE the surface's frozen test is written and before its own close-out
        (the drain orders units only by `dependsOn`);
    (y3 ASSERTION AT THE SURFACE) that adapter's paired stage-1 test carries the row id and the
        cross-owner case: a permission rule proven only on the predicate's own unit test is a
        rule the request path never exercises (a role check that still fetches another tenant's
        row by id passes it, and that is the IDOR the spec forbids).

    The join key is the row's `surface` text, widened by any strategy surface whose name it
    carries: phase 1's `surfaces[].name` is what the architect is told to copy into both the
    row and the entry unit's intent, so a row matched to no inbound adapter is either a
    consumer/job/cli row (nothing to wire) or a plan that never named its surface. SURFACE
    OWNERSHIP closes that dodge: a declared surface no inbound unit carries is refused - the
    reach law needs the name, and a plan that hides the adapter hides the hole.
    """
    errors = []
    surfaces = [ddd.norm_surface(surface.get("name"))
                for surface in (ddd.strategy_surfaces(slug) or []) if isinstance(surface, dict)]
    rows = {str(row.get("id", "")).strip(): row for row in (spec.get("authorization_matrix")
            or []) if isinstance(row, dict)}
    units = [record for record in by_id.values()
             if str(record.get("project", "")) == slug and int(record.get("stage") or 0) >= 1]
    # y5 (2026-11-24 v4): the detector is widened by the DECLARED surface names - the
    # unit that names a surface IS its entry, whatever layer it lives at.
    inbound = _inbound_units(units, surfaces)
    testers = {}
    for unit in units:
        if int(unit.get("stage") or 0) != settings.TESTER_STAGE:
            continue
        mark = str(unit.get("id", "")).rsplit("-", 1)
        if len(mark) == 2:
            testers.setdefault(mark[1], []).append(unit)
    for name in sorted(n for n in surfaces if n):
        # SURFACE OWNERSHIP: the reach law below needs a join, and a join needs the entry unit
        # to name its surface. A declared surface no inbound unit carries is therefore either
        # an unscheduled adapter or a plan that dodges the join by silence - both are the same
        # hole the step-log claim law killed (a promised boundary with no owner).
        if not any(name in ddd.norm_surface(_unit_text(unit)) for unit in inbound):
            errors.append(
                f"{slug}: surface {name!r} is declared by phase 1 and named by NO inbound unit "
                "of the plan - schedule the adapter that IS this surface (its intent carries the "
                "strategy's `surfaces[].name` verbatim), or the surface ships unwired and "
                "unauthorized while every per-unit gate stays green")
    for rid, row in sorted(rows.items()):
        row_text = ddd.norm_surface(row.get("surface"))
        names = {name for name in (row_text,) if name}
        names |= {name for name in surfaces
                  if name and (name in row_text or row_text in name)}
        if not names:
            continue
        matched = [unit for unit in inbound
                   if any(name in ddd.norm_surface(_unit_text(unit)) for name in names)]
        if not matched:
            continue  # no inbound adapter claims this surface: nothing on the path to wire
        claim = claims.get(rid)
        if not claim:
            continue  # (closure) already refused above
        implementers = [record for record in claim["records"]
                        if int(record.get("stage") or 0) == settings.TDD_STAGE]
        if not implementers:
            errors.append(
                f"{slug}: security duty {rid} is claimed only by "
                f"{sorted(str(record.get('id', '?')) for record in claim['records'])} - a test "
                "or refactor task carries no implementation: name the token in the stage-2 unit "
                "that ENFORCES it, or the duty ships as a comment")
            continue
        wired = [entry for entry in matched if any(_pins(entry, unit, by_id)
                                                   for unit in implementers)]
        for entry in [item for item in matched if item not in wired]:
            errors.append(
                f"{slug}: surface {row.get('surface')!r}: {rid} is enforced by "
                f"{sorted(str(unit.get('id')) for unit in implementers)} but the entry unit "
                f"{entry.get('id')} neither pins that unit in `ast_hints.dependencies` nor "
                "depends on it - the drain orders units ONLY by `dependsOn` and the tester "
                "writes assertions ONLY against pinned tables, so this surface is implemented, "
                "gated and closed with no guard on its path (and the guard arrives, if at all, "
                "as a retrofit that can no longer change the frozen pair). Wire the enforcing "
                "unit into the entry unit's contract, or put the predicate on the unit that "
                "does the lookup")
        for entry in wired:
            mark = str(entry.get("id", "")).rsplit("-", 1)
            pair = testers.get(mark[-1], []) if len(mark) == 2 else []
            if not any(rid in _unit_text(tester)
                       and CROSS_OWNER_RE.search(str(tester.get("intent", "")))
                       for tester in pair):
                errors.append(
                    f"{slug}/{entry.get('id')}: {rid} is enforced on the request path but the "
                    "paired stage-1 test never carries the row and its CROSS-OWNER case (a valid "
                    "identifier owned by someone else, refused) - the spec's `test_duty` is "
                    "asserted AT the lookup: a permission rule proven only on its own unit test "
                    "is a rule no request ever meets")
    return errors


def _security_claim_errors(staged, index):
    """SECURITY DUTY CLAIM COVERAGE - the same completeness hole the step-log gate closed,
    one artifact later. The security spec tables what must hold; if the decomposition never
    claims a duty, that rule exists in no unit, ships in no code, and every per-unit gate
    stays green. An unclaimed authorization rule is an unenforced one.
    Two layers, both stack-neutral token comparisons (no source is ever read):
    (closure) every duty's `spec_ref` must appear as a token in at least one task of that
     domain - naming a duty is what schedules it;
    (mapping) and the claiming task must also carry the duty's `capability` token, because a
     bare `AZ-03` is a citation, not a realization: the requirement and the thing that holds it
     travel together, or the duty is only decorated. The engine never checks WHICH mechanism the
     architect chose - that judgment belongs to the tech-stack skill, and a stack-neutral validator
     naming frameworks would be the leak this whole phase exists to prevent;
    (fabrication) a token shaped like a spec entry that the spec does not declare is refused
     too: one plan, one vocabulary.
    The placement layer that coverage alone cannot see ((y1) implantation, (y2) reach,
    (y3) assertion at the surface) lives in `_security_reach_errors`.
    Three deliberate skips, each blocking a refusal no agent could answer:
    (a) the domain has no spec file - boards that never ran the phase;
    (b) the batch stages no application task - the scaffold and the database step emit
     stage 0 only, and a stage-0 session cannot claim a decomposition duty;
    (c) the project has no stage-2 unit on the board yet - demanding claims before
     decomposition exists is the phase-order hole that burned an architect's whole budget
     on 2026-11-16 09:50.
    """
    errors = []
    projects = {str(t.get("project", "")) for t in staged if t.get("project")}
    if not any(int(record.get("stage") or 0) >= 1 for record in staged):
        return errors  # skip (b): a stage-0 emit answers no decomposition duty
    by_id = {}
    for record in list(index.values()) + list(staged):
        if isinstance(record, dict) and record.get("id"):
            by_id[str(record["id"])] = record
    for slug in sorted(projects):
        spec = _security_spec(slug)
        if spec is None:
            continue  # skip (a)
        declared = _security_declared_ids(spec)
        # spec_ref -> the capability tokens its duties say must hold. A claim without one of
        # them is a token pasted onto a unit: the duty was "covered" and nothing was mapped.
        duty_caps = {}
        row_caps = {}
        for duty in (spec.get("duties") or []):
            if not isinstance(duty, dict):
                continue
            ref = str(duty.get("spec_ref", "")).strip()
            if ref:
                capability = str(duty.get("capability", "")).strip()
                duty_caps.setdefault(ref, set())
                if capability:
                    duty_caps[ref].add(capability)
                # (row layer) a row discharged THROUGH this duty's `covers` inherits its
                # capability: the row-level claim map accepts the covering duty's token
                # as the row's mapping evidence.
                row_caps.setdefault(ref, duty_caps[ref])
                for cid in (str(x).strip() for x in (duty.get("covers") or [])):
                    if cid:
                        row_caps.setdefault(cid, set())
                        if capability:
                            row_caps[cid].add(capability)
        if not any(str(record.get("project", "")) == slug
                   and int(record.get("stage") or 0) == settings.TDD_STAGE
                   for record in by_id.values()):
            continue  # skip (c): decomposition has not landed yet (see docstring)
        claims, fabricated = {}, {}
        for record in by_id.values():
            if str(record.get("project", "")) != slug or int(record.get("stage") or 0) < 1:
                continue
            text = _unit_text(record)
            for token in SECURITY_REF_RE.findall(text):
                if token in declared:
                    claim = claims.setdefault(token, {"owners": set(), "mapped": False,
                                                      "records": []})
                    claim["owners"].add(str(record.get("id", "?")))
                    claim["records"].append(record)
                    caps = duty_caps.get(token) or set()
                    if not caps or any(cap in text for cap in caps):
                        claim["mapped"] = True
                else:
                    fabricated.setdefault(token, []).append(str(record.get("id", "?")))
        for token in sorted(set(duty_caps) - set(claims)):
            errors.append(
                f"{slug}: security duty {token} is claimed by NO unit - name the token in the "
                "enforcing unit's intent (the unit that owns its `unit_kind`: see the mechanism "
                "table), and its tester asserts the permitted, denied and cross-owner cases. Where "
                "the stack realizes nothing, the duty still needs its home - the CONFIG unit for "
                "custody/lifetime facts, the store or domain unit for identifier and crypto shapes; "
                "a reported risk never substitutes for a claiming unit (this session has no write "
                "path to the spec: if the spec itself is wrong, stop and re-run the security phase "
                "for this domain with the strategy amended)")
        # (row layer 2026-11-26, measured live: 3 of 8 authorization rows unclaimed while every
        # duty was) duty-level closure has a hole: a row discharged only through another duty's
        # `covers` is scheduled at SPEC level but never SPOKEN in the plan - the surface unit then
        # carries neither the row id, nor its capability, nor the row's own test_duty cases.
        # Authorization rows are the IDOR law made concrete: an unspoken row ships untested.
        for row in (spec.get("authorization_matrix") or []):
            if not isinstance(row, dict):
                continue
            rid = str(row.get("id", "")).strip()
            if not rid:
                continue
            if rid not in claims:
                cases = str(row.get("test_duty", "")).strip()
                errors.append(
                    f"{slug}: authorization row {rid} (surface {str(row.get('surface'))!r}) is "
                    "claimed by NO unit - duty coverage is not scheduling: the unit that IS this "
                    "row's surface entry spells the row id beside the capability of the duty that "
                    "discharges it"
                    + (f", and its paired tester asserts the row's test_duty: {cases[:140]}"
                       if cases else ""))
            elif row_caps.get(rid) and not claims[rid]["mapped"] and not any(
                    any(cap in _unit_text(rec) for cap in row_caps[rid])
                    for rec in claims[rid]["records"]):
                errors.append(
                    f"{slug}: authorization row {rid} is cited without the capability of any duty "
                    f"that discharges it ({sorted(row_caps[rid])}) - spell the capability token "
                    "beside the mechanism in the enforcing unit (rule (y1))")
        for token in sorted(claims):
            caps = duty_caps.get(token) or set()
            if caps and not claims[token]["mapped"]:
                errors.append(
                    f"{slug}: security duty {token} is claimed by {sorted(claims[token]['owners'])} "
                    f"without the capability its duty names ({sorted(caps)}) - a bare token is a "
                    f"citation, not a mapping: spell the capability beside the concrete mechanism "
                    f"the active tech-stack skill provides, in that unit's intent")
        for token, owners in sorted(fabricated.items()):
            errors.append(
                f"{slug}: unit(s) {sorted(set(owners))} name security entry {token} the spec never "
                f"declares - fix the plan or the spec, never both silently")
        errors.extend(_security_reach_errors(slug, spec, claims, by_id))
    return errors


def _planning_claim_lines(slug, units):
    """Unclaimed performance/AI duties for one domain, read over `units` (all records of
    the project the caller can see). The claim law is the (y1) FORM - the pair (spec_ref +
    capability) VERBATIM inside one STAGE-2 unit's text - and deliberately not (y2)/(y3):
    a load-shed or a model-port duty has no surface-reach geometry the way an ownership
    predicate does, and inventing one would refuse lawful placements. Phase-order hole
    (V6b doctrine): until the domain has any stage-2 unit, nothing is demanded.
    A spec the phase never wrote is not this gate's subject (the pipeline already stops
    on a missing mandatory spec; an AI spec is optional by directive)."""
    lines = []
    for label, path in (("performance", ddd.performance_spec_path(slug)),
                        ("AI", ddd.ai_spec_path(slug))):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(spec, dict):
            continue
        duties = [duty for duty in (spec.get("duties") or []) if isinstance(duty, dict)]
        stage2 = [u for u in units if int(u.get("stage") or 0) == settings.TDD_STAGE]
        if not duties or not stage2:
            continue
        for duty in duties:
            ref = str(duty.get("spec_ref", "")).strip()
            cap = str(duty.get("capability", "")).strip()
            if not ref or not cap:
                continue
            claimed = any(ref in _unit_text(unit)
                          and re.search(r"\b" + re.escape(cap) + r"\b", _unit_text(unit))
                          for unit in stage2)
            if not claimed:
                lines.append(
                    f"{slug}: {label} duty {ref} ({cap}) is claimed by no stage-2 unit - "
                    "the plan cannot discharge a rule it was never shown: copy spec_ref and "
                    "capability VERBATIM into the intent of the unit that enforces it (the "
                    "claim law of the (y) family; the machine enforces the claim, the "
                    "placement stays the architect's) - if this spec arrived after its "
                    f"decomposition, relaunch with --replan {slug}")
    return lines


def planning_claim_gaps(slug):
    """One domain's unclaimed performance/AI duties OVER THE LIVE BOARD (same reading the
    emit gate applies, same role `security_claim_gaps` plays for the security spec)."""
    index = load_index()
    units = [record for record in index.values()
             if isinstance(record, dict) and str(record.get("project", "")) == slug]
    return _planning_claim_lines(slug, units)


def security_claim_gaps(slug):
    """One domain's security-claim gaps OVER THE LIVE BOARD (queue + complete; quarantined
    records are invisible, exactly as the drain sees them).

    Same reading `_security_claim_errors` applies to an emit batch, so the pipeline can
    answer a question the emit gate structurally cannot: is a spec that arrived AFTER its
    decomposition actually discharged? [] means every duty is claimed, implemented,
    reachable from the surface it defends, and asserted at that surface.
    """
    index = load_index()
    live = [record for record in index.values()
            if isinstance(record, dict) and str(record.get("project", "")) == slug]
    return _security_claim_errors(live, index)


def _manifest_order_errors(staged, index):
    """BUILD-MANIFEST PRECEDES EVERY RED COMPILE (2026-11-20 root fix - AS15's prose law
    promoted to the machine tier): a stage-0 task whose export is `build-manifest` means
    the plan ADDS coordinates the scaffold build file lacks, and a module's test compile
    pulls the WHOLE module's classpath - the same fact in Maven, Gradle, npm and pip.
    So EVERY stage-1 and stage-2 task of that project must reach the manifest through
    `dependsOn`, transitively: without the edge, the unit's first red gate is the D4
    import storm (live 2026-11-18; repeated on the 2026-11-20 board, where T2-019's
    chain never depended on T0-007). The rule reads ONLY structural board facts - the
    export marker and the dependency closure - never an annotation, artifact or
    framework name: the engine stays stack-agnostic, and the mapping table keeps its
    monopoly on mechanism vocabulary."""
    world = dict(index)
    world.update({str(task.get("id")): task for task in staged
                  if isinstance(task, dict) and task.get("id")})
    manifests = {}
    for tid, task in world.items():
        if not isinstance(task, dict) or int(task.get("stage") or 0) != 0:
            continue
        if str(task.get("export", "")).strip() == BUILD_MANIFEST_EXPORT:
            manifests.setdefault(str(task.get("project", "")), []).append(str(tid))
    errors = []
    for task in staged:
        if not isinstance(task, dict) or int(task.get("stage") or 0) not in (1, 2):
            continue
        targets = manifests.get(str(task.get("project", "")))
        if not targets:
            continue
        seen, stack = set(), [str(task.get("id", ""))]
        reached = None
        while stack:
            for dep in world.get(stack.pop(), {}).get("dependsOn") or []:
                dep = str(dep)
                if dep in targets:
                    reached = dep
                    break
                if dep not in seen:
                    seen.add(dep)
                    stack.append(dep)
            if reached:
                break
        if not reached:
            errors.append(
                f"{task.get('id')}: the project schedules build-manifest {targets} - new "
                "coordinates must be in the build file BEFORE the first compile of the "
                "module its tests build - add the manifest id to `dependsOn` (the pair's "
                "twin then inherits it through the pair)")
    return errors


def _writable_channel_errors(staged):
    errors = []
    for task in staged:
        if int(task.get("stage") or 0) not in (settings.TESTER_STAGE, settings.TDD_STAGE):
            continue
        path = str(task.get("path") or "").replace("\\", "/")
        if not path:
            continue
        suffix = Path(path).suffix.lower()
        if suffix in test_gate.SOURCE_SUFFIXES or suffix in (".yml", ".yaml", ".properties"):
            continue
        errors.append(
            f"{task.get('id')}: its `path` '{path}' ends in {suffix or '(no suffix)'} - the pipeline "
            "writes LANGUAGE SOURCES and configuration documents (.yml/.yaml/.properties) "
            "only; no agent of this board authors template or text files. A unit planned "
            "there is a duty without a lawful channel: move the artifact INTO a source type "
            "the weaver lands (an AI prompt contract is a Java type whose five members are "
            "tabled in ast_hints: version, role identity, input placeholders, output-schema "
            "reference, refusal text), or onto the configuration document that owns the key "
            "- do not re-emit hoping for a writer that does not exist")
    return errors


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


def _stage0_family_errors(staged, world=None):
    """ONE scaffold and ONE build-manifest per domain (2026-11-20 split edge): the
    per-context sessions share a single build file, so a coordinate two contexts each
    notice would be scheduled twice and the container would mutate the same file in two
    stage-0 sessions - last writer wins, first duty silently lost. The families are
    keyed by their export marker (never by path shape, the S16 lesson): a second task
    with the same family export in the same project is refused naming the FIRST one,
    because the lawful remedy is to amend that task (a repair pass may edit it; a
    planning session may not touch another context's draft) - or to read the symbol
    table's `build_manifest` before emitting at all."""
    seen = {}
    for record in list(staged) + list((world or {}).values()):
        if not isinstance(record, dict) or int(record.get("stage") or 0) != 0:
            continue
        export = str(record.get("export", "")).strip()
        if export not in (SCAFFOLD_EXPORT, BUILD_MANIFEST_EXPORT):
            continue
        ids = seen.setdefault((str(record.get("project", "")), export), [])
        tid = str(record.get("id", "?"))
        if tid not in ids:
            ids.append(tid)
    problems = []
    for (project, export), ids in sorted(seen.items()):
        if len(ids) > 1:
            problems.append(
                f"ERR [{', '.join(sorted(ids[1:]))}]: a second '{export}' stage-0 task for "
                f"project '{project}' - the domain ships ONE scaffold and ONE build-manifest "
                f"mutation of the build file (the first is {sorted(ids)[0]}); if its intent "
                "lacks a coordinate you need, report the gap and the repair pass amends the "
                "ONE task - never schedule a twin over the same file")
    return problems


def _perf_budget_closure_errors(slug, staged, index=None):
    """(z7 2026-11-25 cold6 audit) The performance spec tables each budget with a
    machine-readable `measurement` - kind and assertion text. Enforcement was wired
    (every PB id sits in some stage-2 intent) but NOTHING demanded the bound reach a
    FROZEN TEST: cold6 shipped PB-05 and PB-06 with zero stage-1 citations - a limit
    that exists in code and in the spec, proved nowhere, is a limit that regresses
    silently. The law mirrors the security test_duty rule: a promised measurement
    must be asserted, and the pair-test is the only place a bound survives refactors.
    LINT tier (one context): fires only when THIS context enforces the budget; EMIT
    tier (whole board): every declared budget must be cited by some stage-1 record."""
    path = settings.COMPLETE_DIR / f"performance-spec-{slug}.json"
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = [b for b in (spec.get("budgets") or []) if isinstance(b, dict)
            and str(b.get("id", "")).startswith("PB-")]
    if not rows:
        return []
    records = list(staged) + list((index or {}).values())
    t1_blobs = [json.dumps(r) for r in records
                if isinstance(r, dict) and int(r.get("stage") or 0) == 1]
    own_t1 = [json.dumps(r) for r in staged
              if isinstance(r, dict) and int(r.get("stage") or 0) == 1]
    errors = []
    for b in rows:
        pid = str(b.get("id"))
        enforcers = sorted(str(r.get("id")) for r in records
                           if isinstance(r, dict) and int(r.get("stage") or 0) == 2
                           and pid in json.dumps(r))
        if index is None:
            if pid not in enforcers_text(staged) or not enforcers:
                continue  # this context enforces nothing of it: the batch decides
            pool = own_t1
        else:
            pool = t1_blobs
        if any(pid in blob for blob in pool):
            continue
        meas = b.get("measurement") or {}
        label = enforcers[0] if enforcers else pid
        errors.append(
            f"ERR [{label}]: performance budget {pid} ({b.get('target')}) is enforced "
            "but asserted by NO stage-1 test - the spec tables its measurement "
            f"(kind {meas.get('kind')!r}: {str(meas.get('assertion') or '')[:90]}). "
            f"Table the bound into the enforcing unit's twin test - one intent "
            f"sentence naming {pid} and its limit; a limit proved nowhere is a limit "
            "that regresses silently (rule (z7))")
    return errors


def _slice_isolation_problems(staged):
    """(P2 root fix, 2026-11-25 audit) the (p) slice shares ONE embedded substitute
    across every case of its class - R5 froze test-runner order into a contract by
    asserting a bare global count. The law (STATE IS A CONTRACT TOO) lived only in
    SKILL.md, the carrier sessions open ONLY on an unsummarized pointer - and the
    v7 batch shipped four slices, none naming its isolation choice, one asserting
    global counters. The law moves to the map; its machine leg lives here, where
    one file can decide it: a stage-1 whose intent spells a slice marker must also
    name the choice - a UNIQUE identity per case, a RELATIVE delta against its own
    baseline, or a CLEANUP between cases."""
    errors = []
    marker = re.compile(r"end[- ]to[- ]end|integration slice|request[- ]path", re.I)
    choice = re.compile(r"unique|baseline|delta|cleanup|isolat|its own (?:device|id|key)", re.I)
    for record in staged:
        if not isinstance(record, dict) or int(record.get("stage") or 0) != 1:
            continue
        intent = str(record.get("intent") or "")
        if marker.search(intent) and not choice.search(intent):
            errors.append(
                f"ERR [{record.get('id')}]: the request-path slice drives a shared "
                "substitute but names no isolation choice - STATE IS A CONTRACT TOO: "
                "each case seeds a UNIQUE identity, asserts a RELATIVE delta against "
                "its own baseline, or the support unit provides a CLEANUP between "
                "cases; say which (a bare global count freezes test order into the "
                "contract - rule (p), R5)")
    return errors


def _slice_coverage_errors(slug, stem, staged):
    """PER-CONTEXT COVERAGE AT LINT (2026-11-25): the laws ONE file can be judged by,
    against its own strategy and digest slice - duty claims (`spec_ref` AND
    `capability` VERBATIM in some stage-2 intent), this context's floor step logs, and
    this context's tabled rule literals - run BEFORE LINT-CLEAN prints. A clean lint
    now means the context is COMPLETE, not merely well-formed; only the genuinely
    cross-context laws (the literal join across files, provider closure over the whole
    board, the security reach into a sibling's surface) stay batch laws. Silent when
    the slice files are absent: a draft with no planning session behind it is not
    judged against a slice that was never written."""
    errors = []
    slice_file = Path(f"/tmp/{ddd.PHASE2_SLICE_PREFIX}{slug}-{stem}.json")
    strat_file = Path(f"/tmp/{ddd.STRATEGY_SLICE_PREFIX}{slug}-{stem}.json")
    try:
        digest = json.loads(slice_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return errors
    stage2 = [t for t in staged if isinstance(t, dict)
              and int(t.get("stage") or 0) == settings.TDD_STAGE]
    intents = [str(t.get("intent") or "") for t in stage2]
    for duty in digest.get("duties") or []:
        if not isinstance(duty, dict):
            continue
        ref = str(duty.get("spec_ref") or "").strip()
        cap = str(duty.get("capability") or "").strip()
        if not ref or not cap:
            continue
        if not any(ref in text and cap in text for text in intents):
            errors.append(
                f"ERR [{ref}]: duty '{cap}' is not claimed inside any stage-2 unit of "
                "this file - spell `spec_ref` AND `capability` VERBATIM beside the "
                "mechanism copied from the duty's table_row (rule (y)); the batch would "
                "refuse the same absence, and a billed repair is not the place to "
                "discover it")
    ctx = str(digest.get("context") or "")
    try:
        strat = json.loads(strat_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        strat = {}
    floor = (strat.get("observability") or {}).get("step_logs")
    owned = set()
    for t in stage2:
        for entry in ((t.get("observability") or {}).get("step_logs") or []):
            owned.add(_claim_norm(entry))
    if isinstance(floor, dict) and ctx in floor:
        for entry in floor.get(ctx) or []:
            if _claim_norm(entry) not in owned:
                errors.append(
                    f"ERR [{ctx}]: floor step '{entry}' is claimed by no stage-2 unit "
                    "of this file - reference it in `claims_steps` VERBATIM (rule (j)); "
                    "the engine hydrates the string, you only name it")
    # (2026-11-25 speed pass) the rule-LITERAL numeric check was DELETED: an exact
    # substring demand ("30-240" must appear verbatim) refused honest spellings ("min 30
    # BPM, max 240") and every false refusal cost an edit round - the same year the plan
    # was slow that the budget was spent on. Rule values stay enforced where the law is
    # robust: the emit-side claim and RULE VALUES prose laws, and the `value` field the
    # config coverage copies. The two checks that survived name VERBATIM tokens
    # (spec_ref+capability pair, floor step strings) - a draft either carries the exact
    # token or it does not, so they cannot false-refuse.
    return errors
