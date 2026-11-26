"""plan_flow - the phase-2 planning loop: one bounded-context session per
context, engine-side claim, routed bounded repair, ONE batch emit, the
post-amendment shape gate. Sessions decide, Python joins and judges.

(Extracted from pipeline.py, 2026-11-26.)"""
from pathlib import Path

import settings
import ddd
import prompts
import task_queue
import workspace
from plan_wiring import resolve_sibling_anchors



PLANNER_REPAIR_ROUNDS = 2  # engine-side refusals are ROUTED (R3): every guilty bucket
# gets TWO bounded repair passes over ITS OWN lines; a third pass over the same ERR text is
# the retry-storm shape the drain pays for in sessions; the operator's --replan is the
# lawful third try. The bucket fingerprint guard additionally starves any bucket whose
# repair changed no byte, so a round is only ever billed on a bucket that can move.


# gets TWO bounded repair passes over ITS OWN lines; a third pass over the same ERR text is
# the retry-storm shape the drain pays for in sessions; the operator's --replan is the
# lawful third try. The bucket fingerprint guard additionally starves any bucket whose
# repair changed no byte, so a round is only ever billed on a bucket that can move.


def _plan_domain_tasks(args, backend, slug):
    """The 2026-11-20 architect split in one function: ONE planner session per bounded
    context, the ENGINE emitting the batch.

    The session sees only what it needs - the strategy, ITS digest slice (duties with
    their rule rows and matched mechanism rows pre-attached), and the symbol table of
    already-drafted contexts - so the draft of context N never rides the turns of
    context N+1 (the per-turn transcript re-send is what made the monolith burn: one
    40,442-token single turn measured 2026-11-16). The batch laws survive untouched:
    claims, provider closure and cross-context pins still see every file at once,
    because the batch `--emit` is a Python call, not an agent turn. Id arithmetic,
    collisions and dangling joins are repaired by Python first (claim_draft); only a
    real plan defect costs a repair session, and at most two."""
    digest, problems = ddd.write_phase2_digest(slug)
    for line in problems[:5]:
        print(f"[fatal] digest {slug}: {line}")
    if problems:
        return False, ("the phase-2 digest refused - a duty or covers id resolves to no "
                       "rule row; relaunch with --replan " + slug)
    print(f"[digst] {slug}: {digest.name} carries duties, joined rules, matched table rows")
    # R1: snapshot the binding inputs BEFORE any session can touch them
    task_queue.snapshot_plan_inputs(slug)
    # PHASE 1.5 (2026-11-25 root restructure): the ONE stage-0 build-manifest is ENGINE
    # data - the stack table's Build coordinates rows filtered against the PLANNED
    # capability set - queued deterministically before any session. The first-drafter
    # bootstrap and the missing_coordinates channel are deleted; every context sees the
    # same scheduled manifest in the stage-0 summary and reaches it mechanically.
    manifest_id, manifest_notes, manifest_problems = ddd.plan_build_manifest(slug)
    for line in manifest_notes:
        print(f"[wire  ] {slug}: {line}")
    for line in manifest_problems:
        print(f"[fatal] manifest prepass {slug}: {line}")
    if manifest_problems:
        return False, ("the engine could not queue the ONE build manifest: "
                       + "; ".join(manifest_problems[:3]))
    contexts = [ddd.ROOT_CONTEXT] + ddd.context_draft_order(slug)
    if len(contexts) == 1:
        return False, f"{slug}: the strategy declares no bounded contexts to plan"
    # selective clear (2026-11-20 resume economics): drafts newer than every plan input
    # are the previous (crashed or budget-killed) run's RESULT and are claimed without a
    # session; only stale bytes - written before a spec/strategy rewrite - are dropped.
    removed = []
    for context in contexts:
        path = task_queue.draft_path(slug, context)
        state = task_queue.draft_state(slug, context)
        # selective clear (2026-11-20 resume economics; 2026-11-26 unjudged kept):
        # drafts newer than every plan input are the previous (crashed or budget-killed)
        # run's RESULT - an UNJUDGED draft (no sidecar yet) never re-bills a session, it
        # goes to the claim gate below; only stale bytes - written before a spec/strategy
        # rewrite - and damaged files are dropped.
        if path.is_file() and state in ("broken", "stale"):
            path.unlink()
            removed.append(path.name)
            task_queue.draft_meta_path(slug, context).unlink(missing_ok=True)
        # (PHASE 1.5) the .gaps.json channel is deleted; a lingering file from an old
        # board is stale noise and goes with its draft
        legacy = str(path)[:-len(".json")] + ".gaps.json"
        if Path(legacy).is_file():
            Path(legacy).unlink()
    if removed:
        print(f"[draft ] {slug}: cleared stale drafts {', '.join(removed)}")
    drafted = []
    # (2026-11-26 parallel plan) slice preparation first for EVERY context: it is pure
    # Python (digest joins) and a refusal there must not be discovered after sessions
    # were billed. The per-context loop then keeps its original order when
    # settings.PLAN_PARALLEL <= 1 - the serial path is byte-identical to the flow that
    # produced today's green plan; the parallel path only changes WHEN sessions run.
    slices = {}
    for context in contexts:
        slice_path, slice_problems = ddd.write_phase2_digest_slice(slug, context)
        if slice_problems:
            return False, f"{slug}/{context}: " + "; ".join(slice_problems[:3])
        slices[context] = slice_path

    def _state_gate(context):
        """Prints the resume/validate/redraft line; (proceed, needs_session, reason)."""
        state = task_queue.draft_state(slug, context)
        if state == "fresh":
            print(f"[resume] {slug}/{ddd.context_stem(context)}: draft kept - current facts, "
                  "clean verdict; claimed without a session")
            return True, False, ""
        if state == "unjudged":
            # no sidecar (killed run), a LAW bump, or a pre-verdict stamp: the claim gate
            # re-VALIDATES these bytes for free - a session is billed only when the law
            # actually refuses them (fact/law split, 2026-11-26).
            print(f"[draft ] {slug}/{ddd.context_stem(context)}: not validated against the "
                  "current law/facts yet - the claim gate re-validates it free")
            return True, False, ""
        if state == "exhausted":
            return False, False, (f"{slug}/{context}: refused the claim gate after "
                                  f"{task_queue.MAX_REDRAFTS} re-draft sessions - the "
                                  "escalation ladder is spent; inspect the draft, its "
                                  "digest slice and the refusal history, fix the plan (or "
                                  f"the law), then --replan {slug}")
        if state == "rejected":
            attempt = task_queue.record_redraft_attempt(slug, context)
            print(f"[redraft] {slug}/{ddd.context_stem(context)}: the board refused this "
                  f"draft under the current law - re-draft "
                  f"{attempt}/{task_queue.MAX_REDRAFTS} (bounded escalation)")
        return True, True, ""

    def _run_session(context, siblings=None, next_free=None):
        """One planner session for one context; the failed-session-with-bytes rule is
        identical serial or parallel: the claim gate, not the session exit, judges."""
        symbols_path = None
        if drafted:
            symbols_path = (task_queue.DRAFT_DIR
                            / f"{slug}-symbols-{ddd.context_stem(context)}.json")
            symbols_path, write_problems = task_queue.draft_symbol_table(
                slug, drafted, symbols_path)
            if write_problems:
                return False, "; ".join(write_problems)
        message = prompts.build_planner_prompt(
            workspace.get_project_root(), getattr(backend, "RUNNER_SCRIPT", ""),
            slug, context, task_queue.draft_path(slug, context), slices[context],
            symbols_path, next_free if next_free is not None else _next_free_for(slug),
            [c for c in contexts if c not in drafted and c != context],
            siblings=siblings)
        ok, reason = backend.run_planner(args, slug, context, message)
        if not ok:
            # the hard-kill guard protects the transcript, not the draft (2026-11-26:
            # a compliant session was killed at the cap ONE lint round from done and
            # its finished draft was thrown away): a failed session that left bytes
            # loses nothing until the claim gate says so - only total absence of a
            # draft re-plans, and refusals ride the repair rounds below.
            if task_queue.draft_state(slug, context) == "absent":
                return False, f"{slug}/{context}: {reason}"
            print(f"[draft ] {slug}/{ddd.context_stem(context)}: the session failed "
                  f"({reason[:120]}) but its draft stands - the claim gate judges it, "
                  "refusals route to the bounded repair rounds")
        return True, ""

    def _claim_and_repair(context):
        claim_problems, renames = task_queue.claim_draft(slug, context)
        for old, new in sorted(renames.items()):
            print(f"[id    ] {slug}: {old} -> {new} (draft ids joined to the board's number space)")
        round_left = PLANNER_REPAIR_ROUNDS
        while claim_problems and round_left:
            round_left -= 1
            print(f"[repair] {slug}/{context}: {len(claim_problems)} draft problem(s), "
                  f"{round_left} repair session(s) left")
            for line in claim_problems[:8]:
                # a supervisor that cannot see the refusal text cannot root-cause a stop
                print(f"[repair]   {line[:240]}")
            before = _repair_fingerprint(slug, [context])
            backend.run_planner_repair(
                args, slug, prompts.build_planner_repair_prompt(
                    getattr(backend, "RUNNER_SCRIPT", ""), slug, "\n".join(claim_problems[:40]),
                    [task_queue.draft_path(slug, context)], digest))
            if _repair_fingerprint(slug, [context]) == before:
                return False, (f"{slug}/{context}: the repair session changed no draft "
                               "byte - refusing identically would burn the next round; "
                               "operator decision or --replan " + slug)
            claim_problems, more = task_queue.claim_draft(slug, context)
            renames.update(more)
        if claim_problems:
            return False, (f"{slug}/{context}: the draft still refuses after "
                           f"{PLANNER_REPAIR_ROUNDS} repair session(s): "
                           + "\n".join(claim_problems[:5]))
        drafted.append(context)
        return True, ""

    parallel = settings.PLAN_PARALLEL > 1 and len(contexts) > 2
    if not parallel:
        for context in contexts:
            proceed, needs_session, why = _state_gate(context)
            if not proceed:
                return False, why
            if needs_session:
                ok, why = _run_session(context)
                if not ok:
                    return False, why
            ok, why = _claim_and_repair(context)
            if not ok:
                return False, why
    else:
        # PHASE P: the billed part of planning is model DECODE of a 40-90KB draft; the
        # pin law used to serialize it context by context. The root pass stays first
        # (the symbol table every sibling pins its gate/config ids from), then bounded
        # contexts draft CONCURRENTLY - each writes only its own draft file, and each
        # lint runs on its own file: sessions share no writable state. Claims stay
        # sequential (ids, sidecar verdicts), and {type, context} anchors the siblings
        # left instead of unknown ids are bound by resolve_sibling_anchors below, all
        # before the ONE batch emit. Wall time moves from sum(sessions) to root + max.
        root = contexts[0]
        proceed, needs_session, why = _state_gate(root)
        if not proceed:
            return False, why
        if needs_session:
            ok, why = _run_session(root)
            if not ok:
                return False, why
        ok, why = _claim_and_repair(root)
        if not ok:
            return False, why
        bounded = contexts[1:]
        to_run = []
        for context in bounded:
            proceed, needs_session, why = _state_gate(context)
            if not proceed:
                return False, why
            if needs_session:
                to_run.append(context)
        next_free = _next_free_for(slug) if to_run else None
        outcomes = {}
        workers = []
        import threading

        def _worker(context):
            outcomes[context] = _run_session(
                context, siblings=[c for c in bounded if c != context], next_free=next_free)

        slot = max(1, int(settings.PLAN_PARALLEL))
        queue_threads = [threading.Thread(target=_worker, args=(c,), daemon=True) for c in to_run]
        live = []
        for t in queue_threads:
            while len(live) >= slot:
                for x in list(live):
                    if not x.is_alive():
                        live.remove(x)
                if len(live) >= slot:
                    live[0].join(1)
            t.start()
            live.append(t)
        for t in live:
            t.join()
        for context in to_run:  # report in board order, first failure decides
            ok, why = outcomes.get(context, (False, f"{slug}/{context}: session thread died"))
            if not ok:
                return False, why
        for context in bounded:
            ok, why = _claim_and_repair(context)
            if not ok:
                return False, why
    # (PHASE 1.5 2026-11-25) the X11 gap consumption lived here; the channels are
    # gone - the manifest is engine-queued and config coverage is wired at the emit.
    # (R3 2026-11-25) refusals are ROUTED: an `ERR [id]` pointer knows its owner, and
    # the owner is exactly one context file. A one-unit defect dragged every draft file
    # and the whole digest into each billed whole-domain repair round - the shape the
    # plan bled on. Each bucket now gets its lines, its files, and its own rounds;
    # genuinely cross-context lines ("domain" bucket) keep the whole-batch treatment.
    # (2026-11-26 parallel plan) the batch judgment FIRST binds sibling anchors: an
    # unresolvable pin is a refusal with the consumer's id pointer, so it routes to
    # the same bounded repair rounds; resolvable ones become concrete pair edges.
    def _batch():
        problems, bound = resolve_sibling_anchors(slug, drafted)
        for note in bound:
            print(f"[wire  ] {slug}: {note} (engine binding - sibling anchor)")
        if problems:
            return "\n".join(problems)
        return task_queue.emit_draft_batch(slug, drafted)

    reason = _batch()
    # (2026-11-26 calibration fix, measured live): the global cap predates R3's bucket
    # routing - it was sized for TWO whole-batch passes, when one repair session touched
    # every draft. With routed buckets one sweep bills a session PER GUILTY BUCKET: four
    # buckets spent the entire 4-round budget in the first pass and the loop died before
    # any bucket could take its promised second round - fatal, every repair billed on
    # progress, one line from convergence. The honest bound: each bucket (drafted
    # contexts + the "domain" bucket) may burn its own rounds; the per-bucket cap and the
    # fingerprint starvation stay the real storm guards.
    total_rounds, max_rounds = 0, PLANNER_REPAIR_ROUNDS * (len(drafted) + 1)
    bucket_rounds = {}
    stuck = {}
    while reason and total_rounds < max_rounds:
        buckets, scope = task_queue.route_refusals(reason, slug, drafted)
        routed = sum(len(v) for v in buckets.values())
        blame = ", ".join(f"{k} [{len(v)} line(s)]" for k, v in sorted(buckets.items()))
        print(f"[emit  ] {slug}: the batch refused ({routed} routed line(s)); blame: "
              f"{blame or 'no routed lines'}")
        for line in [l for l in reason.splitlines() if l.startswith("ERR")][:8]:
            print(f"[emit  ]   {line[:240]}")
        progress = False
        for bucket, lines in sorted(buckets.items()):
            # (2026-11-26 speed fix) a domain repair reads ONLY the files its lines name
            # unless a line names none of them - the whole-board reading is for true
            # whole-board laws, not for a join that spans two contexts.
            files = ((scope.get("domain") or drafted) if bucket == "domain" else [bucket])
            if bucket_rounds.get(bucket, 0) >= PLANNER_REPAIR_ROUNDS:
                continue  # this bucket had its rounds; the domain verdict stands
            bucket_rounds[bucket] = bucket_rounds.get(bucket, 0) + 1
            total_rounds += 1
            before = _repair_fingerprint(slug, files)
            backend.run_planner_repair(
                args, slug, prompts.build_planner_repair_prompt(
                    getattr(backend, "RUNNER_SCRIPT", ""), slug, "\n".join(lines),
                    [task_queue.draft_path(slug, c) for c in files],
                    digest if bucket == "domain" else
                    # a routed repair reads its OWN context's slice of the digest -
                    # the duties it is accountable for, not the whole domain's
                    ddd.phase2_slice_path(slug, bucket)))
            # R1: a repair may amend strategy TEXT lawfully; restructuring is
            # rolled back at the boundary, never carried to the next launch
            restored, amended = task_queue.verify_plan_inputs(slug)
            for name in restored:
                print(f"[heal  ] {slug}: {name} restored to the phase-1 snapshot - a "
                      "session mutated it outside its amendment rights")
            for name in amended:
                print(f"[warn  ] {slug}: {name} carries a lawful rule (t)/(k) text "
                      "amendment; phase-1 bytes stay snapshotted")
            if _repair_fingerprint(slug, files) == before:
                # (2026-11-25 cold5 starvation fix) A no-op is the guilty BUCKET's
                # verdict, not the domain's: exhaust that bucket so its next round is
                # NOT billed, and let the other buckets take their turns. The old
                # code returned False HERE - one unroutable line in the validation
                # bucket fatals the batch and starves a perfectly fixable
                # distribution error behind it (the very whole-domain blindness R3
                # exists to end, re-entering through the guard).
                bucket_rounds[bucket] = PLANNER_REPAIR_ROUNDS
                stuck[bucket] = lines
                print(f"[emit  ] {slug}: {bucket} changed no draft byte - the bucket "
                      "is exhausted and its lines ride to the final verdict; other "
                      "buckets keep their rounds (2026-11-24 live guard, per bucket)")
                continue
            progress = True
        if not progress:
            break
        reason = _batch()
    if reason:
        first = [line for line in reason.splitlines() if line.startswith("ERR")][:5]
        starved = "; exhausted without progress: " + ", ".join(sorted(stuck)) if stuck else ""
        return False, ("the batch still refuses after "
                       f"{total_rounds} repair round(s){starved}; relaunch with --replan "
                       f"{slug} - " + " | ".join(first))
    if not any((match := settings.ID_PATTERN.match(task_id)) and int(match.group(1)) >= 1
               for task_id in task_queue.load_index()):
        return False, f"{slug}: the planner queued no application tasks"
    # post-amendment shape gate (2026-11-25): sessions hold ONE strategy-amendment
    # authority (rule (t)); a desperate repair abused it and added an out-of-process KEY
    # no gate reads, and the next launch died at the pre-session shape gate after a
    # full paid plan. Re-validating here fails the SAME launch that made the damage,
    # zero extra sessions, pointing at the phase that owns the schema.
    reason = ddd.validate_strategy(slug)
    if reason:
        return False, (f"strategy {slug} no longer satisfies its shape after the planning "
                       f"pass - {reason}; an amendment may only reword sentences of "
                       f"existing fields; relaunch with --replan {slug} if the schema "
                       "itself must change")
    print(f"[plan  ] {slug}: {len(drafted)} bounded-context session(s), one batch emit")
    return True, ""




