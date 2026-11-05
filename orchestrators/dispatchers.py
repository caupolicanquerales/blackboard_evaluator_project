"""Skill dispatchers called by the pipeline between agent stages.

Every function here shells out to a ``.opencode/skills`` script and interprets its
JSON contract; none of them import agent logic or touch source files directly.
"""
import json
import subprocess
import sys

import agent_runners
import settings
import telemetry
import workspace


def red_phase_problem(task):
    """Return a reason string if blackboard/red-phase/<id>.json is missing or invalid, else None.

    The red-phase artifact lives on the repository-root blackboard (same root the
    queue writers use). `compile_error` and `assertion_failure` are VALID reds
    (java-junit5 skill); only a pre-implementation pass is rejected.
    """
    path = settings.RED_PHASE_DIR / f"{task['id']}.json"
    if not path.is_file():
        return f"red-phase file missing: {path.name}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"red-phase file unreadable: {exc}"
    if not isinstance(data, dict) or not data:
        return f"red-phase file is empty or not an object: {path.name}"
    if data.get("executed") is not True:
        return f"red-phase not executed: {path.name}"
    status = data.get("status")
    if status == "passed":
        return f"red-phase passed before implementation, not a valid red: {path.name}"
    return None


def _dispatch(command, timeout, span_name, task_id, failure_reason):
    """Shared subprocess call for the skill dispatchers.

    Returns (returncode, stdout, telemetry_reason_or_None). ``failure_reason``
    turns a non-zero exit into the reason recorded on the span.
    """
    with telemetry.span(span_name, {"task": task_id}) as current:
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                cwd=str(settings.ROOT),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            telemetry.mark_error(current, str(exc))
            return None, str(exc), str(exc)
        if result.returncode != 0:
            reason = failure_reason(result.returncode, result.stdout)
            telemetry.mark_error(current, reason)
            return result.returncode, result.stdout, reason
        return result.returncode, result.stdout, None


def evaluate_result_problem(task):
    """Return a reason string if blackboard/evaluate-results/<id>.json is missing or not green, else None."""
    path = settings.ROOT / "blackboard" / "evaluate-results" / f"{task['id']}.json"
    if not path.is_file():
        return f"evaluate-results file missing: {path.name}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"evaluate-results file unreadable: {exc}"
    if not isinstance(data, dict) or not data:
        return f"evaluate-results file is empty or not an object: {path.name}"
    if data.get("executed") is not True:
        return f"evaluate-results not executed: {path.name}"
    final_test = data.get("final_test")
    status = final_test.get("status") if isinstance(final_test, dict) else None
    if status != "passed":
        return f"evaluator did not finish green (final_test.status={status!r})"
    return None


def run_ast_dispatcher(task):
    """Run the AST dispatcher once agent-tester finishes, then mark agent-coder as ready.

    The dispatcher reads <root>/blackboard and writes blackboard/ast-context/<id>.json.
    `unsupported` is an outcome, not a failure: a brand-new unit has no production source
    to extract yet, and agent-coder proceeds from the red-phase record. A dispatcher
    failure is reported but does not block agent-coder.
    """
    command = [sys.executable, str(settings.AST_DISPATCHER),
               "--root", str(settings.ROOT),
               "--project-root", str(workspace.project_root_for(task["project"])),
               "--task-id", task["id"]]
    print(f"[ast ] {task['id']} running ast-dispatcher")
    code, stdout, reason = _dispatch(
        command, settings.AST_DISPATCH_TIMEOUT, "blackboard.ast_dispatcher", task["id"],
        lambda exit_code, text: f"dispatcher exit {exit_code}",
    )
    if code is None:
        print(f"[ast ] {task['id']} dispatcher could not run: {stdout}")
        return False
    status = ""
    detail = ""
    try:
        payload = json.loads(stdout)
        status = str(payload.get("status") or "")
        detail = str(payload.get("reason") or "")
    except (TypeError, json.JSONDecodeError):
        pass
    if status == "unsupported":
        print(f"[ast ] {task['id']} no context yet (coder proceeds from red-phase): {detail[:200]}")
        return True
    if code != 0 or status not in ("ok", ""):
        print(f"[ast ] {task['id']} dispatcher exit {code}: {agent_runners.verify_tail(stdout)}")
        return False
    print(f"[ast ] {task['id']} context saved to blackboard/ast-context/{task['id']}.json")
    print(f"[next] {task['id']} tester done; agent-coder notified to start")
    return True


def run_code_weaver_dispatcher(task):
    """Splice the agent-coder payload into the source tree via the code-weaver dispatcher.

    The dispatcher reads blackboard/coder-changes/<id>.json, selects the weaver
    executable by payload language and records blackboard/weave-results/<id>.json.
    Returns None on success, or a reason string; the reason is fed back to the
    coder as TDD retry feedback, so it must explain what to re-emit with --retry.
    """
    command = [
        sys.executable,
        str(settings.CODE_WEAVER_DISPATCHER),
        "--root", str(settings.ROOT),
        "--project-root", str(workspace.project_root_for(task["project"])),
        "--task-id", task["id"],
    ]
    print(f"[weave] {task['id']} running code-weaver-dispatcher")
    code, stdout, reason = _dispatch(
        command, settings.WEAVER_DISPATCH_TIMEOUT, "blackboard.code_weaver_dispatcher", task["id"],
        lambda exit_code, text: _weaver_failure_reason(text),
    )
    if code is None:
        return f"code-weaver dispatcher could not run: {reason}"
    if code != 0:
        print(f"[weave] {task['id']} failed (exit {code})")
        return reason
    print(f"[weave] {task['id']} changes applied; result saved to blackboard/weave-results/{task['id']}.json")
    return None


def _weaver_failure_reason(output_text):
    """Compact the dispatcher JSON into a single actionable line for coder retry feedback."""
    try:
        summary = json.loads(output_text)
    except (TypeError, json.JSONDecodeError):
        summary = None
    detail = ""
    if isinstance(summary, dict):
        detail = str(summary.get("reason") or summary.get("stdout") or summary.get("stderr") or "").strip()
    if not detail:
        detail = agent_runners.verify_tail(output_text)
    return f"code-weaver failed: {detail[:400] if detail else 'no dispatcher output'}"
