"""plan_wiring - the engine's deterministic draft rewritings: compact unit
expansion, stage-3 triple synthesis, T1/T2 table mirroring, shorthand
hydration, pin/gate/config/manifest wiring. Python does the bookkeeping no
session should pay tokens for; refusals it cannot resolve are reported, never
silently patched."""

import json
import re
from pathlib import Path
import settings
import ddd
import tasks
from plan_board import BUILD_MANIFEST_EXPORT
from plan_drafts import draft_path


def resolve_sibling_anchors(slug, contexts):
    """Bind {type, context} dependency anchors drafted in parallel (2026-11-26).

    The pin law made planning SERIAL: a session could name no sibling id because
    claim renumbers ids and the sibling's file may not even exist yet. Sessions now
    run concurrently and pin siblings by ANCHOR - (type, context name), the two facts
    a drafting session legitimately holds. After every context is claimed (ids final),
    this pass replaces each resolvable anchor with the producer's task_id and mirrors
    the pair edge onto the test side; an anchor no context answers becomes an ERR line
    for the routed repair rounds. The engine binds, never guesses: a type found in a
    DIFFERENT than named context is still a refusal (the anchor named its owner).
    Returns (problems, notes)."""
    batches, index = {}, {}
    for context in contexts:
        path = draft_path(slug, context)
        try:
            batch = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(batch, list):
            batch = [batch]
        batches[context] = (path, batch)
        for record in batch:
            if not isinstance(record, dict):
                continue
            stage = int(record.get("stage") or 0)
            export = tasks.exported_product(record) or ""
            tid = str(record.get("id") or "")
            if export and tid and stage == 2:
                index[(context, export)] = tid

    def _pair(tid):
        return ("T1-" + tid.split("-", 1)[1], "T2-" + tid.split("-", 1)[1])

    problems, notes = [], []
    for context, (path, batch) in batches.items():
        touched = False
        for record in batch:
            if not isinstance(record, dict) or int(record.get("stage") or 0) not in (1, 2):
                continue
            hints = record.get("ast_hints")
            if not isinstance(hints, dict):
                continue
            for dep in hints.get("dependencies") or []:
                if not (isinstance(dep, dict) and dep.get("context") and not dep.get("task_id")):
                    continue
                anchor_type, anchor_ctx = str(dep["type"]), str(dep["context"])
                # the anchor's context name must be a drafted context (exact or case-insensitive)
                matched_ctx = next((c for c in contexts if c == anchor_ctx),
                                   next((c for c in contexts
                                         if c.strip().casefold() == anchor_ctx.strip().casefold()), None))
                tid = index.get((matched_ctx, anchor_type)) if matched_ctx else None
                if tid is None and matched_ctx:
                    tid = index.get((matched_ctx, anchor_type.rsplit(".", 1)[-1]))
                if tid is None:
                    known = sorted(t for (c, t) in index if c == matched_ctx) if matched_ctx else []
                    problems.append(
                        f"ERR [{record.get('id')}]: pins {anchor_type!r} in context "
                        f"{anchor_ctx!r}, which exports no such unit"
                        + (f" - candidates: {', '.join(known[:8])}" if known else
                           " - the context is not drafted on this board")
                        + " (rule (k) sibling anchor); fix the anchor's type/context or"
                        " the producer's export")
                    continue
                t1_id, t2_id = _pair(tid)
                dep["task_id"] = t2_id
                del dep["context"]
                edges = record.setdefault("dependsOn", [])
                want = t2_id if int(record.get("stage") or 0) == 2 else t1_id
                if want not in edges:
                    edges.append(want)
                    notes.append(f"{record.get('id')}: dependsOn += {want} "
                                 f"(sibling anchor {anchor_ctx}/{anchor_type})")
                if int(record.get("stage") or 0) == 2:
                    t1 = next((r for r in batch if isinstance(r, dict)
                               and str(r.get("id")) == "T1-" + str(record.get("id", ""))[3:]), None)
                    if t1 is not None:
                        t1_edges = t1.setdefault("dependsOn", [])
                        if t1_id not in t1_edges:
                            t1_edges.append(t1_id)
                            notes.append(f"{t1.get('id')}: dependsOn += {t1_id} "
                                         f"(pair edge of the bound sibling pin)")
                touched = True
        if touched:
            path.write_text(json.dumps(batch, indent=1), encoding="utf-8")
    return problems, notes




def _claim_norm(text) -> str:
    return " ".join(str(text or "").strip().lower().rstrip(".").split())


OBSERVABILITY_SURFACES = ("correlation_key", "step_logs", "audit_trail", "metrics", "export")
ROUTE_PROSE_RE = re.compile(r"(?<![\w/:.\-])(/[A-Za-z][\w{}-]*(?:/[\w{}.*-]+)*)")


def _config_canon(path):
    """Relaxed-binding canonical form: each dotted segment camel->kebab, lowercase - so the
    binder's `secretHash` and the seed's `secret-hash` are ONE literal, as the runtime
    itself reads them."""
    return ".".join(re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", str(path).strip()).lower()
                    .split("."))


def _signature_param_text(signature):
    text = str(signature or "")
    return text[text.index("("):] if "(" in text else ""


def _config_entry_shape(record):
    """(path, kind, fields, value) - value joins the shape tuple 2026-11-25: the seeded
    DEFAULT is part of the one-owner fact (rule (l)'s impossible pair made mechanical:
    two binders of one path may differ only where one of them spells no value)."""
    return [(str(e.get("path")), str(e.get("kind")),
             tuple(sorted(_config_canon(f) for f in (e.get("fields") or []))),
             ("" if e.get("value") is None else str(e.get("value")).strip()))
            for e in _z_tables(record, "config") if isinstance(e, dict) and e.get("path")]


