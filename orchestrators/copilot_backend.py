"""GitHub Copilot backend: runs agents headlessly through the Copilot CLI.

Custom agent profiles in ``.github/agents`` are resolved by name, the CLI is
launched with JSON event output, and only a ``result`` event with exit code 0
counts as a successful run.
"""
import json
import subprocess
import threading

import contextlib
import os
import shutil

import ddd
import prompts
import settings
import task_queue
import tdd_engine
import telemetry
import workspace

RUNNER_SCRIPT = "orchestrators/orchestrator_github.py"
GITHUB_AGENTS_DIR = settings.ROOT / ".github" / "agents"
DEFAULT_COPILOT_BIN = os.environ.get("COPILOT_BIN", "copilot")
DEFAULT_ALLOW_TOOL = os.environ.get("COPILOT_ALLOW_TOOL", "read,write,shell")


def preflight(args):
    """Copilot needs its CLI on PATH; OpenCode does not preflight-check anything."""
    if shutil.which(args.copilot_bin) is None:
        print(f"[fatal] {args.copilot_bin!r} not found on PATH (install GitHub Copilot CLI or set COPILOT_BIN)")
        return 2
    return 0


def read_profile_name(file):
    try:
        text = file.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    for line in text[3:end].splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            name = value.strip().strip('"').strip("'")
            return name or None
    return None


def list_profiles():
    profiles = []
    if not GITHUB_AGENTS_DIR.is_dir():
        return profiles
    files = sorted(set(GITHUB_AGENTS_DIR.rglob("*.agent.md")) | set(GITHUB_AGENTS_DIR.rglob("*.md")))
    for file in files:
        relative = file.relative_to(GITHUB_AGENTS_DIR)
        stem = file.name.removesuffix(".agent.md").removesuffix(".md")
        parent = relative.parts[0] if len(relative.parts) > 1 else ""
        agent_id = stem if not parent else f"{parent}--{stem}"
        profiles.append(
            {
                "file": file,
                "stem": stem,
                "parent": parent,
                "id": agent_id,
                "name": read_profile_name(file),
            }
        )
    return profiles


def resolve_profile(target_agent, profiles):
    for rule in ("parent", "stem", "id"):
        matches = [profile for profile in profiles if profile[rule] == target_agent]
        if len(matches) == 1:
            profile = matches[0]
            if not profile["name"]:
                return None, (
                    f"profile {profile['file'].relative_to(settings.ROOT)} is empty or missing "
                    "a frontmatter 'name'"
                )
            return profile, None
        if len(matches) > 1:
            return None, f"ambiguous .github/agents profiles for {target_agent!r} (matched by {rule})"
    return None, f"no profile in .github/agents matches {target_agent!r}"


def build_copilot_command(args, profile, message, add_project_root=True):
    command = [
        args.copilot_bin,
        "-p", message,
        "-s",
        "--agent", profile["name"],
        "--no-ask-user",
        "--add-dir", str(settings.ROOT),
    ]
    # The project folder is created by agent-container (stage 0), never here.
    # copilot rejects --add-dir for a missing path, so pass it only once it exists.
    if add_project_root and workspace.get_project_root().is_dir():
        command += ["--add-dir", str(workspace.get_project_root())]
    command += [
        "--allow-all-tools",
        "--allow-tool", args.allow_tool,
        "--allow-all-paths",
        "--output-format", "json",
    ]
    return command


def run_agent(command, timeout, cwd):
    with telemetry.span("blackboard.agent", {"agent": _agent_name(command), "timeout": timeout}) as current:
        ok, reason = _run_agent(command, timeout, cwd)
        if not ok:
            telemetry.mark_error(current, reason)
        return ok, reason


def _agent_name(command):
    try:
        index = command.index("--agent")
    except ValueError:
        return "copilot"
    try:
        return command[index + 1]
    except IndexError:
        return "copilot"


def _handle_copilot_event(line, result):
    stripped = line.strip()
    if not stripped:
        return
    try:
        event = json.loads(stripped)
    except json.JSONDecodeError:
        print(f"    | {stripped}")
        return
    if not isinstance(event, dict):
        return
    event_type = event.get("type")
    data = event.get("data")
    if event_type == "assistant.message" and isinstance(data, dict):
        content = data.get("content")
        if content:
            print(f"    | {content}")
    elif event_type == "result":
        result["seen"] = True
        try:
            result["exitCode"] = int(event.get("exitCode", 0))
        except (TypeError, ValueError):
            result["exitCode"] = event.get("exitCode")
        usage = {}
        for source in (data if isinstance(data, dict) else {}, event):
            for key in ("usage", "tokens", "inputTokens", "outputTokens", "costUsds"):
                if key in source:
                    usage[key] = source[key]
        if usage:
            print(f"    [tokens] {usage}")


