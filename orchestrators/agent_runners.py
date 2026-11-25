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


# ---- child-adoption shim (2026-11-24 operator incident) ----------------------------
# A killed orchestrator must not leave an agent CLI running as an orphan: it streams a
# transcript nobody reads and bills every turn. Live-stop evidence: an operator SIGTERM
# between two repair rounds left a copilot session alive for a minute; the engine had
# already launched the NEXT one when the parent died. Every Popen'd child is adopted
# here, and SIGTERM/SIGINT kills the live children before re-raising the default
# disposition, so the orchestrator's exit status stays what the operator expects.
import signal as _signal

_LIVE_CHILDREN = set()
_shim_installed = {"done": False}


def adopt_child(process):
    """Register a live child; install the death shim once (main thread only)."""
    _LIVE_CHILDREN.add(process)
    _install_death_shim()


def release_child(process):
    _LIVE_CHILDREN.discard(process)


def kill_child(process):
    """Kill a spawned CLI AND its whole group: the Copilot CLI is a node wrapper that
    forks the native binary; killing only the wrapper orphans the billed child (live
    2026-11-24: budget-kill left a native copilot running under init)."""
    import os as _os
    import signal as _sig
    try:
        _os.killpg(_os.getpgid(process.pid), _sig.SIGKILL)
    except (OSError, ProcessLookupError):
        try:
            process.kill()
        except OSError:
            pass


def kill_live_children():
    for proc in list(_LIVE_CHILDREN):
        _LIVE_CHILDREN.discard(proc)
        kill_child(proc)  # group kill: the CLI wrapper AND its native child


def _install_death_shim():
    if _shim_installed["done"]:
        return
    _shim_installed["done"] = True
    for sig in (_signal.SIGTERM, _signal.SIGINT):
        try:
            _signal.signal(sig, _dying)
        except (ValueError, OSError):
            return  # not the main thread: the child set still covers explicit kills


def _dying(signum, frame):
    kill_live_children()
    _signal.signal(signum, _signal.SIG_DFL)
    import os as _os
    _os.kill(_os.getpid(), signum)


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
            start_new_session=True,
        )
    except OSError as exc:
        return False, f"cannot launch {command[0]}: {exc}"
    adopt_child(process)
    timed_out = {"flag": False}

    def kill_on_timeout():
        timed_out["flag"] = True
        kill_child(process)

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
        release_child(process)
    if timed_out["flag"]:
        return False, f"agent timed out after {timeout}s"
    if process.returncode != 0:
        tail = "".join(lines).strip()[-1000:]
        return False, f"agent exited {process.returncode}: {tail}"
    return True, ""