def _repair_fingerprint(slug, contexts):
    """Digest of every draft + gap file a repair session could lawfully change (2026-11-24
    operator incident: the first repair round died mid-start, the engine re-ran the batch
    against UNCHANGED bytes, refused identically, and billed the second round anyway).
    A repair that changes nothing cannot change the next emit's verdict - stop and hand
    the operator the refusal instead of another session."""
    import hashlib
    h = hashlib.sha256()
    for context in contexts:
        for path in (task_queue.draft_path(slug, context),):
            try:
                h.update(path.read_bytes())
            except OSError:
                h.update(b"<absent>")
    return h.hexdigest()




def _next_free_for(slug):
    """The next-free ids the planner's file starts from: the board's index plus every
    drafted file already claimed for THIS domain (the symbol table carries the same
    numbers; stating them in the brief is the one id rule the session must see early)."""
    world = task_queue.draft_world(slug)
    stages = {}
    # stage 0 included (2026-11-24): the ONE build-manifest bootstrap a planner may
    # schedule needs the next-free T0 printed in its brief, not guessed at - a hand-picked
    # id either collides (claim renumbers, fine) or leaves gaps the operator reads as loss.
    for stage in (0, 1, 2, 3):
        numbers = [int(m.group(2)) for tid in world
                   if (m := settings.ID_PATTERN.match(tid)) and int(m.group(1)) == stage]
        stages[f"T{stage}"] = f"T{stage}-{(max(numbers) + 1 if numbers else 1):03d}"
    return stages
