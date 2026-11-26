"""task_queue - the task-creation engine top layer: claim, lint, batch emit,
refusal routing. The heavy content lives in four cohesive modules (2026-11-26
split): plan_drafts (state machine), plan_board (queue records),
plan_wiring (deterministic rewrites), plan_laws (validators). This module keeps
the public surface: every historical ``task_queue.X`` caller works unchanged.
"""

import json
import re
from pathlib import Path
import settings
import tasks
import telemetry
import ddd
import shutil
import test_gate

# stable public API across the split (2026-11-26)
from plan_drafts import DRAFT_DIR, LAW_VERSION, MAX_REDRAFTS, PLAN_SNAPSHOT_VERSION, _INPUT_VALIDATORS, _input_hashes, _plan_input_paths, _shape, _snapshot_input_files, apply_coordinate_gaps, clear_drafts, draft_is_fresh, draft_meta_path, draft_path, draft_state, record_redraft_attempt, snapshot_plan_inputs, stamp_draft_meta, verify_plan_inputs
from plan_board import BUILD_MANIFEST_EXPORT, BUILD_MANIFEST_EXPORT, DB_TASKS_SUFFIX, SCAFFOLD_EXPORT, ScaffoldUnresolved, _quarantined_scaffold_reasons, complete_task_ids, database_task_ids, draft_symbol_table, draft_world, load_index, load_valid_tasks, next_task_id, read_queue, recover_lost_scaffold, reopen_completed, replan_domain, retry_error_tasks, scaffold_task_id, send_to_error, stage_task_summary
from plan_wiring import OBSERVABILITY_SURFACES, ROUTE_PROSE_RE, SHORTHAND_KEYS, _claim_norm, _closest_spelling, _config_canon, _config_entry_shape, _duty_context_probe, _route_key, _route_prose, _signature_param_text, _strategy_meter_floor, _unit_family, _wire_guard_visibility, _wire_manifest_edges, _z_has_table, _z_tables, complete_board_draft, enforcers_text, expand_unit_draft, hydrate_batch, mirror_pair_tables, synthesize_triples, wire_config_coverage, wire_pin_edges, wire_root_gate
from plan_laws import CROSS_OWNER_RE, LANGUAGE_RESERVED_SEGMENTS, SECURITY_REF_RE, SECURITY_TOKEN_SECTIONS, SECURITY_TRACE_FIELDS, _inbound_units, _manifest_order_errors, _perf_budget_closure_errors, _pins, _planning_claim_lines, _reserved_segment_errors, _security_claim_errors, _security_declared_ids, _security_reach_errors, _security_secret_inventory, _security_spec, _shared_literal_errors, _slice_coverage_errors, _slice_isolation_problems, _stage0_family_errors, _steplog_claim_errors, _strategy_language, _unit_text, _writable_channel_errors, _z3_prose_problems, planning_claim_gaps, security_claim_gaps