def wire_root_gate(staged, index):
    """PHASE 1.5 composition closure (2026-11-25): the ROOT gate is drafted BEFORE the
    bounded contexts, so the managers, handlers and credential stores that live INSIDE
    the admission chain - claimed by contexts that do not exist yet - can never be
    typed into its table at drafting time. At the batch they are all visible, and the
    join is pure data: every claimed duty whose digest row is a chain-composition row
    (the mechanism cells name the root chain - a composition chain in every stack's
    vocabulary) or is UNATTRIBUTED (no surface owns it: the gate is its natural host)
    adds its claimant's product to the gate's collaborator table and its code-task id
    to dependsOn, mirrored onto the twin (z4). Under-pinning the gate is the R3/
    NoSuchBeanDefinition death the join refuses; over-pinning costs one import in a
    test that never uses it - so every chain-role claimant is pinned, and the gate
    still cites no address (routes belong to hydrate_batch's root_gate injection)."""
    world = dict(index)
    world.update({str(t.get("id")): t for t in staged if isinstance(t, dict) and t.get("id")})
    twins = {}
    for record in world.values():
        if isinstance(record, dict) and int(record.get("stage") or 0) in (1, 2):
            twins.setdefault(_unit_family(record), {})[int(record["stage"])] = record
    staged_ids = {str(t.get("id")) for t in staged if isinstance(t, dict) and t.get("id")}
    notes = []
    gates = [t for t in staged if isinstance(t, dict) and t.get("root_gate")
             and str(t.get("id")) in staged_ids
             and int(t.get("stage") or 0) == settings.TDD_STAGE]
    for gate in gates:
        slug = str(gate.get("project", ""))
        try:
            digest = json.loads((Path("/tmp") / f"phase2-digest-{slug}.json")
                                .read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            notes.append(f"{gate.get('id')}: root gate kept as drafted - no readable "
                         "digest to close its chain composition")
            continue
        surfaces = digest.get("surfaces") or []
        rules_map = digest.get("rules") or {}
        stage2_claims = [t for t in staged if isinstance(t, dict)
                         and int(t.get("stage") or 0) == settings.TDD_STAGE]
        pinned = {str(d.get("task_id")) for d in _z_tables(gate, "dependencies")
                  if isinstance(d, dict)}
        for duty in digest.get("duties") or []:
            if not isinstance(duty, dict):
                continue
            ref = str(duty.get("spec_ref") or "").strip()
            cap = str(duty.get("capability") or "").strip()
            if not ref or not cap:
                continue
            row = duty.get("table_row") or {}
            cells = " ".join(str(c) for c in (row.get("cells") or [])).lower()
            attributed = _duty_context_probe(duty, rules_map, surfaces)
            chain_role = "chain" in cells
            if not (chain_role or attributed is None):
                continue
            claimant = next((t for t in stage2_claims
                             if ref in str(t.get("intent") or "")
                             and cap in str(t.get("intent") or "")), None)
            if claimant is None or str(claimant.get("id")) in pinned \
                    or _unit_family(claimant) == _unit_family(gate):
                continue
            product = tasks.exported_product(claimant) or str(claimant.get("export"))
            entry = {"type": str(product), "task_id": str(claimant.get("id"))}
            for holder in (gate, twins.get(_unit_family(gate), {}).get(1)):
                if isinstance(holder, dict) and isinstance(holder.get("ast_hints"), dict):
                    table = holder["ast_hints"].setdefault("dependencies", [])
                    if not any(isinstance(e, dict) and str(e.get("task_id")) == entry["task_id"]
                               for e in table):
                        table.append(dict(entry))
            depends = gate.setdefault("dependsOn", [])
            if entry["task_id"] not in [str(d) for d in depends]:
                depends.append(entry["task_id"])
            pinned.add(entry["task_id"])
            notes.append(f"{gate.get('id')}: chain composition closed - pins {product} "
                         f"({entry['task_id']}, duty {ref}) claimed by the batch")
    return notes


def _duty_context_probe(duty, rules_map, surfaces):
    """The digest's own attribution rule, re-evaluated for the gate wire (unattributed
    duties are the ROOT's; a duty with a surface belongs to a bounded context)."""
    owner = str(duty.get("owner_context") or "").strip()
    if owner:
        return owner
    entry = (rules_map.get(str(duty.get("spec_ref", ""))) or {}).get("entry") or {}
    surface = str(entry.get("surface") or "").strip()
    if surface:
        norm = ddd.norm_surface(surface)
        for s in surfaces:
            if isinstance(s, dict) and ddd.norm_surface(s.get("name")) == norm:
                ctx = str(s.get("context") or "").strip()
                if ctx:
                    return ctx
    return None


def wire_pin_edges(staged, index):
    """(P1 root fix, 2026-11-25 audit) a collaborator pin without its code-task edge:
    the payload contract has said "the producer must also be in `dependsOn`" since it
    existed, three carriers repeat it, and NOTHING enforced it - so a session that
    pinned without the edge shipped a red compile ordered by luck (the drain runs
    dependsOn only; the tester doubles from the table, but the TYPE the code side
    imports must already exist). Pin-to-edge closure is pure graph arithmetic: the
    engine completes the edge, mechanically, like the manifest and guard wires."""
    world = dict(index)
    world.update({str(t.get("id")): t for t in staged if isinstance(t, dict) and t.get("id")})
    notes = []
    for task in staged:
        if not isinstance(task, dict) or int(task.get("stage") or 0) != settings.TDD_STAGE:
            continue
        depends = task.setdefault("dependsOn", [])
        have = {str(d) for d in depends}
        for pin in (task.get("ast_hints") or {}).get("dependencies") or []:
            if not isinstance(pin, dict):
                continue
            pid = str(pin.get("task_id") or "").strip()
            prod = world.get(pid)
            if (pid and pid not in have and isinstance(prod, dict)
                    and int(prod.get("stage") or 0) == settings.TDD_STAGE
                    and pid != str(task.get("id"))):
                depends.append(pid)
                have.add(pid)
                notes.append(f"{task.get('id')}: dependsOn += {pid} "
                             "(pin edge wired by the engine - the table already owned it)")
    return notes


def wire_config_coverage(staged, index):
    """PHASE 1.5 completion (2026-11-25, the user's "engine merges all contexts into
    the ONE generated config unit at --emit"): the configuration-artifact unit's table
    is the UNION of every path the board tables, copied VERBATIM from the binding
    entries - a value the binder spells fills an empty seed slot; conflicting values
    are left to the z5 join to refuse (one path, one fact). Sessions never copy a path
    into the config unit and never patch it through a gaps file: the coverage is a
    wire, disclosed like the manifest edges."""
    world = dict(index)
    world.update({str(t.get("id")): t for t in staged if isinstance(t, dict) and t.get("id")})
    notes, errors = [], []
    batch_ids = {str(t.get("id")) for t in staged if isinstance(t, dict) and t.get("id")}
    projects = {str(t.get("project", "")) for t in staged if isinstance(t, dict) and t.get("project")}
    for slug in sorted(projects):
        hosts = [t for t in staged if isinstance(t, dict)
                 and int(t.get("stage") or 0) == settings.TDD_STAGE
                 and str(t.get("project", "")) == slug
                 and tasks._path_is_config_artifact(t.get("path"))]
        if not hosts:
            continue  # no host in THIS batch: the join below refuses bound-but-unhosted
                      # paths only when a config unit exists nowhere on the board
        if any(str(t.get("id")) not in batch_ids
               and int(t.get("stage") or 0) == settings.TDD_STAGE
               for t in index.values() if isinstance(t, dict)
               and str(t.get("project", "")) == slug
               and tasks._path_is_config_artifact(t.get("path"))):
            # a DELIVERED config unit is frozen - emit_tasks folds the batch's own
            # records into `index` while staging, so "delivered" must mean "on the
            # board and NOT in this batch" (2026-11-25: the first wire cut treated
            # the batch's own host as delivered and silently wired nothing - SF15
            # caught it as a written record with no table)
            continue  # coverage of a delivered artifact moves with --replan
        host = hosts[0]
        table = host.setdefault("ast_hints", {}).setdefault("config", [])
        # the twin mirror (z4): records arrive from disk as SEPARATE dicts, so every
        # wired entry lands on the unit's stage-1 twin too - the pair must stay one table
        twin = next((r for r in world.values() if isinstance(r, dict)
                     and int(r.get("stage") or 0) == 1
                     and _unit_family(r) == _unit_family(host)
                     and str(r.get("project", "")) == slug), None)
        def _host_tables():
            yield table
            if isinstance(twin, dict):
                yield twin.setdefault("ast_hints", {}).setdefault("config", [])
        seeded = {}
        for entry in table:
            if isinstance(entry, dict) and entry.get("path"):
                seeded[_config_canon(entry["path"])] = entry
        for record in world.values():
            if (not isinstance(record, dict) or record is host
                    or int(record.get("stage") or 0) != settings.TDD_STAGE
                    or str(record.get("project", "")) != slug):
                continue
            for entry in _z_tables(record, "config"):
                if not (isinstance(entry, dict) and entry.get("path")):
                    continue
                canon = _config_canon(entry["path"])
                if canon not in seeded:
                    for holder in _host_tables():
                        if not any(isinstance(e, dict) and _config_canon(e.get("path")) == canon
                                   for e in holder):
                            holder.append(json.loads(json.dumps(entry)))
                    seeded[canon] = entry
                    notes.append(f"{host.get('id')}: tables {entry['path']} copied from "
                                f"{record.get('id')} (config coverage wired by the engine)")
                elif (str(seeded[canon].get("value") or "").strip() == ""
                      and str(entry.get("value") or "").strip()):
                    seeded[canon]["value"] = entry["value"]
                    notes.append(f"{host.get('id')}: {entry['path']} default seeded from "
                                f"{record.get('id')}'s tabled value")
    return notes, errors

def _unit_family(record):
    """The id number one unit's T1/T2/T3 records share - owners are counted per unit."""
    ident = str(record.get("id", ""))
    return ident.rsplit("-", 1)[-1] if "-" in ident else ident


def _route_key(method, path):
    return (str(method or "").strip().upper(), "/" + str(path or "").strip().strip("/"))


def _route_prose(text):
    """Route-shaped literals in a unit's text: leading-slash, >=2 segments, first alphabetic.
    File paths (extension in the last segment) stay rule (a)'s territory; media types,
    placeholders and relative paths cannot match (the lookbehind eats their preceding char)."""
    found = []
    for match in ROUTE_PROSE_RE.finditer(str(text or "")):
        literal = match.group(1).rstrip("/")
        last = literal.rsplit("/", 1)[-1]
        if ".." in literal or re.search(r"\.\w{1,5}$", last):
            continue
        if literal not in found:
            found.append(literal)
    return found


def _closest_spelling(name, candidates):
    import difflib
    near = difflib.get_close_matches(str(name), sorted(candidates), n=1, cutoff=0.75)
    return f" - closest tabled spelling: '{near[0]}'" if near else ""


def _z_tables(record, key):
    hints = record.get("ast_hints") if isinstance(record.get("ast_hints"), dict) else {}
    entries = hints.get(key)
    return entries if isinstance(entries, list) else []


def _z_has_table(record, key):
    hints = record.get("ast_hints") if isinstance(record.get("ast_hints"), dict) else {}
    return isinstance(hints.get(key), list)


def mirror_pair_tables(records):
    """z4 as a WIRE (2026-11-25 bleeding stop): the carriers have always promised the
    engine mirrors the pair's table - true for the compact form since 2026-11-24, but a
    BOARD-object draft kept T1 and T2 as separate typed copies, so every repair edit of a
    code-side table manufactured a fresh twin-dr refusal and burned a whole round
    (v5 live: repair #1 fixed seven lines and created two). The CODE side owns the
    interface; its table is mirrored byte-identical onto the test twin. Idempotent."""
    by_family = {}
    for record in records:
        if isinstance(record, dict) and int(record.get("stage") or 0) in (1, 2):
            by_family.setdefault(_unit_family(record), {})[int(record["stage"])] = record
    mirrored = 0
    for sides in by_family.values():
        t1, t2 = sides.get(1), sides.get(2)
        if not (isinstance(t1, dict) and isinstance(t2, dict)):
            continue
        hints = t2.get("ast_hints")
        if isinstance(hints, dict) and t1.get("ast_hints") != hints:
            t1["ast_hints"] = json.loads(json.dumps(hints))
            mirrored += 1
    return mirrored


def _strategy_meter_floor(slug):
    """The strategy's floor meter names - the same flattening the batch join uses."""
    strategy = {}
    try:
        strategy = json.loads((settings.COMPLETE_DIR
                               / f"execution-strategy-{slug}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    obs = strategy.get("observability") if isinstance(strategy, dict) else {}
    floor = set()
    for entry in (obs or {}).get("metrics") or []:
        name = str((entry or {}).get("name") if isinstance(entry, dict) else entry).strip()
        if name:
            floor.add(name)
    return floor



# THE WRITABLE CHANNEL (2026-11-19, the prompt-contract trap the operator review caught):
# a stage-1/2 unit's `path` is the file its agent will actually create - and the pipeline
# has exactly two writers: the language weavers (source files) and the text-payload route
# the config units use (.yml/.yaml/.properties full-file writes). Template files -
# prompts/*.st, docs/*.md, fixtures/*.txt - have NO writer on this board: the coder emits a
# payload the dispatcher routes to a weaver that cannot splice a template, the stage-0
# channel belongs to the container/migration authors, and the architect cannot write project
# files at all. A unit planned onto such a path is a duty without a lawful channel (the D4
# class), discovered at its first red gate - so emit refuses it and the plan moves the
# artifact where it can live: a prompt contract becomes a Java TYPE whose tabled members
# carry the contract elements; other facts belong to a source type or the config document.
def _wire_manifest_edges(staged, index):
    """Build-manifest edges are MECHANICAL, not decisions (2026-11-24 seed-002): the
    context drafted FIRST cannot depend on a manifest a LATER context is about to
    schedule, so every unit of the first context arrived at the batch unable to reach
    the manifest - a law unsatisfiable at drafting time refused 46 objects and billed
    repair sessions to type an id into a list. The refusal's own remedy names the fix
    exactly (add the manifest id to `dependsOn`; the pair's twin inherits through it),
    so Python joins the edge BEFORE the gate runs and discloses every append;
    `_manifest_order_errors` keeps its teeth as the assertion it was written to be."""
    world = dict(index)
    world.update({str(task.get("id")): task for task in staged
                  if isinstance(task, dict) and task.get("id")})
    manifests = {}
    for tid, task in world.items():
        if not isinstance(task, dict) or int(task.get("stage") or 0) != 0:
            continue
        if str(task.get("export", "")).strip() == BUILD_MANIFEST_EXPORT:
            manifests.setdefault(str(task.get("project", "")), []).append(str(tid))
    notes = []
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
        if reached is None:
            task.setdefault("dependsOn", []).append(targets[0])
            notes.append(f"{task.get('id')}: dependsOn += {targets[0]} "
                         "(build-manifest edge wired by the engine - mechanical, not billed)")
    return notes


def expand_unit_draft(batch):
    """THE COMPACT UNIT FORM -> the canonical triad, deterministically (2026-11-24 planner
    performance pass). The session submits ONE record per unit - both paths, both intents,
    ONE ast_hints, the two dependsOn lists - and this function materializes the T1+T2+T3
    triad the board has always validated. Why in Python: (a) T1/T2 must carry the
    BYTE-IDENTICAL table (rule z4) - typing it twice is 2x output tokens plus drift that
    costs a lint round each time, copying it once is free and exact; (b) targetAgent/stage/
    kind/T3-shape are boilerplate, and AS10's whole point is that arithmetic never gets
    billed to a session; (c) a 68-object draft shrinks ~35-45%, halving the single-turn
    streaming wall. A fully-formed task record (has `stage`) passes through untouched, so
    both draft shapes are lawful inputs until the draft is claimed. Returns (tasks, errors)
    with ERR pointers in the derived-object space (T1-007 = unit 7 test side)."""
    out, errors = [], []
    for position, entry in enumerate(batch, start=1):
        if not isinstance(entry, dict) or "stage" in entry:
            out.append(entry)          # canonical record (or garbage for validate to name)
            continue
        if "n" not in entry and "test" not in entry and "code" not in entry:
            out.append(entry)          # not a unit record: the id-less refusal names it
            continue
        n = entry.get("n")
        label = f"unit[{n}]" if isinstance(n, int) else f"unit[{position}]"
        if not isinstance(n, int) or n < 1:
            errors.append(f"ERR [{label}].n: a unit needs a positive integer n "
                          "(the id number its triad will carry)")
            continue
        test, code = entry.get("test") or {}, entry.get("code") or {}
        if not isinstance(test, dict) or not isinstance(code, dict) or not test or not code:
            errors.append(f"ERR [{label}]: a unit needs both objects test (the stage-1 test "
                          "side) and code (the stage-2 production side)")
            continue
        missing = [f"{side}.{key}" for side, d in (("test", test), ("code", code))
                   for key in ("path", "export", "intent")
                   if not str(d.get(key) or "").strip()]
        if missing:
            errors.append(f"ERR [{label}]: {', '.join(missing)} empty - each side carries "
                          "its path, export and intent")
            continue
        hints = code.get("ast_hints")
        if hints is not None and not isinstance(hints, dict):
            errors.append(f"ERR [{label}].code.ast_hints: must be an object - the SAME table "
                          "lands byte-identical on T1 and T2 (z4 by construction)")
            continue
        shared = {"layer": entry.get("layer"), "feature": entry.get("feature"),
                  "project": entry.get("project")}
        deps = entry.get("dependsOn") or []
        if isinstance(deps, list):
            # flat list = unit-wide dependencies (scaffold, manifest, db ids): the model's
            # canonical-form habit, honored as BOTH sides' base rather than dropped (2026-11-24)
            deps = {"test": deps, "code": deps}
        t1_deps = [str(d) for d in (deps.get("test") or [])]
        t2_extra = [str(d) for d in (deps.get("code") or [])]
        # stage-0 bootstrap ids are UNIT facts, not side facts (2026-11-24): the code side
        # compiles against the same scaffold/manifest/database classpath the TEST side
        # compiles against - red precedes green, so the tester's first compile needs them
        # too. Propagate any T0-* listed on either side to both (the law's "its T1 twin
        # inherits through the pair", enforced by construction); side-specific T1/T2 pins
        # stay side-specific.
        t0_shared = sorted({d for d in t1_deps + t2_extra if d.startswith("T0-")})
        if t0_shared:
            t1_deps = t0_shared + [d for d in t1_deps if not d.startswith("T0-")]
            t2_extra = t0_shared + [d for d in t2_extra if not d.startswith("T0-")]
        tid1, tid2, tid3 = f"T1-{n:03d}", f"T2-{n:03d}", f"T3-{n:03d}"
        t1 = {"id": tid1, "targetAgent": settings.STAGE_AGENTS[1], "stage": 1,
              "dependsOn": t1_deps, "kind": settings.STAGE_KINDS[1][0],
              "path": test["path"], "export": test["export"], "intent": test["intent"],
              **shared}
        t2 = {"id": tid2, "targetAgent": settings.STAGE_AGENTS[2], "stage": 2,
              "dependsOn": [tid1] + [d for d in t2_extra if d != tid1],
              "kind": settings.STAGE_KINDS[2][0],
              "path": code["path"], "export": code["export"], "intent": code["intent"],
              **shared}
        if hints is not None:
            t1["ast_hints"] = json.loads(json.dumps(hints))
            t2["ast_hints"] = json.loads(json.dumps(hints))
        if code.get("observability") is not None:
            t2["observability"] = json.loads(json.dumps(code["observability"]))
        # REFERENCE keys ride to the code side for hydrate_batch (2026-11-25): the session
        # declares WHAT it consumes; the engine looks the owner up and tables the literal.
        for key in SHORTHAND_KEYS:
            if code.get(key) is not None:
                t2[key] = json.loads(json.dumps(code[key]))
        intent3 = str(entry.get("refactor_intent") or "").strip() or (
            f"Refactor {code['export']}: keep the tabled contract and the paired tests "
            "green; no behavior, status, meter or route change.")
        t3 = {"id": tid3, "targetAgent": settings.STAGE_AGENTS[3], "stage": 3,
              "dependsOn": [tid2], "kind": settings.STAGE_KINDS[3][0],
              "path": code["path"], "export": code["export"], "intent": intent3, **shared}
        out.extend([t1, t2, t3])
    return out, errors


SHORTHAND_KEYS = ("uses_meters", "uses_routes", "uses_config", "claims_steps", "root_gate")
# prompt emits /tmp/tasks/{slug}-db-tasks.json directly) is NOT a planning draft: it
# shares DRAFT_DIR and the {slug}- prefix, so without this exception draft_world treats
# already-queued stage-0 records as pins-of-a-draft-generation (2026-11-25 fresh-board
# audit: the stale channel from the v2 run sat beside the cleaned blackboard and its ids
# would have answered _next_free_for's T0 numbers as "used" against a board that moved on)

def hydrate_batch(batch, slug, world):
    """THE MECHANICAL JOINS ARE PYTHON'S, NOT SESSIONS' (2026-11-25 bottleneck pass). A
    draft record may REFERENCE a shared fact instead of copying it; this step resolves
    each reference against the batch and the drafted world and tables the canonical entry
    VERBATIM where the emit law demands it, stripping the reference key after. Why: the
    verbatim-copy law (z)/(z5)/(j) is symbol-table bookkeeping across 40-60 objects -
    the class of work an LLM drifts on and a repair session pays for at premium rates
    (2026-11-25 v7: four refusal families were exactly this - unowned step logs,
    uncited meter spellings, orphaned config shapes). Contract:
      uses_meters  [name]      -> ast_hints.meters {name, duty: uses} from the OWNING unit
      uses_routes  ["M /path"] -> ast_hints.routes {method, path, duty: uses} from the SERVING unit
      uses_config  [path]      -> ast_hints.config {path, kind, fields?} from the BINDING unit
      claims_steps [string]    -> observability.step_logs, VERBATIM from the strategy floor
      root_gate    true        -> the engine tables every addressed surface of the
                                  composition root (own AND foreign) into this unit's
                                  routes: the ONE gate accounts for the whole root, and
                                  the session types zero foreign citations
    An unresolvable reference is a one-line deterministic problem naming the closest
    tabled spelling - fail fast at lint, never a billed repair guess. `root_gate` is the
    ONE reference key that STAYS on the record: it is a machine-checked marker (one gate
    per project, the symbol table shows it to later contexts)."""
    problems, notes = [], []
    by_id = dict(world)
    for record in batch:
        if isinstance(record, dict) and record.get("id"):
            by_id[str(record["id"])] = record
    twins = {}
    for record in batch:
        if isinstance(record, dict) and int(record.get("stage") or 0) in (1, 2):
            twins.setdefault(_unit_family(record), {})[
                int(record["stage"])] = record
    strategy = {}
    try:
        strategy = json.loads((settings.COMPLETE_DIR
                               / f"execution-strategy-{slug}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        strategy = {}
    floor = {}
    for entry in tasks.step_log_entries(
            (strategy.get("observability") or {}).get("step_logs")):
        key = _claim_norm(entry)
        if key:
            floor[key] = str(entry).strip()
    metric_floor = set()
    for m in ((strategy.get("observability") or {}).get("metrics") or []):
        if isinstance(m, dict) and str(m.get("name", "")).strip():
            metric_floor.add(str(m["name"]).strip())
        elif isinstance(m, str) and m.strip():
            metric_floor.add(m.strip())
    surfaces = [s for s in (strategy.get("surfaces") or []) if isinstance(s, dict)]
    claimed_steps = {}
    for source, record in by_id.items():
        if isinstance(record, dict) and int(record.get("stage") or 0) == 2:
            for entry in ((record.get("observability") or {}).get("step_logs") or []):
                claimed_steps.setdefault(_claim_norm(entry), str(record.get("id")))
    for record in batch:
        if not (isinstance(record, dict) and int(record.get("stage") or 0) == 2):
            for key in SHORTHAND_KEYS:
                if isinstance(record, dict) and record.pop(key, None) is not None:
                    problems.append(f"ERR [{record.get('id')}].{key}: references belong to "
                                    "the stage-2 side - the pair's table mirrors them")
            continue
        label = str(record.get("id"))
        hints = record.setdefault("ast_hints", {}) if isinstance(
            record.get("ast_hints", {}) or {}, dict) else None
        if hints is None:
            problems.append(f"ERR [{label}].ast_hints: must be an object to hydrate")
            continue
        twin = twins.get(_unit_family(record), {}).get(1)
        def _append_both(key, entry):
            holders = [hints]
            if isinstance(twin, dict) and isinstance(twin.get("ast_hints"), dict):
                holders.append(twin["ast_hints"])
            for holder in holders:
                table = holder.setdefault(key, [])
                if key == "meters" and not any(
                        isinstance(e, dict) and str(e.get("name")) == str(entry.get("name"))
                        for e in table):
                    table.append(json.loads(json.dumps(entry)))
                elif key == "routes" and not any(
                        isinstance(e, dict) and _route_key(e.get("method"), e.get("path"))
                        == _route_key(entry.get("method"), entry.get("path")) for e in table):
                    table.append(json.loads(json.dumps(entry)))
                elif key == "config" and not any(
                        isinstance(e, dict) and _config_canon(e.get("path"))
                        == _config_canon(entry.get("path")) for e in table):
                    table.append(json.loads(json.dumps(entry)))
        for name in (record.pop("uses_meters", None) or []):
            owner, owner_id = None, None
            for source, candidate in by_id.items():
                if not isinstance(candidate, dict):
                    continue
                for entry in _z_tables(candidate, "meters"):
                    if (isinstance(entry, dict) and entry.get("duty") == "owns"
                            and str(entry.get("name", "")).strip() == str(name).strip()):
                        owner, owner_id = entry, str(source)
            if owner is None and str(name).strip() in metric_floor:
                # a floor meter is a strategy TABLED name: the first context may lawfully
                # reference a sibling's meter before the owning unit is drafted - the
                # batch join still demands exactly one `owns` when the batch completes (z1)
                _append_both("meters", {"name": str(name).strip(), "duty": "uses"})
                notes.append(f"{label}: meter '{str(name).strip()}' cited from the floor "
                             "(the registering unit owes the 'owns' entry at batch)")
                continue
            if owner is None:
                problems.append(f"ERR [{label}].uses_meters: no unit owns '{name}' and no "
                                "floor meter carries it - the registering unit must table "
                                "it with duty 'owns' (or the strategy must plan it)"
                                + _closest_spelling(name, {
                                    str(e.get("name")) for r in by_id.values()
                                    if isinstance(r, dict) for e in _z_tables(r, "meters")}))
                continue
            _append_both("meters", {"name": str(owner.get("name")), "duty": "uses"})
        for ref in (record.pop("uses_routes", None) or []):
            parts = str(ref).split(None, 1)
            if len(parts) != 2:
                problems.append(f"ERR [{label}].uses_routes: '{ref}' is not "
                                "'<METHOD> /path' - spell the reference like the serving "
                                "unit tables it")
                continue
            method, path = parts[0].upper(), "/" + parts[1].strip().lstrip("/")
            server = None
            for _source, candidate in by_id.items():
                for entry in _z_tables(candidate, "routes"):
                    if (isinstance(entry, dict) and entry.get("duty") == "serves"
                            and _route_key(entry.get("method"), entry.get("path"))
                            == _route_key(method, path)):
                        server = entry
            if server is None:
                row = next((s for s in surfaces
                            if str(s.get("method", "")).strip().upper() == method
                            and "/" + str(s.get("path", "")).strip().lstrip("/") == path), None)
                if row is not None:
                    # the address is a strategy TABLED surface: a sibling's inbound unit
                    # will answer it in the same batch - the join still demands the server
                    _append_both("routes", {"method": method, "path": path, "duty": "uses"})
                    notes.append(f"{label}: route {method} {path} cited from the strategy "
                                 "surface table (the serving unit owes 'serves' at batch)")
                    continue
                problems.append(f"ERR [{label}].uses_routes: no unit serves {method} {path} "
                                "and the strategy tables no such address - the inbound unit "
                                "must table it with duty 'serves' first"
                                + _closest_spelling(path, {
                                    str(e.get("path")) for r in by_id.values()
                                    if isinstance(r, dict) for e in _z_tables(r, "routes")}))
                continue
            _append_both("routes", {"method": str(server.get("method")),
                                    "path": str(server.get("path")), "duty": "uses"})
        for path in (record.pop("uses_config", None) or []):
            binder = None
            shapes = []
            for _source, candidate in by_id.items():
                for entry in _z_tables(candidate, "config"):
                    if (isinstance(entry, dict)
                            and _config_canon(entry.get("path")) == _config_canon(path)):
                        shapes.append({k: v for k, v in entry.items()
                                       if k in ("kind", "fields")})
                        binder = binder or entry
            if binder is None:
                problems.append(f"ERR [{label}].uses_config: no unit tables '{path}' - the "
                                "binding unit owns the shape; table it there first"
                                + _closest_spelling(path, {
                                    str(e.get("path")) for r in by_id.values()
                                    if isinstance(r, dict) for e in _z_tables(r, "config")}))
                continue
            if len({json.dumps(s, sort_keys=True) for s in shapes}) > 1:
                problems.append(f"ERR [{label}].uses_config: '{path}' is tabled in two "
                                "shapes - one path, one shape (rule (z5)): fix the binders, "
                                "the reference cannot pick")
                continue
            entry = json.loads(json.dumps(binder))
            entry["path"] = str(entry.get("path"))
            _append_both("config", entry)
        steps = record.pop("claims_steps", None)
        if steps:
            obs = record.setdefault("observability", {})
            table = obs.setdefault("step_logs", [])
            if isinstance(twin, dict):
                twin.setdefault("observability", {}).setdefault("step_logs", table)
            for step in (steps if isinstance(steps, list) else [steps]):
                key = _claim_norm(step)
                if key not in floor:
                    problems.append(f"ERR [{label}].claims_steps: '{step}' is not on the "
                                    "strategy floor - claim the floor's string VERBATIM"
                                    + _closest_spelling(str(step).strip(), set(floor.values())))
                    continue
                if claimed_steps.get(key) not in (None, label):
                    problems.append(f"ERR [{label}].claims_steps: '{floor[key]}' is already "
                                    f"claimed by {claimed_steps[key]} - one owner per step "
                                    "(rule (j))")
                    continue
                if floor[key] not in table:
                    table.append(floor[key])
                    claimed_steps[key] = label
                    notes.append(f"{label}: claims '{floor[key]}' VERBATIM from the floor")
        if record.get("root_gate"):
            others = [str(r.get("id")) for r in by_id.values()
                      if isinstance(r, dict) and r.get("root_gate")
                      and str(r.get("project", "")) == str(record.get("project", ""))
                      and str(r.get("id")) != label]
            if others:
                problems.append(f"ERR [{label}].root_gate: {others[0]} already carries the "
                                "ONE root gate for this project - PIN that unit (add its "
                                "type to your dependencies); never a second gate (y4)")
                record["root_gate"] = False
            else:
                for s in surfaces:
                    if not (str(s.get("method", "")).strip() and str(s.get("path", "")).strip()):
                        continue
                    _append_both("routes", {"method": str(s["method"]).upper(),
                                            "path": "/" + str(s["path"]).strip().lstrip("/"),
                                            "duty": "uses"})
                notes.append(f"{label}: root gate - the engine tabled every addressed "
                             "surface of the composition root (y4 hydration; a session "
                             "never cites a foreign address itself)")
    return problems, notes


def _wire_guard_visibility(staged, index):
    """Rule (z6) as a WIRING, not a typing job (2026-11-25): a surface unit that serves a
    route some guard cites must pin every project product the guard's own table declares,
    or no slice importing the chain can construct it. The graph walk that computes the
    missing set is deterministic; leaving it to the session cost a repair family per run
    (2026-11-19 R3 died it manually). Python appends the missing collaborator entries to
    BOTH twins' tables and the producer's code-task id to the surface's dependsOn, then
    `_shared_literal_errors` keeps its teeth as the assertion it was written to be."""
    world = dict(index)
    world.update({str(task.get("id")): task for task in staged
                  if isinstance(task, dict) and task.get("id")})
    twins = {}
    for record in world.values():
        if isinstance(record, dict) and int(record.get("stage") or 0) in (1, 2):
            twins.setdefault(_unit_family(record), {})[
                int(record["stage"])] = record
    by_product = {}
    for record in world.values():
        if isinstance(record, dict) and int(record.get("stage") or 0) == settings.TDD_STAGE:
            product = tasks.exported_product(record)
            if product:
                by_product.setdefault(str(product).lower(), record)
    served_by_family = {}
    for record in world.values():
        if not isinstance(record, dict):
            continue
        for entry in _z_tables(record, "routes"):
            if isinstance(entry, dict) and entry.get("duty") == "serves":
                served_by_family.setdefault(_unit_family(record), set()).add(
                    _route_key(entry.get("method"), entry.get("path")))
    notes = []
    staged_ids = {str(t.get("id")) for t in staged if isinstance(t, dict)}
    for record in staged:
        if not isinstance(record, dict) or int(record.get("stage") or 0) != settings.TDD_STAGE:
            continue
        family = _unit_family(record)
        if family not in served_by_family:
            continue
        pinned = {str(d.get("task_id")) for d in _z_tables(record, "dependencies")
                  if isinstance(d, dict)}
        for guard in world.values():
            if (guard is record or not isinstance(guard, dict)
                    or int(guard.get("stage") or 0) != settings.TDD_STAGE):
                continue
            guard_cites = {_route_key(e.get("method"), e.get("path"))
                           for e in _z_tables(guard, "routes")
                           if isinstance(e, dict) and e.get("duty") == "uses"}
            if not (guard_cites & served_by_family[family]):
                continue
            wanted = []
            for dep in _z_tables(guard, "dependencies"):
                if isinstance(dep, dict):
                    name = str(dep.get("type", "")).rsplit(".", 1)[-1]
                    if name.lower() in by_product:
                        wanted.append((name, str(dep.get("task_id"))))
            for member in _z_tables(guard, "methods"):
                if isinstance(member, dict):
                    for token in tasks.CAMEL_TYPE_RE.findall(
                            _signature_param_text(member.get("signature"))):
                        if token.lower() in by_product:
                            wanted.append((token,
                                           str(tasks.exported_product(by_product[token.lower()]))))
            for name, _hint in wanted:
                producer = by_product.get(name.lower())
                if producer is None:
                    continue
                pid = str(producer.get("id"))
                if (pid in pinned or pid == str(record.get("id"))
                        or _unit_family(producer) == family):
                    continue
                entry = {"type": name, "task_id": pid}
                for holder in (record, twins.get(family, {}).get(1)):
                    if isinstance(holder, dict) and isinstance(holder.get("ast_hints"), dict):
                        table = holder["ast_hints"].setdefault("dependencies", [])
                        if not any(isinstance(e, dict) and str(e.get("task_id")) == pid
                                   for e in table):
                            table.append(dict(entry))
                depends = record.setdefault("dependsOn", [])
                if pid not in [str(d) for d in depends]:
                    depends.append(pid)
                pinned.add(pid)
                notes.append(f"{record.get('id')}: dependsOn += {pid} and pins {name} "
                             "(guard chain closed by the engine - z6, mechanical)")
    return notes


def enforcers_text(staged):
    return " ".join(json.dumps(r) for r in staged
                    if isinstance(r, dict) and int(r.get("stage") or 0) == 2)


def synthesize_triples(batch):
    """(R4 2026-11-25 machine-enforced draft economy) A BOARD-object draft that omits a
    unit's stage-3 record is COMPLETE, not deficient: the refactor task is pure
    boilerplate derived from the code side, exactly like the compact form's triad.
    The engine issues the missing T3 records (id from the family, default intent,
    stage-2's path); a family without both sides is left untouched (a lone record is a
    real defect the joins must still name). Returns the number synthesized."""
    sides = {}
    for record in batch:
        if isinstance(record, dict) and int(record.get("stage") or 0) in (1, 2, 3):
            sides.setdefault(_unit_family(record), set()).add(int(record["stage"]))
    added = 0
    by_id = {str(r.get("id")): r for r in batch if isinstance(r, dict) and r.get("id")}
    for family, stages in sorted(sides.items()):
        if 3 in stages or not {1, 2} <= stages:
            continue
        t2 = next((r for r in batch if isinstance(r, dict)
                   and int(r.get("stage") or 0) == 2 and _unit_family(r) == family), None)
        if t2 is None:
            continue
        t3 = {"id": f"T3-{family}", "targetAgent": settings.STAGE_AGENTS[3], "stage": 3,
              "dependsOn": [str(t2.get("id"))], "kind": settings.STAGE_KINDS[3][0],
              "path": t2.get("path"), "export": t2.get("export"),
              "layer": t2.get("layer"), "feature": t2.get("feature"),
              "project": t2.get("project"),
              "intent": (f"Refactor {t2.get('export')}: keep the tabled contract and the "
                         "paired tests green; no behavior, status, meter or route change.")}
        batch.append(t3)
        by_id[t3["id"]] = t3
        added += 1
    return added


def complete_board_draft(batch):
    """Mechanical draft completion (R4): pair mirror then triple synthesis. Idempotent;
    returns (mirrored, synthesized)."""
    mirrored = mirror_pair_tables(batch)
    synthesized = synthesize_triples(batch)
    return mirrored, synthesized