def _run_agent(command, timeout, cwd):
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(cwd),
        )
    except OSError as exc:
        return False, f"cannot launch {command[0]}: {exc}"
    timed_out = {"flag": False}

    def kill_on_timeout():
        timed_out["flag"] = True
        process.kill()

    watchdog = threading.Timer(timeout, kill_on_timeout)
    watchdog.start()
    stderr_lines = []
    result = {"seen": False, "exitCode": None}

    def read_stderr():
        for line in process.stderr:
            stderr_lines.append(line)
            print(f"    ! {line.rstrip()}")

    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()
    try:
        for line in process.stdout:
            _handle_copilot_event(line, result)
        process.wait()
    finally:
        watchdog.cancel()
        stderr_thread.join(timeout=5)
    if timed_out["flag"]:
        return False, f"agent timed out after {timeout}s"
    stderr_tail = "".join(stderr_lines).strip()[-1000:]
    if process.returncode != 0:
        return False, f"agent exited {process.returncode}: {stderr_tail}"
    if not result["seen"]:
        return False, f"copilot produced no result event: {stderr_tail or 'no output'}"
    if result["exitCode"] != 0:
        return False, f"copilot result exitCode={result['exitCode']}: {stderr_tail}"
    return True, ""


def _run_phase(agent, message, args, post_check=None, span_name=None,
               span_attributes=None, cmd_note=""):
    profile, reason = resolve_profile(agent, list_profiles())
    if profile is None:
        return False, reason
    print(f"[    ] profile {profile['file'].relative_to(settings.ROOT)} -> --agent {profile['name']}")
    span = telemetry.span(span_name, dict(span_attributes or {})) if span_name else contextlib.nullcontext()
    with span as current:
        command = build_copilot_command(args, profile, message)
        print(f"[cmd ] {args.copilot_bin} -p <{cmd_note or 'task'}> -s --agent {profile['name']} "
              f"--no-ask-user --add-dir {settings.ROOT} --allow-all-tools "
              f"--allow-tool {args.allow_tool} --allow-all-paths")
        ok, reason = run_agent(command, args.timeout, settings.ROOT)
        if ok and post_check is not None:
            reason = post_check()
            ok = reason is None
        if not ok and span_name:
            telemetry.mark_error(current, reason)
            return False, reason
        return ok, reason


def invoke_agent(task, args, feedback=None):
    message = prompts.build_task_message(task, feedback)
    return _run_phase(task["targetAgent"], message, args)


def run_discovery(args, description_path):
    return _run_phase(
        settings.DISCOVERY_AGENT, prompts.build_discovery_prompt(description_path), args,
        post_check=ddd.validate_domain_files, span_name="blackboard.discovery",
        span_attributes={"description": str(description_path)}, cmd_note="description",
    )


def run_mapping(args):
    return _run_phase(
        settings.MAPPING_AGENT, prompts.build_mapping_prompt(), args,
        post_check=ddd.validate_context_maps, span_name="blackboard.mapping",
        span_attributes={"domain_dir": str(settings.DOMAIN_DIR)}, cmd_note="draft",
    )


def run_architect(args, phase="tasks"):
    """Run the architect in phase 'strategy' (writes execution strategies) or 'tasks' (queues tasks)."""

    def post_check():
        if phase == "strategy" and not any(settings.COMPLETE_DIR.glob("execution-strategy-*.json")):
            return "architect finished but no execution-strategy-<slug>.json was created"
        if phase == "tasks" and not any(
            (match := settings.ID_PATTERN.match(task_id)) and int(match.group(1)) >= 1
            for task_id in task_queue.load_index()
        ):
            return "architect finished but queued no application tasks"
        return None

    return _run_phase(
        settings.ARCHITECT_AGENT,
        prompts.build_architect_prompt(workspace.get_project_root(), RUNNER_SCRIPT, phase=phase),
        args, post_check=post_check, span_name="blackboard.architect",
        span_attributes={"context_maps": str(settings.CONTEXT_MAP_DIR), "phase": phase},
        cmd_note=phase,
    )


def run_database(args, slug):
    """Run the database architect for one context. Returns (ok, reason)."""
    return _run_phase(
        settings.DATABASE_AGENT, prompts.build_database_prompt(slug, RUNNER_SCRIPT), args,
        span_name="blackboard.database", span_attributes={"slug": slug}, cmd_note="database",
    )


def invoke_agent_batch(tasks, args, feedback=None):
    message = prompts.build_batch_message(tasks, feedback)
    return _run_phase(tasks[0]["targetAgent"], message, args, cmd_note=f"batch x{len(tasks)}")


def run_pass(args):
    def invoke_for_task(task, feedback):
        return invoke_agent(task, args, feedback)

    def invoke_batch(tasks):
        return invoke_agent_batch(tasks, args)

    invoke_for_task.batch = invoke_batch
    return tdd_engine.drain_queue(args, invoke_for_task)