def emit_tasks(paths):
    """Validate a batch of task files against the schema, then write them to the queue.

    A path may hold one task object or an array of them, and several paths may be passed at
    once: the architect drafts one file per bounded context and emits them together, so the whole
    plan is still validated as ONE batch (cross-context pins, provider closure and the security
    reach law each see every file) while no single output turn has to carry a 57-unit document.
    Every validation error is reported in ONE message - stopping at the first error makes the agent
    re-emit, re-fail, re-emit, and every extra turn re-sends the whole transcript. The remedy the
    message asks for is an EDIT pass over the named task objects: a measured 2026-11-18 drain
    rewrote a whole domain plan (10-30k output tokens) where the fix was a few hundred.
    """
    index = load_index()
    board_ids = set(index)
    staged = []
    errors = []
    with telemetry.span("blackboard.emit", {"tasks.requested": len(paths)}) as current:
        loaded_batches = []
        for raw in paths:
            source = Path(raw)
            try:
                loaded = json.loads(source.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                reason = f"{source}: unreadable JSON: {exc}"
                telemetry.mark_error(current, reason)
                return reason
            loaded_batches.append((source, loaded if isinstance(loaded, list) else [loaded]))
        # BATCH-FIRST INDEXING (2026-11-25 bleeding stop): the batch is validated as ONE
        # unit - that is SP3's own contract - but staging used to interleave loading and
        # validating, so a record in file 1 pinning file 3's ids failed tasks.validate on
        # ordering alone. A rejected record never reaches `staged`, the z4 mirror and the
        # coverage/gate wires skip it, and its siblings refuse cascade into phantom
        # defects a premium repair session then "fixes" by hand-inventing pins (v6 live:
        # ERR [T2-009] dependsOn T2-038 not resolvable - the id was real, the order was
        # wrong; T1-009's "delivered twin" message was pure fallout). Pre-index every id
        # the batch itself will define; file order can no longer manufacture refusals.
        batch_ids = {}
        for _source, batch in loaded_batches:
            for task in batch:
                if isinstance(task, dict) and isinstance(task.get("id"), str) and task["id"]:
                    batch_ids.setdefault(task["id"], task)
        index.update(batch_ids)
        seen_batch_ids = set()
        for source, batch in loaded_batches:
            for position, task in enumerate(batch, start=1):
                # The POINTER is the label: a task id where one exists, else file[entry].
                # The LLM does not have to memorize the contract to heal a plan: the
                # refusal names the exact object and the field, and the remedy is an edit
                # (2026-11-20: the profile stopped restating rules (a)-(z) for this).
                label = (task.get("id") if isinstance(task, dict) and task.get("id")
                         else f"{source.name}[{position}]")
                if not isinstance(task, dict):
                    errors.append(f"{label}: task must be a JSON object")
                    continue
                reason = tasks.validate(task, index, planning=True)
                if reason:
                    errors.append(f"{label}: {reason}")
                    continue
                if task["id"] in board_ids:
                    errors.append(f"{task['id']}: id already exists in queue or complete")
                    continue
                if task["id"] in seen_batch_ids:
                    errors.append(f"{task['id']}: id already exists in this batch - one "
                                  "id, one task, across every file of this emit")
                    continue
                seen_batch_ids.add(task["id"])
                staged.append(task)
        # z4 mirror FIRST (2026-11-25): a repair pass edits the code-side table and the
        # twin follows - the drift the v5 run paid two rounds for cannot be manufactured
        # at the batch any more. Silent, idempotent, mechanical.
        mirror_pair_tables(staged)
        pin_edge_notes = wire_pin_edges(staged, index)
        # z6 closure is MECHANICAL (2026-11-25): wire the guard chains before the joins
        # read the tables, exactly as the manifest edges are wired below
        root_gate_notes = wire_root_gate(staged, index)
        wiring_notes = _wire_guard_visibility(staged, index)
        # Cross-task completeness: a unit pinned by anyone as a collaborator must spell
        # the surface its consumers touch - an empty method table there forces two
        # consumers to improvise the same type differently (the seed-002 pair-defect root).
        producers: dict = {}
        for source in list(index.values()) + staged:
            if not isinstance(source, dict):
                continue
            for dep in (source.get("ast_hints") or {}).get("dependencies", []):
                if isinstance(dep, dict) and str(dep.get("task_id", "")).strip():
                    producers.setdefault(str(dep["task_id"]), set()).add(
                        f"{source.get('id')}: {dep.get('type')}")
        for producer_id, consumers in producers.items():
            producer = index.get(producer_id)
            if producer is None:
                errors.append(f"{producer_id}: collaborator pin by "
                              f"{sorted(consumers)[:2]} references no task in the batch, "
                              "queue or complete")
                continue
            if int(producer.get("stage") or 0) not in (1, 2):
                continue
            if not (producer.get("ast_hints") or {}).get("methods"):
                errors.append(
                    f"{producer_id}: pinned as a collaborator by "
                    f"{sorted(consumers)[:3]} but its ast_hints.methods is empty - "
                    "spell the surface (accessors included) every consumer touches")
        # Plan validity across units (seed-002 D1..D3): unowned file duties, config-less
        # runtime plans and request-encoding contradictions die here, at zero sessions.
        coverage_notes, coverage_errors = wire_config_coverage(staged, index)
        errors.extend(coverage_errors)
        errors.extend(tasks.plan_consistency(staged, index))
        errors.extend(_steplog_claim_errors(staged, index))
        errors.extend(_shared_literal_errors(staged, index))
        errors.extend(_security_claim_errors(staged, index))
        _claim_index = dict(index)
        _claim_index.update({str(t.get("id")): t for t in staged if t.get("id")})
        for _slug in sorted({str(t.get("project", "")) for t in staged if t.get("project")}):
            errors.extend(_planning_claim_lines(_slug, [
                record for record in _claim_index.values()
                if isinstance(record, dict) and str(record.get("project", "")) == _slug]))
        errors.extend(_reserved_segment_errors(staged))
        errors.extend(_writable_channel_errors(staged))
        errors.extend(_stage0_family_errors([], index))
        manifest_notes = _wire_manifest_edges(staged, index)
        errors.extend(_manifest_order_errors(staged, index))
        if errors:
            reason = "\n".join([_format_error(e) for e in errors] + [
                "Fix EVERY error above by EDITING the named task objects in the draft file that "
                "holds them - never re-emit an unchanged file, never regenerate the whole plan "
                "(one rewrite of a domain plan is 10-30k output tokens; the same fix as an edit is "
                "a few hundred) - then re-emit the same files in ONE command."])
            telemetry.mark_error(current, reason)
            return reason
        for note in (manifest_notes + pin_edge_notes + root_gate_notes
                      + coverage_notes + wiring_notes):
            print(f"[wire  ] {note}")
        for task in staged:
            destination = settings.QUEUE_DIR / tasks.task_file_name(task)
            # One id, one record across the whole board. A QUARANTINED sibling of the same
            # id is a zombie: producers keyed with include_error=True would resolve types
            # to a task that is live in the queue, so its payload would be treated as
            # pending-absent and every consumer would defer forever (seed-002 rerun 13:51
            # left error/T4-001 beside the re-emitted queue record; a relaunch would hang
            # the boot contract behind its own zombie). Re-issuing an id supersedes its old
            # quarantine - the fresh record carries the CURRENT tree truth.
            zombie = next(iter(settings.ERROR_DIR.glob(
                f"{task['id']}-*.json")), None)
            if zombie is not None:
                zombie.unlink()
                print(f"[emit  ] {task['id']}: superseded stale quarantine record "
                      f"error/{zombie.name}")
            with telemetry.span("blackboard.queue", {"file": destination.name,
                                                     **telemetry.task_attributes(task)}):
                destination.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
            print(f"[emit] {task['id']} -> queue/{destination.name}")
        if current is not None:
            current.set_attribute("tasks.emitted", len(staged))
    return None


def _format_error(line):
    """One refusal = one `ERR [pointer]: reason` line. A line naming a task id (as its
    first token or as the subject of a batch rule) or a file[entry] gets that text as its
    pointer; multi-line details keep their follow-up lines verbatim (they carry the fix
    instruction, not a new error)."""
    if line.startswith(("ERR ", "Fix EVERY", "DEFERRED", "LINT-CLEAN")):
        return line
    match = re.match(r"^([^\n:]{1,110}):([\s\S]*)$", line)
    if not match:
        return line
    pointer = match.group(1).strip()
    head = pointer.split(".", 1)[0].split("/", 1)[0]
    if (settings.ID_PATTERN.match(head)
            or re.search(r"\bT\d-\d{3}\b", pointer)
            or pointer.endswith("]") or ".json" in pointer):
        return f"ERR [{pointer}]:{match.group(2)}"
    return line


# ---------------------------------------------------------------------------
# PER-CONTEXT PLANNING (2026-11-20 architect split). The planner agent now runs ONE
# session per bounded context: it drafts exactly one file and lints it. The engine
# owns the rest of the lifecycle it used to leave to the session's memory:
#   claim_draft      - id-collision renumbering after each session (deterministic,
#                      so a mis-numbered context never bills a repair turn)
#   draft_symbol_table - the exported surface of the drafted contexts, the only
#                      lawful pin source for the NEXT context's session
#   emit_draft_batch - the SINGLE batch emit, run in-process after every context:
#                      cross-context pins, provider closure and the claim law each
#                      still see every file, and the price is zero sessions.


def route_refusals(reason, slug, contexts):
    """(R3 2026-11-25) Batch refusals carry id pointers; id pointers carry blame.
    Routes every `ERR` line to the ONE context file whose claimed bytes define its
    first id; lines with no id, or whose ids span several files (the true
    cross-context laws), route to "domain". A domain-wide repair read every draft
    file and rewrote whole generations for a defect living in one unit - the
    round-cost the plan phase bled on. Returns (buckets, files): buckets maps
    {"domain": [lines], "<context>": [lines]} - empty lists omitted - and files
    carries the repair scope for the domain bucket: the contexts the domain lines
    actually name, or None when a line names none of them (whole-batch law, all
    drafts). (2026-11-26 speed fix) before the scope existed, a two-context join
    refusal billed a repair that read FOUR 60KB drafts and the whole digest for a
    defect living in two files."""
    import collections
    owner = {}
    for context in contexts:
        path = draft_path(slug, context)
        try:
            batch = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for task in (batch if isinstance(batch, list) else [batch]):
            if isinstance(task, dict) and task.get("id"):
                owner.setdefault(str(task["id"]), set()).add(context)
    buckets = collections.defaultdict(list)
    domain_named: set = set()
    domain_scoped = True
    current = None

    def bucket_for(pointer_line):
        nonlocal domain_scoped
        ids = re.findall(r"T\d-\d{3}", pointer_line[:120])
        hits = set()
        for i in ids:
            owners_of_id = owner.get(i)
            if not owners_of_id:
                continue  # queue/complete id or unknown: not a draft-file blame
            hits |= set(owners_of_id)
        if len(hits) == 1:
            return next(iter(hits))
        if hits:
            domain_named.update(hits)
        else:
            domain_scoped = False  # a domain line the files cannot be narrowed to
        return "domain"  # no id, several files blamed, or unresolvable: whole-batch law

    for line in (reason or "").splitlines():
        if line.startswith("ERR"):
            current = line
            buckets[bucket_for(line)].append(line)
        elif current is not None and line.strip():
            # follow-up detail lines belong to the last pointer's bucket
            buckets[bucket_for(current)].append(line)
        elif re.search(r"T\d-\d{3}", line):
            # (2026-11-26 blind-fatal fix) a batch-JOIN refusal names its units but
            # carries no ERR prefix ("slug: step log 'X' claimed by [T2-043, T2-058]"):
            # routing ignored it, the loop saw no bucket, and the domain fatalled with
            # "no routed lines" without ever billing the repair the text asked for.
            # An id-bearing line IS a pointer; blame follows the ids (cross-context =>
            # domain). Instruction boilerplate carries no ids and stays unrouted.
            buckets[bucket_for(line)].append(line)
        elif current is None and f"{slug}:" in line:
            # the join's zero-owner shape has no ids to follow - it is domain law by
            # definition: route it, never silently drop the verdict the loop awaits
            buckets["domain"].append(line)
            domain_scoped = False
        elif not line.strip():
            current = None
    files = {"domain": sorted(domain_named) if (domain_named and domain_scoped) else None}
    return {k: v for k, v in buckets.items() if v}, files


# R1 (2026-11-25 cross-launch damage stop): the plan phase snapshots its binding
# inputs before ANY session runs, re-validates them at every mutation boundary, and
# RESTORES phase 1 bytes on unlawful mutation instead of letting the damage kill the
# NEXT launch after a fully paid plan (live: a repair answered the (k) remedy by
# adding an invented key to the strategy; the next cold launch died at the shape
# gate with zero sessions run). A lawful amendment has the SAME schema shape and
# passes the input's own gate; restructuring is never an amendment.


def lint_draft(path):
    """The agent-facing single-file check: `python3 <runner> --lint <draft file>`.

    Strict where one file can be judged alone - schema, per-task contract, dangling
    pins (a forward pin into an undrafted context is unlawful: the pin source is the
    symbol table), reserved segments, the writable channel - and explicitly DEFERRED
    where the batch is the unit of truth - duty claims, step-log ownership, the cross-unit
    literal join, provider closure across contexts. The batch emit after the last context
    is the authority; the repair session carries its refusals.
    """
    source = Path(path)
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"ERR [{source.name}]: unreadable JSON: {exc}"
    batch = loaded if isinstance(loaded, list) else [loaded]
    batch, expand_errors = expand_unit_draft(batch)
    errors = list(expand_errors)
    task = batch[0] if isinstance(loaded, dict) else None
    # (2026-11-26 truncation fix) the slug is the RECORDS' project, not the filename's
    # first dash-segment: every lawful project slug is hyphenated, and the old
    # split("-",1)[0] read 'conversational-agent' as 'conversational' - the strategy and
    # floor files then resolved to nothing and the meter/step prose laws silently
    # degraded to empty sets INSIDE the session's own lint (the batch tier still refused:
    # live 2026-11-26 a draft linted LINT-CLEAN and the emit refused the spelling lint had
    # been built to catch). Filename only as the last resort.
    slug = (str((task or {}).get("project") or "")
            or next((str(rec.get("project")) for rec in batch
                     if isinstance(rec, dict) and rec.get("project")), "")
            or source.name.split("-", 1)[0])
    world = draft_world(slug, exclude=source)
    # references resolve exactly as claim will resolve them: the session sees the
    # deterministic refusal at lint, before any of it is ever billed to a repair pass
    hy_problems, _hy_notes = hydrate_batch(batch, slug, world)
    errors.extend(hy_problems)
    # mechanical completion at BOTH tiers (R4): a board file may omit T1.ast_hints
    # and omit T3 records entirely - lint judges the COMPLETED draft, exactly as claim
    # will persist it, so no session is refused for not typing boilerplate
    complete_board_draft(batch)
    index = dict(world)
    staged = []
    reasons = {}
    for position, entry in enumerate(batch, start=1):
        label = (entry.get("id") if isinstance(entry, dict) and entry.get("id")
                 else f"{source.name}[{position}]")
        if not isinstance(entry, dict):
            errors.append(f"{label}: task must be a JSON object")
            continue
        reason = tasks.validate(entry, index, planning=True)
        if reason:
            errors.append(f"{label}: {reason}")
        reasons[label] = reason or ""
        if isinstance(entry.get("id"), str) and entry["id"] not in index:
            index[entry["id"]] = entry
        staged.append(entry)
    # Forward pins are the split's one new temptation: name them exactly, with the
    # lawful alternative (the symbol table, or draft the provider first). A dependsOn
    # the per-task validator already called unresolvable is not reported twice - the
    # extra value here is the FIELD pointer and the pin law, not a second refusal.
    for entry in staged:
        if not isinstance(entry, dict):
            continue
        tid = str(entry.get("id") or "?")
        seen = reasons.get(tid, "")
        refs = [(str(d), "dependsOn") for d in (entry.get("dependsOn") or []) if str(d).strip()]
        for dep in (entry.get("ast_hints") or {}).get("dependencies", []) if isinstance(
                entry.get("ast_hints"), dict) else []:
            if isinstance(dep, dict) and str(dep.get("task_id", "")).strip():
                refs.append((str(dep["task_id"]), "ast_hints.dependencies"))
        for ref, field in refs:
            if ref not in index:
                if field == "dependsOn" and f"dependsOn {ref}" in seen:
                    continue
                errors.append(
                    f"{tid}.{field}/{ref}: references no task in the queue, the drafted "
                    "contexts, or this file - a context not yet drafted cannot be pinned; "
                    "pin only through the symbol table, or let the provider context's units "
                    "depend on yours")
    errors.extend(_reserved_segment_errors(staged))
    errors.extend(_writable_channel_errors(staged))
    errors.extend(_stage0_family_errors(staged, world))
    errors.extend(_manifest_order_errors(staged, world))
    stem = (source.name[len(slug) + 1:-len(".json")]
            if source.name.startswith(slug + "-") else "")
    if stem:
        errors.extend(_slice_coverage_errors(slug, stem, staged))
    # per-record joins that need no sibling file (2026-11-25 bleeding stop): the batch
    # caught them too, but a batch refusal costs a premium repair session - the same
    # verdict at lint costs one edit inside the drafting session's own budget
    errors.extend(tasks.per_record_signal_problems(staged))
    errors.extend(_z3_prose_problems(staged, _strategy_meter_floor(slug)))
    errors.extend(_slice_isolation_problems(staged))
    errors.extend(_perf_budget_closure_errors(slug, staged))
    if errors:
        return "\n".join([_format_error(e) for e in errors])
    return ("LINT-CLEAN (this context's slice coverage ran: duties and floor steps "
            "accounted for; the cross-context laws remain DEFERRED to "
            "the engine's single --emit: the shared-literal join, provider closure "
            "across contexts, whole-board step-log ownership, the security reach into "
            "a sibling's surface).")


def claim_draft(slug, context):
    """Engine step after one planning session: the draft file joins the domain's id space.

    An id that collides with the queue, complete, or an already-drafted context is
    RENUMBERED here deterministically (the references inside the same file follow), so a
    session that miscounted never burns a repair turn on arithmetic the machine can do.
    Returns (problems, renames): problems are what the session still owns (malformed JSON,
    dangling pins); renames are reported for the symbol table's sake."""
    path = draft_path(slug, context)
    if not path.is_file():
        return [f"draft file missing: {path}"], {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        stamp_draft_meta(slug, context, clean=False, state="broken")
        return [f"{path.name}: unreadable JSON: {exc}"], {}
    batch = loaded if isinstance(loaded, list) else [loaded]
    if not batch or not all(isinstance(task, dict) for task in batch):
        stamp_draft_meta(slug, context, clean=False, state="broken")
        return [f"{path.name}: must be a JSON array of task objects"], {}
    was_compact = any(isinstance(t, dict) and "stage" not in t
                      and ("n" in t or "test" in t or "code" in t) for t in batch)
    batch, expand_errors = expand_unit_draft(batch)
    world = draft_world(slug, exclude=path)
    problems, renames = [], {}
    problems.extend(expand_errors)
    if expand_errors:
        stamp_draft_meta(slug, context, clean=False)
        return problems, {}
    # 2026-11-25 hydration: references resolve in Python (see hydrate_batch); a refusal
    # here is the same one the session already saw at lint - ids are never rewritten on
    # a draft that will not claim, so the bytes stay as the session left them
    hydrated = any(isinstance(t, dict) and any(k in t for k in SHORTHAND_KEYS)
                   for t in batch)
    hy_problems, hy_notes = hydrate_batch(batch, slug, world)
    if hy_problems:
        stamp_draft_meta(slug, context, clean=False)
        return hy_problems, {}
    for note in hy_notes:
        print(f"[wire  ] {slug}: {note}")
    mirrored, synthesized = complete_board_draft(batch)
    if synthesized:
        print(f"[wire  ] {slug}: {synthesized} stage-3 record(s) issued by the engine "
              "(R4 triple completion - the refactor task is derived, never typed)")
    for note in wire_pin_edges(batch, world):
        print(f"[wire  ] {slug}: {note}")
    counters = {}
    originals = []  # (task, old id) recorded BEFORE any rename - the reference pass needs both spaces
    for task in batch:
        stage_match = settings.ID_PATTERN.match(str(task.get("id", "")))
        if not stage_match:
            problems.append(f"ERR [{path.name}]: task without a valid id")
            continue
        stage = int(stage_match.group(1))
        old = task["id"]
        originals.append((task, old))
        if old in world:
            numbers = [int(m.group(2)) for tid in world
                       if (m := settings.ID_PATTERN.match(tid)) and int(m.group(1)) == stage]
            numbers += [int(m.group(2)) for m in (
                settings.ID_PATTERN.match(str(t.get("id", ""))) for t in batch)
                if m and int(m.group(1)) == stage]
            counters.setdefault(stage, max(numbers) + 1)
            new_id = f"T{stage}-{counters[stage]:03d}"
            counters[stage] += 1
            renames[old] = new_id
            task["id"] = new_id
    if renames or was_compact or hydrated or mirrored or synthesized:
        own_export = {old: str(task.get("export") or "") for task, old in originals
                      if old in renames}
        for task, _old in originals:
            task["dependsOn"] = [renames.get(str(dep), str(dep)) for dep in task["dependsOn"]]
            hints = task.get("ast_hints")
            if isinstance(hints, dict):
                for dep in hints.get("dependencies", []):
                    if not (isinstance(dep, dict) and str(dep.get("task_id", "")) in renames):
                        continue
                    ref = str(dep["task_id"])
                    # A pinned type is attributed by its NAME first: a reference whose type
                    # matches an OWN renamed unit follows the rename; one whose type belongs
                    # to the drafted world (the valid backward pin through the symbol table)
                    # keeps the world id. Only a reference no world task answers stays self.
                    if str(dep.get("type") or "") == own_export.get(ref) or ref not in world:
                        dep["task_id"] = renames[ref]
        path.write_text(json.dumps(batch, indent=1), encoding="utf-8")
    ids_here = {str(task.get("id")) for task in batch if isinstance(task, dict)}
    for task in batch:
        if not isinstance(task, dict):
            continue
        for ref in [str(d) for d in (task.get("dependsOn") or [])]:
            if ref not in world and ref not in ids_here:
                problems.append(f"ERR [{task.get('id')}].dependsOn: dangling reference {ref} "
                                "- not in the queue, the drafted contexts, or this file")
    # (R2) stamp regardless of rewrites: the hashes are the contract of what this
    # draft was validated against; a changed input flips freshness deterministically.
    # (2026-11-26 laundering fix) the stamp records the VERDICT too: a draft that was
    # JUDGED and REJECTED must not relaunch as "fresh - claimed without a session",
    # because re-claim + repair on identical bytes replays the same storm every launch.
    # claim=clean is the only state that skips a session; claim=rejected escalates the
    # context to a real drafting session next pass - the repair's sibling escape hatch.
    stamp_draft_meta(slug, context, clean=not problems)
    return problems, renames


def emit_draft_batch(slug, contexts):
    """The ONE batch emit, run by the ENGINE after every context file is drafted:
    cross-context pins, provider closure and the claim law each see every file (the law
    F1 kept), at zero sessions. Returns the emit_tasks reason (None on success)."""
    paths = [draft_path(slug, context) for context in contexts]
    return emit_tasks([str(p) for p in paths if p.is_file()])
