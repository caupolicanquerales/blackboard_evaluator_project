"""OpenCode backend: runs agents with the ``opencode run`` CLI.

Phase runners render shared prompts, delegate execution to ``agent_runners``,
and apply the DDD gates after a successful agent run.
"""
import json

import agent_runners
import ddd
import prompts
import settings
import task_queue
import tdd_engine
import telemetry
import workspace

RUNNER_SCRIPT = "orchestrators/orchestrator_opencode.py"


def build_command(agent, message, auto_approve):
    # v2 CLI (>=2.x): `opencode run` has no --dir flag - the working directory comes from the
    # subprocess cwd, which run_agent() already sets to settings.ROOT. Passing --dir makes the
    # CLI exit 1 ("Unrecognized flag") BEFORE any agent session starts (observed live 2026-11-18).
    command = ["opencode", "run", "--agent", agent]
    if auto_approve:
        command.append("--auto")
    command.append(message)
    return command


def _run_phase(span_name, agent, message, timeout, auto_approve, post_check=None,
               attributes=None, cmd_note=""):
    span_attributes = dict(attributes or {})
    with telemetry.span(span_name, span_attributes) as current:
        print(f"[cmd ] opencode run --agent {agent} {cmd_note}".rstrip())
        ok, reason = agent_runners.run_agent(build_command(agent, message, auto_approve),
                                             timeout, settings.ROOT)
        if ok and post_check is not None:
            reason = post_check()
            ok = reason is None
        if not ok:
            telemetry.mark_error(current, reason)
            return False, reason
        return True, ""


def invoke_agent_batch(tasks, auto_approve, timeout, feedback=None):
    message = prompts.build_batch_message(tasks, feedback)
    print(f"[cmd ] opencode run --agent {tasks[0]['targetAgent']} (batch x{len(tasks)})")
    return agent_runners.run_agent(
        build_command(tasks[0]["targetAgent"], message, auto_approve), timeout, settings.ROOT)


def invoke_agent(task, auto_approve, timeout, feedback=None):
    message = prompts.build_task_message(task, feedback)
    print(f"[cmd ] opencode run --agent {task['targetAgent']}")
    return agent_runners.run_agent(build_command(task["targetAgent"], message, auto_approve),
                                   timeout, settings.ROOT)


def run_discovery(args, description_path):
    return _run_phase(
        "blackboard.discovery", settings.DISCOVERY_AGENT,
        prompts.build_discovery_prompt(description_path),
        args.timeout, not args.no_auto, ddd.validate_domain_files,
        {"description": str(description_path)},
    )


def run_mapping(args):
    return _run_phase(
        "blackboard.mapping", settings.MAPPING_AGENT,
        prompts.build_mapping_prompt(),
        args.timeout, not args.no_auto, ddd.validate_context_maps,
        {"domain_dir": str(settings.DOMAIN_DIR)},
    )


def run_strategy(args):
    """Phase 1 of the split architect: execution strategies + the scaffold task.
    The tasks phase moved to `run_planner` (one session per bounded context)."""

    def post_check():
        if not ddd.database_slugs():
            return "no execution strategy was written"
        coverage = ddd.validate_strategy_coverage()
        if coverage:
            return coverage
        for slug in ddd.database_slugs():
            # The strategy is the security step's only input: existence was never
            # enough, an underspecified plan silently costs the domain its permissions.
            reason = ddd.validate_strategy(slug)
            if reason:
                return reason
        return None

    return _run_phase(
        "blackboard.strategy", settings.ARCHITECT_STRATEGY_AGENT,
        prompts.build_architect_prompt(workspace.get_project_root(), RUNNER_SCRIPT,
                                       phase="strategy"),
        args.timeout, not args.no_auto, post_check,
        {"context_maps": str(settings.CONTEXT_MAP_DIR)},
        cmd_note="(strategy)",
    )


def _draft_reason(slug, context):
    """Post-check for one planning session: the draft file is its whole deliverable."""
    draft = task_queue.draft_path(slug, context)
    if not draft.is_file():
        return f"the planning session wrote no draft file at {draft}"
    try:
        loaded = json.loads(draft.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return f"draft {draft.name} is not readable JSON: {exc}"
    if not isinstance(loaded, list) or not loaded \
            or not all(isinstance(task, dict) for task in loaded):
        return f"draft {draft.name} is not a JSON array of task objects"
    return None


def run_planner(args, slug, context, message):
    """Phase 2 of the split architect: ONE bounded context per session. The message is
    built by the pipeline (it owns the drafting state); this backend only runs the
    session and holds it to its one-file deliverable."""
    return _run_phase(
        "blackboard.planner", settings.ARCHITECT_PLANNER_AGENT, message,
        args.timeout, not args.no_auto,
        lambda: _draft_reason(slug, context),
        {"slug": slug, "context": str(context)},
        cmd_note=f"(planner {slug}/{context})",
    )


def run_planner_repair(args, slug, message):
    """The bounded remedy after an engine-side refusal (claim or batch emit). The file
    law is the claim step's post-check, so no session post_check here - the engine
    re-validates after the session by itself."""
    return _run_phase(
        "blackboard.planner_repair", settings.ARCHITECT_PLANNER_AGENT, message,
        args.timeout, not args.no_auto, None,
        {"slug": slug},
        cmd_note=f"(planner-repair {slug})",
    )


def run_database(args, slug):
    """Run the database architect for one context. Returns (ok, reason).

    A stop reported by the agent (for example, application tasks already queued)
    exits cleanly and is reported to the caller as a normal result.
    """
    return _run_phase(
        "blackboard.database", settings.DATABASE_AGENT,
        prompts.build_database_prompt(slug, RUNNER_SCRIPT),
        args.timeout, not args.no_auto, None, {"slug": slug},
    )


def run_security(args, slug):
    """Run the security architect for one context. Returns (ok, reason).

    No runner is passed: this phase authors one artifact and queues nothing. The
    post-check is the spec gate itself - an agent that stopped mid-write, named the file
    differently, leaked a framework name, or left a matrix row discharging no duty has
    produced an artifact the decomposition cannot consume, and the board must not advance
    on that.
    """
    return _run_phase(
        "blackboard.security", settings.SECURITY_AGENT,
        prompts.build_security_prompt(slug),
        args.timeout, not args.no_auto,
        lambda: ddd.validate_security_spec(slug), {"slug": slug},
    )


def run_performance(args, slug):
    """Performance architect, one context: same one-artifact contract as `run_security`,
    post-checked by `ddd.validate_performance_spec`."""
    return _run_phase(
        "blackboard.performance", settings.PERFORMANCE_AGENT,
        prompts.build_performance_prompt(slug),
        args.timeout, not args.no_auto,
        lambda: ddd.validate_performance_spec(slug), {"slug": slug},
    )


def run_ai(args, slug):
    """AI architect, one context (only when the description directed it): post-checked by
    `ddd.validate_ai_spec`."""
    return _run_phase(
        "blackboard.ai", settings.AI_AGENT,
        prompts.build_ai_prompt(slug),
        args.timeout, not args.no_auto,
        lambda: ddd.validate_ai_spec(slug), {"slug": slug},
    )


def run_pass(args):
    def invoke_for_task(task, feedback):
        return invoke_agent(task, not args.no_auto, args.timeout, feedback)

    def invoke_batch(tasks):
        return invoke_agent_batch(tasks, not args.no_auto,
                                  settings.batch_timeout(args.timeout, len(tasks)))

    invoke_for_task.batch = invoke_batch
    return tdd_engine.drain_queue(args, invoke_for_task)
