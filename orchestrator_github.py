#!/usr/bin/env python3
"""Blackboard orchestrator (GitHub Copilot backend) for the evaluator pipeline.

Same contract and queue format as ``orchestrator_opencode.py``; the only
difference is that agents are activated headlessly through the Copilot CLI using
the custom agent profiles in ``.github/agents/``.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import telemetry
from orchestrator_opencode import (
    ANALYSIS_REPORT,
    ARCHITECT_AGENT,
    COMPLETE_DIR,
    DISCOVERY_AGENT,
    DRAFT_REPORT,
    ERROR_DIR,
    MAPPING_AGENT,
    PLAN_FILE,
    PROMPT_KEYS,
    QUEUE_DIR,
    ROOT,
    SEED_DIR,
    STAGE_INSTRUCTIONS,
    VERIFY_MODES,
    build_architect_prompt,
    build_discovery_prompt,
    build_mapping_prompt,
    claimable,
    emit_tasks,
    get_project_root,
    load_index,
    read_queue,
    resolve_output_path,
    resolve_seed,
    run_verification,
    send_to_error,
    set_project_root,
    validate,
    validate_report,
    verify_project,
)

RUNNER_SCRIPT = "orchestrator_github.py"
GITHUB_AGENTS_DIR = ROOT / ".github" / "agents"
DEFAULT_COPILOT_BIN = os.environ.get("COPILOT_BIN", "copilot")
DEFAULT_ALLOW_TOOL = os.environ.get("COPILOT_ALLOW_TOOL", "read,write,shell")


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
                    f"profile {profile['file'].relative_to(ROOT)} is empty or missing "
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
        "--add-dir", str(ROOT),
    ]
    if add_project_root:
        command += ["--add-dir", str(get_project_root())]
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


def invoke_agent(task, args):
    profile, reason = resolve_profile(task["targetAgent"], list_profiles())
    if profile is None:
        return False, reason
    print(f"[    ] profile {profile['file'].relative_to(ROOT)} -> --agent {profile['name']}")
    instruction = STAGE_INSTRUCTIONS.get(task["stage"], "Complete this blackboard task.")
    message = (
        f"Project root: {get_project_root()}\n"
        f"{instruction}\n"
        "Resolve `path` against the project root above. Task JSON:\n"
    )
    message += json.dumps({key: task[key] for key in PROMPT_KEYS}, indent=2)
    command = build_copilot_command(args, profile, message)
    print(f"[cmd ] {args.copilot_bin} -p <task> -s --agent {profile['name']} --no-ask-user --add-dir {ROOT} --allow-all-tools --allow-tool {args.allow_tool} --allow-all-paths")
    return run_agent(command, args.timeout, ROOT)


def run_discovery(args, description_path):
    profile, reason = resolve_profile(DISCOVERY_AGENT, list_profiles())
    if profile is None:
        return False, reason
    with telemetry.span("blackboard.discovery", {"description": str(description_path)}) as current:
        message = build_discovery_prompt(description_path)
        command = build_copilot_command(args, profile, message)
        print(f"[cmd ] {args.copilot_bin} -p <description> -s --agent {profile['name']} --no-ask-user --add-dir {ROOT} --allow-all-tools --allow-tool {args.allow_tool} --allow-all-paths")
        ok, reason = run_agent(command, args.timeout, ROOT)
        if ok:
            reason = validate_report(DRAFT_REPORT, "discovery")
            ok = reason is None
        if not ok:
            telemetry.mark_error(current, reason)
            return False, reason
        return True, ""


def run_mapping(args):
    profile, reason = resolve_profile(MAPPING_AGENT, list_profiles())
    if profile is None:
        return False, reason
    with telemetry.span("blackboard.mapping", {"draft": str(DRAFT_REPORT)}) as current:
        message = build_mapping_prompt()
        command = build_copilot_command(args, profile, message)
        print(f"[cmd ] {args.copilot_bin} -p <draft> -s --agent {profile['name']} --no-ask-user --add-dir {ROOT} --allow-all-tools --allow-tool {args.allow_tool} --allow-all-paths")
        ok, reason = run_agent(command, args.timeout, ROOT)
        if ok:
            reason = validate_report(ANALYSIS_REPORT, "final")
            ok = reason is None
        if not ok:
            telemetry.mark_error(current, reason)
            return False, reason
        return True, ""


def run_architect(args):
    profile, reason = resolve_profile(ARCHITECT_AGENT, list_profiles())
    if profile is None:
        return False, reason
    with telemetry.span("blackboard.architect", {"analysis": str(ANALYSIS_REPORT)}) as current:
        message = build_architect_prompt(get_project_root(), RUNNER_SCRIPT)
        command = build_copilot_command(args, profile, message)
        print(f"[cmd ] {args.copilot_bin} -p <reports> -s --agent {profile['name']} --no-ask-user --add-dir {ROOT} --allow-all-tools --allow-tool {args.allow_tool} --allow-all-paths")
        ok, reason = run_agent(command, args.timeout, ROOT)
        if ok and not PLAN_FILE.is_file():
            ok, reason = False, f"architect finished but {PLAN_FILE.relative_to(ROOT)} was not created"
        if ok and not any(QUEUE_DIR.glob("*.json")) and not any(COMPLETE_DIR.glob("*.json")):
            ok, reason = False, "architect finished but emitted no tasks"
        if not ok:
            telemetry.mark_error(current, reason)
        return ok, reason


def run_pass(args):
    processed = 0
    while True:
        entries = read_queue()
        if not entries:
            return processed, []
        dirty = False
        tasks = []
        for _, file, task, reason in entries:
            if reason:
                send_to_error(file, reason, task)
                print(f"[error] {file.name}: {reason}")
                dirty = True
            else:
                tasks.append((file, task))
        if dirty:
            continue
        index = load_index()
        kept = []
        for file, task in tasks:
            reason = validate(task, index)
            if reason:
                send_to_error(file, reason, task)
                print(f"[error] {file.name}: {reason}")
                dirty = True
            else:
                kept.append((file, task))
        if dirty:
            continue
        complete_ids = {file.stem for file in COMPLETE_DIR.glob("*.json")}
        queued = [task for _, task in kept]
        ready = [(file, task) for file, task in kept if claimable(task, queued, complete_ids)]
        if not ready:
            return processed, [task["id"] for _, task in kept]
        file, task = ready[0]
        print(f"[run ] {task['id']} -> {task['targetAgent']} ({task['path']})")
        ok, reason = invoke_agent(task, args)
        if ok and task["stage"] != 0 and not (get_project_root() / task["path"]).exists():
            ok, reason = False, f"agent finished but {task['path']} was not created"
        if ok:
            ok, reason = run_verification(get_project_root(), args.verify, args.verify_scope, task, args.verify_timeout)
        if ok:
            with telemetry.span("blackboard.complete", {"file": file.name, **telemetry.task_attributes(task)}):
                file.replace(COMPLETE_DIR / file.name)
            print(f"[done] {task['id']}")
        else:
            send_to_error(file, reason, task)
            print(f"[fail] {task['id']}: {reason}")
        processed += 1
        if args.limit and processed >= args.limit:
            return processed, []


def main():
    parser = argparse.ArgumentParser(
        description="Blackboard orchestrator (GitHub Copilot CLI): DDD discovery -> context mapping -> architect -> container/tester/coder/evaluator."
    )
    parser.add_argument("--seed", metavar="FILE", help="business description to analyze (default: first seed/*_description.md)")
    parser.add_argument("--output", metavar="DIR", help="directory where the project is generated (default: projects/<seed title>)")
    parser.add_argument("--force", action="store_true", help="regenerate existing DDD reports")
    parser.add_argument("--watch", action="store_true", help="poll the queue continuously")
    parser.add_argument("--interval", type=int, default=5, help="seconds between polls in watch mode")
    parser.add_argument("--timeout", type=int, default=900, help="seconds before a copilot run is aborted")
    parser.add_argument("--verify", choices=VERIFY_MODES, default="typecheck", help="post-task compile/check gate run in the project root")
    parser.add_argument("--verify-scope", choices=("task", "global"), default="task", help="verification scope")
    parser.add_argument("--verify-timeout", type=int, default=300, help="seconds before verification times out")
    parser.add_argument("--limit", type=int, default=0, help="stop after N tasks (0 = no limit)")
    parser.add_argument("--copilot-bin", default=DEFAULT_COPILOT_BIN, help="copilot binary (or COPILOT_BIN)")
    parser.add_argument("--allow-tool", default=DEFAULT_ALLOW_TOOL, help="comma-separated tools granted to agents")
    parser.add_argument("--emit", nargs="+", metavar="FILE", help="validate and emit task JSON files to queue, then exit")
    args = parser.parse_args()
    telemetry.init_telemetry()
    for folder in (QUEUE_DIR, COMPLETE_DIR, ERROR_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    if args.emit:
        reason = emit_tasks(args.emit)
        if reason:
            print(f"[emit-error] {reason}")
            return 1
        return 0
    description = resolve_seed(args.seed)
    if description is None or not description.is_file():
        print(f"[fatal] no seed description found in {SEED_DIR} (use --seed FILE)")
        return 2
    print(f"[seed ] {description}")
    project_root = set_project_root(resolve_output_path(args.output, description))
    print(f"[root] generated project: {project_root}")

    if args.force:
        for report in (DRAFT_REPORT, ANALYSIS_REPORT):
            report.unlink(missing_ok=True)

    if shutil.which(args.copilot_bin) is None:
        print(f"[fatal] {args.copilot_bin!r} not found on PATH (install GitHub Copilot CLI or set COPILOT_BIN)")
        return 2

    if validate_report(DRAFT_REPORT, "discovery") is None and not args.force:
        print(f"[skip] discovery report already valid: {DRAFT_REPORT.relative_to(ROOT)}")
    else:
        DRAFT_REPORT.unlink(missing_ok=True)
        ok, reason = run_discovery(args, description)
        if not ok:
            print(f"[fatal] discovery: {reason}")
            return 1
        print("[ddd ] discovery report ready")

    if validate_report(ANALYSIS_REPORT, "final") is None and not args.force:
        print(f"[skip] mapping report already valid: {ANALYSIS_REPORT.relative_to(ROOT)}")
    else:
        ANALYSIS_REPORT.unlink(missing_ok=True)
        ok, reason = run_mapping(args)
        if not ok:
            print(f"[fatal] mapping: {reason}")
            return 1
        print("[ddd ] analysis report ready")

    print("[plan] architect reading the validated reports")
    ok, reason = run_architect(args)
    if not ok:
        print(f"[fatal] architect: {reason}")
        return 1
    print("[plan] architect finished; processing queue")

    try:
        if args.watch:
            while True:
                run_pass(args)
                time.sleep(args.interval)
        processed, blocked = run_pass(args)
    except KeyboardInterrupt:
        return 130
    if blocked:
        print(f"[blocked] {', '.join(blocked)}")
        return 1
    if args.verify != "none":
        ok, reason = verify_project(get_project_root(), args.verify, args.verify_timeout)
        if not ok:
            print(f"[fatal] {reason}")
            return 1
        print(f"[verify] project passes {args.verify}")
    print(f"[ok] processed {processed} task(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
