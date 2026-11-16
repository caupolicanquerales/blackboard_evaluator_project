"""Backend-agnostic pipeline: CLI shape and the full phase order.

The same flow runs over any backend module that exposes ``run_discovery``,
``run_mapping``, ``run_architect``, ``run_database`` and ``run_pass``.
"""
import argparse
import builtins
import json
import sys
import time

import assembly
import closure
import ddd
import settings
import task_queue
import tdd_engine
import telemetry
import verification
import workspace

_REAL_PRINT = builtins.print


def _stamp_print(*args, **kwargs):
    """Tagged `[phase ] ...` lines get a wall clock so a resume's replay flood and
    live progress are distinguishable in the log; passthrough output untouched."""
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
    parser.add_argument("--retry", nargs="*", metavar="ID", default=None,
                        help="move quarantined tasks back to the queue (all, or only ids matching these patterns), then continue")
    parser.add_argument("--skip-docker-check", action="store_true",
                        help="do not gate the queue drain on a reachable Docker daemon")
    return parser


def _migration_files(slug):
    """True when the database architect left real migration scripts on disk."""
    migrations = workspace.project_root_for(slug) / "db" / "migrations"
    return migrations.is_dir() and any(f.is_file() for f in migrations.rglob("*"))


def _database_reason(slug):
    """None when the database phase produced both of its artifacts."""
    if not task_queue.database_task_ids(slug):
        return "database architect queued no stage 0 database tasks"
    if not _migration_files(slug):
        return "database architect wrote no migration scripts"
    return None


def _application_tasks_queued():
    """True when any stage 1..3 task is already in queue or complete (restart guard)."""
    return any((match := settings.ID_PATTERN.match(task_id)) and int(match.group(1)) >= 1
               for task_id in task_queue.load_index())


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
        ok, reason = backend.run_architect(args, "strategy")
        if not ok:
            print(f"[fatal] architect strategy: {reason}")
            return 1
        slugs = ddd.database_slugs()
        missing_scaffold = _strategy_phase_gaps(slugs)
    for slug in missing_scaffold:
        print(f"[fatal] architect strategy: no scaffold task for domain {slug}")
        return 1
    for slug in ddd.database_slugs():
        migrations = workspace.project_root_for(slug) / "db" / "migrations"
        if task_queue.database_task_ids(slug) and _migration_files(slug):
            print(f"[skip] database {slug}: tasks queued and migrations written in {migrations}")
            continue
        # The scaffold (stage 0) is generated AFTER this phase, and Copilot's create tool refuses
        # to write under a missing parent: without this directory the database agent loses ~10
        # tool calls to failed writes and duplicates, every extra turn re-sending the transcript.
        migrations.mkdir(parents=True, exist_ok=True)
        ok, reason = backend.run_database(args, slug)
        if ok:
            reason = _database_reason(slug)
            ok = reason is None
        print(f"[db  ] {slug}: {'done' if ok else 'failed: ' + reason}")
        if not ok:
            print(f"[fatal] database {slug}: {reason}")
            return 1
    if _application_tasks_queued():
        print("[skip] application tasks already queued")
    else:
        print("[plan] architect writing application tasks")
        ok, reason = backend.run_architect(args, "tasks")
        if not ok:
            print(f"[fatal] architect tasks: {reason}")
            return 1
    print("[plan] strategy, database, and task phases finished; processing queue")

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
