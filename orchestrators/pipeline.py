"""Backend-agnostic pipeline: CLI shape and the full phase order.

The same flow runs over any backend module that exposes ``run_discovery``,
``run_mapping``, ``run_architect``, ``run_database`` and ``run_pass``.
"""
import argparse
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


def _closure_blockers():
    """Summary of test imports without producer tasks, per domain (empty string when closed)."""
    root = workspace.get_project_root()
    index = task_queue.load_index()
    offenders = []
    services = sorted((root / settings.PROJECTS_SUBDIR).glob("*")) if (root / settings.PROJECTS_SUBDIR).is_dir() else []
    for service in services:
        found = closure.gaps(service, service.name, index)
        if found:
            names = ", ".join(g["class"] for g in found[:3])
            offenders.append(f"{service.name}: {len(found)} unclosed import(s) [{names}...]")
    return "; ".join(offenders)


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

    if ddd.database_slugs():
        print(f"[skip] execution strategies already written: {len(ddd.database_slugs())} domain(s)")
    else:
        print("[plan] architect writing execution strategies")
        ok, reason = backend.run_architect(args, "strategy")
        if not ok:
            print(f"[fatal] architect strategy: {reason}")
            return 1
    for slug in ddd.database_slugs():
        if task_queue.scaffold_task_id(slug) == "T0-000":
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
        return 2

    # Stage 4: the drain walks stages in ascending order, so a queued assembly task
    # structurally runs after every unit of the domain is implemented and evaluated.
    assembly.ensure_tasks()

    try:
        if args.watch:
            while True:
                backend.run_pass(args)
                time.sleep(args.interval)
        processed, blocked = backend.run_pass(args)
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
