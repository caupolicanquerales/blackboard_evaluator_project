"""Framework verification gates: detect the stack and run the build/check command."""
import shutil
import subprocess

import agent_runners
import settings
import stacks
import telemetry


DOCKER_HINT = (
    "stage 0 scaffolds generate the project through the MCP servers that run in Docker, so the "
    "agents need a usable daemon. No sudo is required during a run: do it once from a terminal, "
    "'sudo usermod -aG docker <user>' for future sessions plus "
    "'sudo setfacl -m u:<user>:rw /var/run/docker.sock' to grant the already open session right "
    "now, then relaunch the orchestrator. If ACLs are unavailable, 'sudo chmod 666 /var/run/docker.sock' "
    "works until the daemon restarts. Never put a sudo password in .env or in any prompt: the agent "
    "logs would carry it."
)


def docker_access(timeout=20):
    """(ok, reason): can this process (and therefore the agents it spawns) reach the Docker daemon?"""
    if shutil.which("docker") is None:
        return False, f"docker CLI not found on PATH. {DOCKER_HINT}"
    try:
        result = subprocess.run(("docker", "info", "--format", "{{.ServerVersion}}"),
                                capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"docker info failed: {exc}. {DOCKER_HINT}"
    if result.returncode != 0:
        lines = (result.stderr or result.stdout or "").strip().splitlines()
        return False, f"{lines[0] if lines else 'docker info failed'}. {DOCKER_HINT}"
    return True, ""


def stage_zero_queued():
    """True while a stage 0 scaffold task is still waiting in the queue."""
    return any(file.name.startswith("T0-") for file in settings.QUEUE_DIR.glob("*.json"))



def get_framework_verification_commands(project_root, mode):
    """Stack-appropriate verification command - the ONE toolchain registry decides.

    (2026-11-26 consolidation) this function used to be an eight-branch if-chain of
    build markers and commands, a private duplicate of facts test_gate and assembly
    also carried; every incident appended a branch to this copy. Detection order,
    wrapper preference and every command now live in stacks.ROWS.

    Returns None when mode is 'none', when no known stack is detected, or when the
    detected stack has no applicable check for the requested mode.
    """
    if mode == "none":
        return None
    return stacks.verification_command(project_root, mode)


def _run_verification(command, project_root, timeout):
    try:
        process = subprocess.run(
            command,
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"verification could not run: {exc}"
    return process.returncode, process.stdout or ""


def run_verification(project_root, mode, scope, task, timeout):
    command = get_framework_verification_commands(project_root, mode)
    if command is None:
        return True, ""
    with telemetry.span("blackboard.verify", {"file": f"{task['id']}.json", "mode": mode}) as current:
        code, output = _run_verification(command, project_root, timeout)
        if code is None:
            telemetry.mark_error(current, output)
            return False, output
        if code == 0:
            return True, ""
        reason = f"verification failed: {agent_runners.verify_tail(output)}"
        telemetry.mark_error(current, reason)
        return False, reason


_VERIFY_MEMO = {}   # (root, mode) -> (tree-fingerprint, ok, reason, typed-verdict)


def verify_project(project_root, mode, timeout):
    """Stack-appropriate build/typecheck gate, memoized on the tree BYTES.

    The verdict is a pure function of (command, tree content): re-running maven/tsc
    on an unchanged tree burns a full build per unit per pass (T3's evaluator gate
    runs it once per attempt). If the content fingerprint is unchanged since the last
    verdict for this (root, mode), replay it; any weave, revert or repair moves the
    fingerprint and the build runs for real.
    """
    command = get_framework_verification_commands(project_root, mode)
    if command is None:
        return True, ""
    import test_gate
    # O4: hash the CANONICAL tree (after the engine's own deterministic normalizers)
    # so a repair pass is never mistaken for an agent's change to the tree
    test_gate.canonicalize_tree(project_root)
    fingerprint = test_gate._tree_fingerprint(project_root)
    memo = _VERIFY_MEMO.get((str(project_root), mode))
    if memo and memo[0] == fingerprint:
        return memo[1], memo[2]
    with telemetry.span("blackboard.verify", {"scope": "project", "mode": mode}) as current:
        code, output = _run_verification(command, project_root, timeout)
        if code is None:
            telemetry.mark_error(current, output)
            _VERIFY_MEMO[(str(project_root), mode)] = (
                fingerprint, False, output,
                {"verdict_version": test_gate._runner_module().VERDICT_VERSION,
                 "status": "not_run", "reason": output})
            return False, output
        if code == 0:
            _VERIFY_MEMO[(str(project_root), mode)] = (
                fingerprint, True, "",
                {"verdict_version": test_gate._runner_module().VERDICT_VERSION,
                 "status": "passed", "exit_code": 0})
            return True, ""
        reason = f"verification failed: {agent_runners.verify_tail(output)}"
        telemetry.mark_error(current, reason)
        # O1 (2026-11-25): the build's raw text is normalized through the TEST TOOL'S
        # parser - one dialect owner for every verdict source, not only test runs.
        # Deferral decisions downstream read THIS field set, never the reason string.
        _VERIFY_MEMO[(str(project_root), mode)] = (
            fingerprint, False, reason,
            test_gate.parse_verdict_text(output, project_root))
        return False, reason


def verify_verdict(project_root, mode):
    """The typed verdict behind the last (root, mode) memo, or None when uncached.
    (O1) The evaluator-gate deferral reads missing_symbols/problem_kinds from here."""
    memo = _VERIFY_MEMO.get((str(project_root), mode))
    return memo[3] if memo and len(memo) > 3 else None
