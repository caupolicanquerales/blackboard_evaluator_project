"""Backend-agnostic pipeline: CLI shape and the full phase order.

The same flow runs over any backend module that exposes ``run_discovery``,
``run_mapping``, ``run_strategy``, ``run_planner``, ``run_planner_repair``,
``run_database``, ``run_security`` and ``run_pass``. The 2026-11-20 architect split made
phase 2 a PIPELINE loop, not one agent call: one short planner session per bounded
context (digest slice + symbol table), then the engine itself runs the single batch
`--emit` and, on refusal, bounded repair sessions carrying only the error text.
"""
import argparse
from pathlib import Path
import builtins
import json
import sys
import time

import assembly
import closure
import ddd
import prompts
import settings
import task_queue
import tdd_engine
import telemetry
import verification
import workspace

_REAL_PRINT = builtins.print


def _stamp_print(*args, **kwargs):
    """Tagged `[phase ] ...` lines get a wall clock so a resume's replay flood and
    live progress are distinguishable in the log; passthrough output untouched.
    ALWAYS flush (2026-11-20): a block-buffered log loses every line when a run is
    stopped - and a supervisor that cannot see the last line cannot diagnose a stop."""
    kwargs.setdefault("flush", True)
    first = args[0] if args else ""
    if isinstance(first, str) and first.lstrip().startswith("["):
        _REAL_PRINT(time.strftime("%H:%M:%S") + " " + first, *args[1:], **kwargs)
        return
    _REAL_PRINT(*args, **kwargs)


builtins.print = _stamp_print


