"""Generic subprocess plumbing for agent runs and log tails.

The OpenCode backend streams a merged stdout/stderr; the Copilot backend has its
own event reader and lives in ``copilot_backend``.
"""
import subprocess
import threading

import telemetry


def verify_tail(text, limit=1200):
    """Last ``limit`` characters of a subprocess log, for compact retry feedback."""
    return text.strip()[-limit:]


def agent_name(command):
    try:
        return command[command.index("--agent") + 1]
    except (ValueError, IndexError):
        return None


def run_agent(command, timeout, cwd):
    """Run an agent CLI to completion with a watchdog; every line is echoed."""
    with telemetry.span("blackboard.agent", {"agent": agent_name(command), "timeout": timeout}) as current:
        ok, reason = _run_agent(command, timeout, cwd)
        if not ok:
            telemetry.mark_error(current, reason)
        return ok, reason


def _run_agent(command, timeout, cwd):
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
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
    lines = []
    try:
        for line in process.stdout:
            print(f"    | {line.rstrip()}")
            lines.append(line)
        process.wait()
    finally:
        watchdog.cancel()
    if timed_out["flag"]:
        return False, f"agent timed out after {timeout}s"
    if process.returncode != 0:
        tail = "".join(lines).strip()[-1000:]
        return False, f"agent exited {process.returncode}: {tail}"
    return True, ""
