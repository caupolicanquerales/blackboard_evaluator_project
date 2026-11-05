"""OpenCode backend: runs agents with the ``opencode run`` CLI.

Phase runners render shared prompts, delegate execution to ``agent_runners``,
and apply the DDD gates after a successful agent run.
"""
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
    command = ["opencode", "run", "--agent", agent, "--dir", str(settings.ROOT)]
    if auto_approve:
        command.append("--auto")
    command.append(message)
    return command


def _run_phase(span_name, agent, message, timeout, auto_approve, post_check=None,
               attributes=None, cmd_note=""):
    span_attributes = dict(attributes or {})
    with telemetry.span(span_name, span_attributes) as current:
        print(f"[cmd ] opencode run --agent {agent} --dir {settings.ROOT} {cmd_note}".rstrip())
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
    print(f"[cmd ] opencode run --agent {tasks[0]['targetAgent']} --dir {settings.ROOT} (batch x{len(tasks)})")
    return agent_runners.run_agent(
        build_command(tasks[0]["targetAgent"], message, auto_approve), timeout, settings.ROOT)


def invoke_agent(task, auto_approve, timeout, feedback=None):
    message = prompts.build_task_message(task, feedback)
    print(f"[cmd ] opencode run --agent {task['targetAgent']} --dir {settings.ROOT}")
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


def run_architect(args, phase="tasks"):
    """Run the architect in phase 'strategy' (writes execution strategies) or 'tasks' (queues tasks)."""

    def post_check():
        if phase == "strategy" and not ddd.database_slugs():
            return "no execution strategy was written"
        if phase == "tasks" and not any(
            (match := settings.ID_PATTERN.match(task_id)) and int(match.group(1)) >= 1
            for task_id in task_queue.load_index()
        ):
            return "architect queued no application tasks"
        return None

    return _run_phase(
        "blackboard.architect", settings.ARCHITECT_AGENT,
        prompts.build_architect_prompt(workspace.get_project_root(), RUNNER_SCRIPT, phase=phase),
        args.timeout, not args.no_auto, post_check,
        {"context_maps": str(settings.CONTEXT_MAP_DIR), "phase": phase},
        cmd_note=f"({phase})",
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


def run_pass(args):
    def invoke_for_task(task, feedback):
        return invoke_agent(task, not args.no_auto, args.timeout, feedback)

    def invoke_batch(tasks):
        return invoke_agent_batch(tasks, not args.no_auto,
                                  settings.batch_timeout(args.timeout, len(tasks)))

    invoke_for_task.batch = invoke_batch
    return tdd_engine.drain_queue(args, invoke_for_task)