def _pass_summary(pass_started, processed, blocked):
    """One heartbeat line per drain pass: wall cost plus the cumulative board
    counters, so progress is readable across restarts without parsing the log."""
    def count(folder):
        try:
            # task records only: the architect's strategy files also live under the board
            return sum(1 for f in folder.glob("*.json")
                       if '"id"' in f.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            return 0
    print("[pass  ] wall {:.1f}s | queue {} complete {} quarantined {} | processed {} blocked {}"
          .format(time.monotonic() - pass_started, count(settings.QUEUE_DIR),
                  count(settings.COMPLETE_DIR), count(settings.ERROR_DIR),
                  processed, len(blocked or [])))


def build_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--seed", metavar="FILE", help="business description to analyze (default: first seed/*_description.md)")
    parser.add_argument("--output", metavar="DIR", help="directory where the project is generated (default: projects/<seed title>)")
    parser.add_argument("--force", action="store_true", help="regenerate existing DDD reports")
    parser.add_argument("--watch", action="store_true", help="poll the queue continuously")
    parser.add_argument("--interval", type=int, default=5, help="seconds between polls in watch mode")
    parser.add_argument("--timeout", type=int, default=900, help="seconds before an agent run is aborted")
    parser.add_argument("--verify", choices=settings.VERIFY_MODES, default="typecheck", help="post-task compile/check gate run in the project root")
    parser.add_argument("--verify-scope", choices=("task", "global"), default="task", help="verification scope")
    parser.add_argument("--verify-timeout", type=int, default=300, help="seconds before verification times out")
    parser.add_argument("--limit", type=int, default=0, help="stop after N tasks (0 = no limit)")
    parser.add_argument("--parallel", type=int, default=1,
                        help="concurrent domains during drain (one task per project in flight)")
    parser.add_argument("--emit", nargs="+", metavar="FILE", help="validate and emit task JSON files to queue, then exit")
    parser.add_argument("--lint", metavar="FILE",
                        help="validate ONE planning draft file against the single-file law "
                             "(schema, dangling pins, writable channel); batch laws - duty "
                             "claims, step-log ownership, the shared-literal join, provider "
                             "closure - are DEFERRED to the engine's batch --emit, then exit")
    parser.add_argument("--retry", nargs="*", metavar="ID", default=None,
                        help="move quarantined tasks back to the queue (all, or only ids matching these patterns), then continue")
    parser.add_argument("--replan", nargs="+", metavar="SLUG",
                        help="archive one or more domains' plan (execution strategy, security, "
                             "performance and AI specs, and stage 1-3 records, all to "
                             "blackboard/archive/) so the phases re-run for them on this "
                             "launch: the fix when a strategy names no inbound surface or a "
                             "spec arrived after its decomposition")
    parser.add_argument("--plan-only", action="store_true",
                        help="run every PLAN phase (discovery, mapping, strategy, database, "
                             "security, performance, AI, planner sessions, gaps, batch "
                             "emit) and STOP before the docker gate and the drain - the "
                             "supervised way to measure plan cost: zero execution sessions "
                             "are billed, the queue holds the finished plan")
    parser.add_argument("--skip-docker-check", action="store_true",
                        help="do not gate the queue drain on a reachable Docker daemon")
    return parser


def _migration_files(slug):
    """True when the database architect left real migration scripts on disk.

    The location is the one the ACTIVE STACK SKILL names as runtime-loaded (Spring:
    src/main/resources/db/migration; generic: db/migrations at the module root) -
    keyed by the migration filename, not one hardcoded folder: a check that only
    accepts the module root would fatal a plan that correctly packaged its schema,
    the same gate-vs-skill collision as the 2026-11-16 N8 pair (2026-11-17: the
    literal folder check quietly endorsed scripts the runtime never loads).
    """
    root = workspace.project_root_for(slug)
    if not root.is_dir():
        return False
    return any(root.rglob("V*__*.sql"))


def _database_reason(slug):
    """None when the database phase produced both of its artifacts."""
    if not task_queue.database_task_ids(slug):
        return "database architect queued no stage 0 database tasks"
    if not _migration_files(slug):
        return "database architect wrote no migration scripts"
    return None


def _security_reason(slug):
    """None when the security phase produced a lawful spec.

    The spec is mandatory for every domain: the strategy already carries the persistence
    and observability floors, and a plan with no permission table leaves every later unit
    to guess who may call what. Nothing is queued here on purpose - the security step
    decides WHAT must hold, the architect decides HOW and schedules it (rule (y)), so this
    phase has no task-shaped success criterion to be graded against.
    """
    return ddd.validate_security_spec(slug)


def _surface_security_risks(slug):
    """Print the domain's risk register - every entry, every launch, including the resume path    where the spec was already valid and the phase printed nothing at all.

    A risk is the spec's own record of a conflict it refused to soften (posture rule: never weaken a
    control to fit an implementation, record it). Until now the array was written, machine-checked for
    shape, and then read by nobody: the gate requires a control's entry id or an accepted posture, and
    this prints which of the two the run is living with, so an accepted exposure is a line an operator
    saw, not a field that aged out of a JSON file."""
    accepted = 0
    for entry in ddd.security_risks(slug):
        rid = str(entry.get("id", "R-??"))
        mitigation = str(entry.get("mitigation", "")).strip()
        is_accepted = ddd._risk_is_accepted(mitigation)
        accepted += 1 if is_accepted else 0
        print(f"[risk  ] {slug} {rid}: {str(entry.get('risk', ''))[:150]} -> "
              f"{'ACCEPTED, not mitigated:' if is_accepted else 'control'} {mitigation[:110]}"
              f" | residual: {str(entry.get('residual', ''))[:110]}")
    if accepted:
        print(f"[risk  ] {slug}: {accepted} of {len(ddd.security_risks(slug))} recorded risks are "
              "accepted postures - the run is defended against the rest by choice, not by accident")


def _surface_spec_risks(slug, label, risks):
    """The same disclosure channel the security register has (A2/SA6): a risk that is only
    WRITTEN is a risk nobody read. Performance and AI specs carry the register law, so the
    pipeline prints their entries on every launch too - fresh phase, skipped phase, resume."""
    accepted = 0
    for entry in risks:
        rid = str(entry.get("id", "R-??"))
        mitigation = str(entry.get("mitigation", "")).strip()
        is_accepted = ddd._risk_is_accepted(mitigation)
        accepted += 1 if is_accepted else 0
        print(f"[risk  ] {slug}/{label} {rid}: {str(entry.get('risk', ''))[:150]} -> "
              f"{'ACCEPTED, not mitigated:' if is_accepted else 'control'} {mitigation[:110]}"
              f" | residual: {str(entry.get('residual', ''))[:110]}")
    if accepted:
        print(f"[risk  ] {slug}/{label}: {accepted} of {len(risks)} recorded risks are accepted "
              "postures - sized/planned against the rest by choice, not by accident")


def _application_tasks_queued():
    """True when any stage 1..3 task is already in queue or complete (restart guard)."""
    return any((match := settings.ID_PATTERN.match(task_id)) and int(match.group(1)) >= 1
               for task_id in task_queue.load_index())


PLANNER_REPAIR_ROUNDS = 2  # engine-side refusals get TWO bounded repair passes, then the
# run stops: a third pass over the same ERR text is the retry-storm shape the drain pays
# for in sessions; the operator's --replan is the lawful third try.


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
        if path.is_file() and not task_queue.draft_is_fresh(slug, context):
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
    for context in contexts:
        slice_path, slice_problems = ddd.write_phase2_digest_slice(slug, context)
        if slice_problems:
            return False, f"{slug}/{context}: " + "; ".join(slice_problems[:3])
        if task_queue.draft_is_fresh(slug, context):
            print(f"[resume] {slug}/{ddd.context_stem(context)}: draft kept - newer than "
                  "every plan input; claimed without a session")
        else:
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
                slug, context, task_queue.draft_path(slug, context), slice_path,
                symbols_path, _next_free_for(slug),
                [c for c in contexts if c not in drafted and c != context])
            ok, reason = backend.run_planner(args, slug, context, message)
            if not ok:
                return False, f"{slug}/{context}: {reason}"
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
    # (PHASE 1.5 2026-11-25) the X11 gap consumption lived here; the channels are
    # gone - the manifest is engine-queued and config coverage is wired at the emit.
    # (R3 2026-11-25) refusals are ROUTED: an `ERR [id]` pointer knows its owner, and
    # the owner is exactly one context file. A one-unit defect dragged every draft file
    # and the whole digest into each billed whole-domain repair round - the shape the
    # plan bled on. Each bucket now gets its lines, its files, and its own rounds;
    # genuinely cross-context lines ("domain" bucket) keep the whole-batch treatment.
    reason = task_queue.emit_draft_batch(slug, drafted)
    total_rounds, max_rounds = 0, PLANNER_REPAIR_ROUNDS * 2
    bucket_rounds = {}
    stuck = {}
    while reason and total_rounds < max_rounds:
        buckets = task_queue.route_refusals(reason, slug, drafted)
        errors = len([line for line in reason.splitlines() if line.startswith("ERR")])
        blame = ", ".join(f"{k} [{len(v)} line(s)]" for k, v in sorted(buckets.items()))
        print(f"[emit  ] {slug}: the batch refused ({errors} error line(s)); blame: "
              f"{blame or 'no routed lines'}")
        for line in [l for l in reason.splitlines() if l.startswith("ERR")][:8]:
            print(f"[emit  ]   {line[:240]}")
        progress = False
        for bucket, lines in sorted(buckets.items()):
            files = drafted if bucket == "domain" else [bucket]
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
        reason = task_queue.emit_draft_batch(slug, drafted)
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


def _strategy_phase_gaps(slugs):
    """Domains whose strategy file is on disk but whose stage-0 scaffold task never
    landed - the resumable partial state (2026-11-16 09:50: the claim gate refused
    T0 before decomposition could exist, the strategy file survived; skipping phase
    1 on `database_slugs()` alone made every relaunch die [fatal] again at zero
    sessions, unable to heal the state it was handed)."""
    return [slug for slug in slugs if task_queue.scaffold_task_id(slug) == "T0-000"]


def _closure_blockers():
    """Summary of test imports without producer tasks, per domain (empty string when closed)."""
    root = workspace.get_project_root()
    index = task_queue.load_index(include_error=True)
    offenders = []
    services = sorted((root / settings.PROJECTS_SUBDIR).glob("*")) if (root / settings.PROJECTS_SUBDIR).is_dir() else []
    for service in services:
        found = closure.gaps(service, service.name, index)
        if found:
            names = ", ".join(g["class"] for g in found[:3])
            offenders.append(f"{service.name}: {len(found)} unclosed import(s) [{names}...]")
    return "; ".join(offenders)


def _stuck_report(blocked):
    """The stuck-drain escalation text: who blocks, who owns the blockers, what to run.

    A watch drain whose passes bill nothing and complete nothing while tasks stay
    blocked is provably waiting on events the engine itself cannot create. The report
    names the quarantined owners and the last deferral reasons so the operator lands
    on the remedy (--retry / closure --emit / source fix) instead of reading a spin.
    """
    import re
    waits = tdd_engine.wait_snapshot()
    quarantined = sorted({match.group(1) for f in settings.ERROR_DIR.glob("*.json")
                          if (match := re.match(r"(T[0-4]-\d{3})", f.name))})
    parts = [f"no progress for {settings.STUCK_PASSES_FATAL} consecutive passes: "
             f"{len(blocked)} task(s) still blocked"]
    if quarantined:
        head = ", ".join(quarantined[:12]) + (", ..." if len(quarantined) > 12 else "")
        parts.append(f"quarantined in blackboard/error/: {head}")
    for task_id in list(blocked)[:3]:
        if task_id in waits:
            parts.append(f"e.g. {task_id} waits on: {waits[task_id][:150]}")
    parts.append("nothing the engine can do changes this: restore quarantined units with "
                 "--retry [ids], queue missing producers with python3 orchestrators/closure.py --emit, "
                 "or fix the blamed source; then relaunch to continue")
    return " | ".join(parts)


def _terminal_tree_report(gate=None):
    """A DETERMINISTIC verdict on the delivered bytes at every terminal exit (seed-002
    supervision gap: the run exited reporting board counts plus a CACHED 16:17 boot
    verdict while the final quarantine rollback had left dangling imports in production
    code). Board-driven by design (2026-11-13 rerun finding): a domain whose stage-4
    assembly NEVER ran is reported as `NEVER BOOTED`, not silently skipped - the old
    report scanned completed T4 records only and inherited the scheduling hole it was
    meant to expose. Zero agent sessions: the gate command is the deterministic boot;
    no stale build output can mask it because the command recompiles. Reporting only -
    this never raises and never requeues."""
    gate = gate or assembly.gate
    index = task_queue.load_index(include_error=True)
    slugs = sorted({str(t.get("project", "")) for t in index.values()
                    if isinstance(t, dict) and t.get("stage") == settings.TDD_STAGE
                    and t.get("project")})
    lines = []
    for slug in slugs:
        record = None
        for file in sorted(settings.COMPLETE_DIR.glob("T4-*.json")):
            try:
                rec = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(rec, dict) and rec.get("project") == slug:
                record = rec
                break
        if (ddd.ai_directive(slug) or {}).get("required") is True:
            lines.append(f"[tree   ] {slug}: AI BY DIRECTIVE - {ddd.ai_required(slug)[1]}"
                          + ("" if ddd.ai_spec_path(slug).is_file()
                             else " BUT NO SPEC ON DISK (the phase never landed)"))
        if ddd.security_waived(slug):
            lines.append(f"[tree   ] {slug}: SECURITY WAIVED by directive in the business description "
                         f"- {ddd._waiver_note(slug)[1]}"
                         + (" BUT A SPEC IS ON DISK (stale: it predates the waiver)"
                            if ddd.security_spec_path(slug).is_file() else ""))
        if record is None:
            lines.append(f"[tree   ] {slug}: RED - NEVER BOOTED: no completed stage-4 assembly "
                         "task exists for this domain - the boot gate never ran, so NOTHING "
                         "proves the application starts (relaunch the drain; assembly is "
                         "queued automatically once the scaffold exists)")
            continue
        try:
            ok, reason = gate(record)
        except Exception as exc:                       # reporting must not crash the exit
            ok, reason = False, f"terminal gate could not run: {exc}"
        lines.append(f"[tree   ] {slug}: "
                     + ("GREEN - the delivered tree compiles and boots" if ok
                        else f"RED - the DELIVERED TREE IS BROKEN: {str(reason)[:500]}"))
    return lines


def run(args, backend):
    """Execute the full pipeline for one backend. Returns the process exit code."""
    telemetry.init_telemetry()
    for folder in (settings.QUEUE_DIR, settings.COMPLETE_DIR, settings.ERROR_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    if args.emit:
        reason = task_queue.emit_tasks(args.emit)
        if reason:
            print(f"[emit-error] {reason}")
            return 1
        return 0

    if args.lint:
        reason = task_queue.lint_draft(args.lint)
        print(reason)
        return 1 if reason.startswith("ERR") else 0

    # Carrier preflight (2026-11-20 live-line stop): a profile whose YAML header does not
    # parse is SILENTLY skipped by the Copilot CLI, and the failure then surfaces mid-run
    # as "No such agent" - only when that carrier is first spawned, after every earlier
    # planning session was already billed. Headers must be parseable BEFORE phase 0.
    header_problems = settings.agent_profiles_problems()
    if header_problems:
        for line in header_problems:
            print(f"[fatal] profile header: {line}")
        return 1

    description = workspace.resolve_seed(args.seed)
    if args.retry is not None:
        restored = task_queue.retry_error_tasks(args.retry)
        print(f"[retry] {len(restored)} quarantined task(s) back in the queue")
    if description is None or not description.is_file():
        print(f"[fatal] no seed description found in {settings.SEED_DIR} (use --seed FILE)")
        return 2
    print(f"[seed ] {description}")
    project_root = workspace.set_project_root(workspace.resolve_output_path(args.output, description))
    print(f"[root] generated project: {project_root}")

    if args.force:
        for map_file in settings.CONTEXT_MAP_DIR.glob("context-map-*.json"):
            map_file.unlink(missing_ok=True)
        for domain_file in settings.DOMAIN_DIR.glob("domain-boundary-*.json"):
            domain_file.unlink(missing_ok=True)

    preflight = getattr(backend, "preflight", None)
    if preflight is not None:
        code = preflight(args)
        if code:
            return code

    def docker_gate():
        """Stop before spending agent runs when a scaffold cannot reach Docker."""
        if args.skip_docker_check or not verification.stage_zero_queued():
            return 0
        ok, reason = verification.docker_access()
        if ok:
            return 0
        print(f"[fatal] docker gate: {reason}")
        return 2

    blocked_by_docker = docker_gate()
    if blocked_by_docker:
        return blocked_by_docker

    if ddd.validate_domain_files() is None and not args.force:
        print(f"[skip] discovery files already valid: {settings.DOMAIN_DIR.relative_to(settings.ROOT)}/")
    else:
        for domain_file in settings.DOMAIN_DIR.glob("domain-boundary-*.json"):
            domain_file.unlink(missing_ok=True)
        ok, reason = backend.run_discovery(args, description)
        if not ok:
            print(f"[fatal] discovery: {reason}")
            return 1
        print("[ddd ] discovery files ready")

    if ddd.validate_context_maps() is None and not args.force:
        print(f"[skip] context maps already valid: {settings.CONTEXT_MAP_DIR.relative_to(settings.ROOT)}/")
    else:
        for map_file in settings.CONTEXT_MAP_DIR.glob("context-map-*.json"):
            map_file.unlink(missing_ok=True)
        ok, reason = backend.run_mapping(args)
        if not ok:
            print(f"[fatal] mapping: {reason}")
            return 1
        print("[ddd ] context maps ready")

    for slug in getattr(args, "replan", None) or []:
        # BEFORE the phase-1 skip decision: archiving the strategy is what makes phase 1 see
        # this domain as un-planned and re-run. Stage 0 (scaffold, migrations) and stage 4
        # (assembly) records stay: the plan is re-issued over the same project root.
        moved = task_queue.replan_domain(slug)
        print(f"[replan] {slug}: strategy={moved['strategy']} spec={moved['spec']} "
              f"performance={moved['performance']} ai={moved['ai']} "
              f"tasks={len(moved['tasks'])} archived to blackboard/archive/ - this launch "
              "re-runs the strategy, security, performance, AI and task phases for this domain "
              "(delivered sources are untouched)")

    slugs = ddd.database_slugs()
    missing_scaffold = _strategy_phase_gaps(slugs)
    if slugs and not missing_scaffold:
        print(f"[skip] execution strategies already written: {len(slugs)} domain(s)")
    else:
        if slugs:
            # 2026-11-16 resume hole: the strategy file survived a phase-1 abort whose
            # REAL defect (a claim gate demanding stage-2 claims before decomposition
            # can exist) refused the scaffold task. Skipping phase 1 because a strategy
            # was on disk made every relaunch die [fatal] again without a session.
            print(f"[plan] strategies written but scaffold task missing for "
                  f"{', '.join(missing_scaffold)}: re-running phase 1")
        else:
            print("[plan] architect writing execution strategies")
        ok, reason = backend.run_strategy(args)
        if not ok:
            print(f"[fatal] architect strategy: {reason}")
            return 1
        slugs = ddd.database_slugs()
        missing_scaffold = _strategy_phase_gaps(slugs)
    for slug in missing_scaffold:
        print(f"[fatal] architect strategy: no scaffold task for domain {slug}")
        return 1
    # A board that skipped phase 1 (or an architect that wrote 3 of 4 strategies) must not proceed:
    # every later loop iterates STRATEGY slugs, so an unstrategised domain loses its security spec and
    # its tasks in total silence.
    reason = ddd.validate_strategy_coverage()
    if reason:
        print(f"[fatal] strategy coverage: {reason}")
        return 1
    reason = ddd.validate_security_directives()
    if reason:
        print(f"[fatal] security directive: {reason}")
        return 1
    reason = ddd.validate_ai_directives()
    if reason:
        print(f"[fatal] AI directive: {reason}")
        return 1
    # R1 (2026-11-25 cross-launch damage stop): a previous killed run's session may
    # have mutated the inputs; verify and restore from the snapshot BEFORE any gate
    # reads them, so an unlawful amendment heals this launch instead of killing it
    for slug in ddd.database_slugs():
        restored, amended = task_queue.verify_plan_inputs(slug)
        for name in restored:
            print(f"[heal  ] {slug}: {name} restored to the phase-1 snapshot - "
                  "unlawful session mutation rolled back, the plan continues")
        for name in amended:
            print(f"[warn  ] {slug}: {name} carries a lawful text amendment from a "
                  "previous plan pass")
    for slug in ddd.database_slugs():
        # SHAPE GATE FIRST (2026-11-24 seed-002 v4 live stop): the strategy's own
        # validate_strategy ran only inside the security loop, AFTER the database phase
        # had already billed a session against the invalid plan - a refused floor shape
        # cost the database agent on the way out. Fail fast where nothing is billed yet.
        reason = ddd.validate_strategy(slug)
        if reason:
            print(f"[fatal] strategy {slug}: {reason}")
            print(f"[hint ] relaunch with --replan {slug} to archive this domain's plan and "
                  "re-run the phases that read it")
            return 1
    for slug in ddd.database_slugs():
        # The runtime-loaded migration directory is named by the ACTIVE tech-stack skill
        # (concrete-database-migration: "the script directory comes ONLY from the active
        # tech-stack skill"), so the engine pre-creates NOTHING: a hard-coded path here
        # (2026-11-24 seed-002: it mkdir'd `services/<slug>/db/migrations` and printed that
        # same path in the skip line) advertised a module-root folder nobody loads and
        # contradicted the skill the database agent was told to follow. The gate stays
        # location-agnostic - _migration_files finds the scripts wherever the skill put them.
        if task_queue.database_task_ids(slug) and _migration_files(slug):
            print(f"[skip] database {slug}: tasks queued and migration scripts written under "
                  f"{workspace.project_root_for(slug)}")
            continue
        ok, reason = backend.run_database(args, slug)
        if ok:
            reason = _database_reason(slug)
            ok = reason is None
        print(f"[db  ] {slug}: {'done' if ok else 'failed: ' + reason}")
        if not ok:
            print(f"[fatal] database {slug}: {reason}")
            return 1
    for slug in ddd.database_slugs():
        # database_slugs() is the board's list of PLANNED domains (one per strategy file).
        # The security phase runs over the same set, after the store is chosen (the spec
        # classifies what that store persists) and before decomposition claims its duties.
        reason = ddd.validate_strategy(slug)
        if reason:
            # A FRESH plan is judged by phase 1's own post-check, so arriving here means the
            # strategy predates the surface contract: the security step would table rows for
            # the surfaces it was told about and never see the rest.
            print(f"[fatal] strategy {slug}: {reason}")
            print(f"[hint ] relaunch with --replan {slug} to archive this domain's plan and "
                  "re-run the phases that read it")
            return 1
        waived, note = ddd._waiver_note(slug)
        if waived:
            # The ONE lawful omission, and it is the user's own sentence, engine-verified verbatim
            # against the description file the slice cites - never an agent's inference.
            print(f"[sec   ] {slug}: WAIVED by the business description - {note}")
            print(f"[sec   ] {slug}: no spec, no duties, nothing to claim; the domain's `surfaces` "
                  "table still ships (it is architecture, not a control) and every later gate reports "
                  "this domain as un-defended by directive, not by oversight")
            if ddd.security_spec_path(slug).is_file():
                # A spec written BEFORE the waiver was recorded must not keep enforcing claims in
                # silence: the phase is waived, so the artifact is stale, and staleness is disclosed.
                print(f"[sec   ] {slug}: a spec is on disk from an earlier run - it now contradicts "
                      f"the directive; remove {ddd.security_spec_path(slug).name} or relaunch with "
                      f"--replan {slug} to archive it (until then the emit gate still demands its "
                      "duties be claimed, which is the conservative reading)")
            continue
        spec = ddd.security_spec_path(slug).name
        if ddd.validate_security_spec(slug) is None:
            print(f"[skip] security {slug}: {spec} already valid")
            _surface_security_risks(slug)
            continue
        ok, reason = backend.run_security(args, slug)
        if ok:
            reason = _security_reason(slug)
            ok = reason is None
        print(f"[sec   ] {slug}: {'done' if ok else 'failed: ' + reason}")
        if not ok:
            print(f"[fatal] security {slug}: {reason}")
            return 1
        _surface_security_risks(slug)
        questions = ddd.security_open_questions(slug)
        if questions:
            # The spec author's honest escape hatch: an entrant or surface its inputs never
            # declared. Nothing else in the engine reads that array, so an open question was
            # filed away and the drain continued over an undefended surface.
            print(f"[fatal] security {slug}: the spec leaves {len(questions)} open question(s) - "
                  "an undecided posture is an unprotected surface, and the answer is an input "
                  "phase 1 never wrote")
            for question in questions[:5]:
                print(f"[fatal]   {slug}: {question[:200]}")
            print(f"[hint ] name the missing surface or persisted concept in "
                  f"{ddd.strategy_path(slug).name} (blackboard/complete/), or relaunch with "
                  f"--replan {slug} to re-run the phases that read it")
            return 1
        if _application_tasks_queued():
            gaps = task_queue.security_claim_gaps(slug)
            if gaps:
                print(f"[fatal] security {slug}: {len(gaps)} security claim gap(s) on a board "
                      "whose application tasks predate the spec - the plan cannot claim duties "
                      "it was never shown, so this spec is advisory and a green drain would "
                      "read as defended")
                for line in gaps[:5]:
                    print(f"[fatal]   {line[:300]}")
                print(f"[hint ] relaunch with --replan {slug} to archive this domain's plan and "
                      "re-issue its units against the spec")
                return 1
    for slug in ddd.database_slugs():
        # the performance floor: unconditional, like security - every executable context has
        # a load side, and a domain nobody sized is sized by framework defaults in the dark
        perf = ddd.performance_spec_path(slug).name
        if ddd.validate_performance_spec(slug) is None:
            print(f"[skip] performance {slug}: {perf} already valid")
            _surface_spec_risks(slug, "performance", ddd.performance_risks(slug))
            continue
        ok, reason = backend.run_performance(args, slug)
        if ok:
            reason = ddd.validate_performance_spec(slug)
            ok = reason is None
        print(f"[perf  ] {slug}: {'done' if ok else 'failed: ' + reason}")
        if not ok:
            print(f"[fatal] performance {slug}: {reason}")
            return 1
        _surface_spec_risks(slug, "performance", ddd.performance_risks(slug))
        questions = ddd.performance_open_questions(slug)
        if questions:
            print(f"[fatal] performance {slug}: the spec leaves {len(questions)} open "
                  "question(s) - an undecided load model is a surface the plan sized by "
                  "default, and only phase 1 can answer it")
            for question in questions[:5]:
                print(f"[fatal]   {slug}: {question[:200]}")
            print(f"[hint ] name the missing surface or volume in "
                  f"{ddd.strategy_path(slug).name}, or relaunch with --replan {slug}")
            return 1
    for slug in ddd.database_slugs():
        # the AI phase runs ONLY on the description-verified directive; absent is the
        # default state (no capability was asked for), never a hole to fill
        directive = ddd.ai_directive(slug)
        if not directive or directive.get("required") is not True:
            if directive:
                print(f"[ai    ] {slug}: directive present but not required=true - no AI phase")
            continue
        verified, note = ddd.ai_required(slug)
        if not verified:
            print(f"[fatal] AI {slug}: {note}")
            return 1
        spec = ddd.ai_spec_path(slug).name
        if ddd.validate_ai_spec(slug) is None:
            print(f"[skip] ai {slug}: {spec} already valid - directed by the description")
            _surface_spec_risks(slug, "AI", ddd.ai_risks(slug))
            continue
        print(f"[ai    ] {slug}: RUNNING by directive - {note}")
        ok, reason = backend.run_ai(args, slug)
        if ok:
            reason = ddd.validate_ai_spec(slug)
            ok = reason is None
        print(f"[ai    ] {slug}: {'done' if ok else 'failed: ' + reason}")
        if not ok:
            print(f"[fatal] AI {slug}: {reason}")
            return 1
        _surface_spec_risks(slug, "AI", ddd.ai_risks(slug))
        questions = ddd.ai_open_questions(slug)
        if questions:
            print(f"[fatal] AI {slug}: the spec leaves {len(questions)} open question(s) - "
                  "an AI behavior no input declared, and inventing one is how a directed "
                  "capability becomes an undirected product")
            for question in questions[:5]:
                print(f"[fatal]   {slug}: {question[:200]}")
            print(f"[hint ] name the missing flow in the context map, or relaunch with "
                  f"--replan {slug}")
            return 1
    if _application_tasks_queued():
        for slug in ddd.database_slugs():
            gaps = task_queue.planning_claim_gaps(slug)
            if gaps:
                print(f"[fatal] planning duties {slug}: {len(gaps)} performance/AI claim gap(s) "
                      "on a board whose application tasks predate the specs - a spec no unit "
                      "claims is advisory, and a green drain would read as sized/planned")
                for line in gaps[:5]:
                    print(f"[fatal]   {line[:300]}")
                print(f"[hint ] relaunch with --replan {slug} to archive this domain's plan "
                      "and re-issue its units against the specs")
                return 1
    if _application_tasks_queued():
        print("[skip] application tasks already queued")
    else:
        print("[plan] architect writing application tasks")
        for slug in ddd.database_slugs():
            ok, reason = _plan_domain_tasks(args, backend, slug)
            if not ok:
                print(f"[fatal] architect tasks: {reason}")
                return 1
    print("[plan] strategy, database, security, performance, AI, and task phases finished; "
          "processing queue")

    if args.plan_only:
        # the drain never starts: a supervised plan measurement bills PLAN sessions only
        print("[plan  ] --plan-only: the plan is queued, the drain was NOT started - "
              f"inspect with blackboard/queue, then relaunch without the flag to drain")
        return 0

    blocked_by_docker = docker_gate()
    if blocked_by_docker:
        print(f"[hint ] nothing ran: fix the environment and relaunch with --retry to restore "
              f"{len(list(settings.ERROR_DIR.glob('*.json')))} quarantined task(s)")
        return blocked_by_docker

    blocked = _closure_blockers()
    if blocked:
        print(f"[fatal] task closure: {blocked}")
        print("[hint ] generate the missing producers with: python3 orchestrators/closure.py --emit")
        if any(settings.ERROR_DIR.glob("*.json")):
            print("[hint ] a quarantined task may own the missing product: relaunch with "
                  "--retry [ids] to restore it (its payload often still needs only a gate)")
        return 2

    # Stage 4: the drain walks stages in ascending order, so a queued assembly task
    # structurally runs after every unit of the domain is implemented and evaluated.
    assembly.ensure_tasks()

    try:
        if args.watch:
            idle_passes = 0
            stuck_passes = 0
            exhausted_passes = 0
            while True:
                pass_started = time.monotonic()
                # Re-scheduled EVERY pass, not once at launch: on a fresh run the services/
                # folder does not exist until the stage-0 scaffold completes DURING the drain,
                # and an ensure_tasks() that only sees the pre-drain emptiness never queues
                # the boot gate - the run then drains to "done" having never booted anything
                # (observed live 2026-11-13 13:33: queue 0, 35 complete, zero T4 records).
                # ensure_tasks() is idempotent and reads directories only: zero sessions.
                assembly.ensure_tasks()
                processed, blocked = backend.run_pass(args)
                _pass_summary(pass_started, processed, blocked)
                if processed == 0:
                    idle_passes += 1
                    # Quiet board: the suite gate re-reads the DELIVERED tree, not the
                    # board statistics (2026-11-16: an evaluator and the assembler each
                    # broke a peer's frozen test AFTER the last wave; every later gate
                    # passed and the drain idled on a red tree). Memoized per tree
                    # fingerprint: a converged board costs file hashes, never builds.
                    if not any(settings.QUEUE_DIR.glob("*.json")):
                        if tdd_engine.terminal_suite_gate():
                            idle_passes = 0
                            continue
                    # Nothing was produced this pass: every unit is idle (empty queue)
                    # or deferred on work only the OPERATOR can unlock (--retry restore,
                    # a newly emitted producer, a source fix). A fixed 5s re-poll burns
                    # CPU and log volume (W3) and, with a blocked queue, used to run
                    # forever: measured 2,900+ zero-progress passes after one root
                    # quarantine reverted the domain's classes. Back off geometrically
                    # for BOTH shapes and stop loudly when a blocked drain repeats.
                    time.sleep(min(max(args.interval, 1) * 2 ** min(idle_passes, 4), 60))
                    if blocked:
                        stuck_passes += 1
                    elif (not any(settings.QUEUE_DIR.glob("*.json"))
                            and any(settings.ERROR_DIR.glob("*.json"))):
                        # BOARD EXHAUSTED (seed-002 rerun shape): the queue is empty ONLY
                        # because quarantines drained it - blocked is empty by definition,
                        # so the stuck breaker above could never see this. Silence here cost
                        # an operator afternoon: zero progress, zero bills, zero guidance.
                        exhausted_passes += 1
                        if exhausted_passes >= settings.STUCK_PASSES_FATAL:
                            restored = tdd_engine.autogrant_progressing()
                            if restored:
                                print(f"[grant ] auto-restored {len(restored)} advancing "
                                      f"quarantined unit(s): {', '.join(restored[:8])}")
                                exhausted_passes = 0
                                idle_passes = 0
                                continue
                            n_err = len(list(settings.ERROR_DIR.glob("*.json")))
                            for line in _terminal_tree_report():
                                print(line)
                            print(f"[exhausted] queue empty with {n_err} quarantined task(s): "
                                  "the drain cannot advance without the operator. Inspect with "
                                  "`python3 orchestrators/status.py`, fix the root failure, then "
                                  "relaunch with --retry.")
                            return 1
                    else:
                        stuck_passes = 0
                        exhausted_passes = 0
                    if stuck_passes >= settings.STUCK_PASSES_FATAL:
                        # Before declaring the block operator-only, auto-grant the
                        # quarantined units that are PROVABLY advancing (their last
                        # failure was never shown to a coder): the drain resumes with
                        # its bounded informed attempts instead of idling on launches.
                        restored = tdd_engine.autogrant_progressing()
                        if restored:
                            print(f"[grant ] auto-restored {len(restored)} advancing "
                                  f"quarantined unit(s): {', '.join(restored[:8])}")
                            stuck_passes = 0
                            idle_passes = 0
                            continue
                        raise tdd_engine.FatalPipeline(_stuck_report(blocked))
                else:
                    idle_passes = 0
                    stuck_passes = 0
                    time.sleep(args.interval)
        processed, blocked = backend.run_pass(args)
        # Same root cause as the watch-loop reschedule: on a single-pass run the services/
        # folder appears DURING the pass, so the one pre-drain ensure_tasks() could not have
        # seen it. Schedule now (idempotent, zero sessions) and, if the boot gate is fresh
        # work, drain it - a run that "finished" without ever booting the app is a lie.
        before = set(settings.QUEUE_DIR.glob("T4-*.json"))
        assembly.ensure_tasks()
        if set(settings.QUEUE_DIR.glob("T4-*.json")) - before:
            extra, blocked = backend.run_pass(args)
            processed += extra
    except KeyboardInterrupt:
        return 130
    except tdd_engine.FatalPipeline as fatal:
        print(f"[fatal] {fatal}")
        return 2
    if blocked:
        print(f"[blocked] {', '.join(blocked)}")
        return 1

    if args.verify != "none":
        for slug in ddd.database_slugs():
            ok, reason = verification.verify_project(workspace.project_root_for(slug),
                                                     args.verify, args.verify_timeout)
            if not ok:
                print(f"[fatal] {slug}: {reason}")
                return 1
            print(f"[verify] {slug} passes {args.verify}")
    print(f"[ok] processed {processed} task(s)")
    return 0
