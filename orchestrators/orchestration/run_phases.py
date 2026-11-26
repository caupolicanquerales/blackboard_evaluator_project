"""run_phases - the ORDER of phases: entry (CLI subcommands, preflights, seed,
docker, retry), the DDD discovery/mapping + replan, strategy with its gate
ladder, then the spec phases (database, security, performance, AI) and the
planner pass. Each function returns an exit code, or None to continue; the
sequence itself is the module - incidents in ordering land here.

(Extracted from pipeline.py's run() in 2026-11-26; prints and returns are the
same statements the monolith executed, per phase.)"""
import settings
import ddd
import telemetry
import verification
import workspace

import task_queue
from plan_flow import PLANNER_REPAIR_ROUNDS, _next_free_for, _plan_domain_tasks, _repair_fingerprint
from plan_gates import (_application_tasks_queued, _database_reason, _migration_files,
                        _security_reason, _surface_security_risks, _surface_spec_risks,
                        _strategy_phase_gaps)


def docker_gate(args):
    """Stop before spending agent runs when a scaffold cannot reach Docker.

    (Was a closure inside run(); the second call site lives in drain_flow.)"""
    if args.skip_docker_check or not verification.stage_zero_queued():
        return 0
    ok, reason = verification.docker_access()
    if ok:
        return 0
    print(f"[fatal] docker gate: {reason}")
    return 2


def entry(args, backend):
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
        for map_file in settings.CONTEXT_MAP_DIR.glob(ddd.CONTEXT_MAP_GLOB):
            map_file.unlink(missing_ok=True)
        for domain_file in settings.DOMAIN_DIR.glob(ddd.DOMAIN_GLOB):
            domain_file.unlink(missing_ok=True)

    preflight = getattr(backend, "preflight", None)
    if preflight is not None:
        code = preflight(args)
        if code:
            return code


    blocked_by_docker = docker_gate(args)
    if blocked_by_docker:
        return blocked_by_docker
    return None


def ddd_and_strategy(args, backend, description):
    if ddd.validate_domain_files() is None and not args.force:
        print(f"[skip] discovery files already valid: {settings.DOMAIN_DIR.relative_to(settings.ROOT)}/")
    else:
        for domain_file in settings.DOMAIN_DIR.glob(ddd.DOMAIN_GLOB):
            domain_file.unlink(missing_ok=True)
        ok, reason = backend.run_discovery(args, description)
        if not ok:
            print(f"[fatal] discovery: {reason}")
            return 1
        print("[ddd ] discovery files ready")

    if ddd.validate_context_maps() is None and not args.force:
        print(f"[skip] context maps already valid: {settings.CONTEXT_MAP_DIR.relative_to(settings.ROOT)}/")
    else:
        for map_file in settings.CONTEXT_MAP_DIR.glob(ddd.CONTEXT_MAP_GLOB):
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
    for slug in slugs:
        # (2026-11-26) before declaring the domain un-planned, heal a damaged stage-0
        # board: a manifest with no scaffold task and the phase-1 draft still on disk is
        # re-queued from the agent's own artifact and the manifest re-pointed behind it -
        # zero sessions. Anything unrecoverable leaves the gap gate's verdict intact.
        healed = task_queue.recover_lost_scaffold(slug)
        if healed:
            print(f"[heal  ] {slug}: scaffold task {healed} re-queued from the phase-1 "
                  "draft - the stage-0 manifest sits behind it again (zero sessions)")
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
    return None


def specs_and_tasks(args, backend):
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
    return None
