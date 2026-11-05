"""Framework verification gates: detect the stack and run the build/check command."""
import shutil
import subprocess
import sys

import agent_runners
import settings
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
    """Detect the project stack from its config files and return the verification command.

    Returns None when mode is 'none', when no known stack is detected, or when the
    detected stack has no applicable check for the requested mode.
    """
    if mode == "none":
        return None

    if (project_root / "pom.xml").exists():
        return (
            ("mvn", "-q", "-DskipTests", "compile")
            if mode == "typecheck"
            else ("mvn", "-q", "-DskipTests", "package")
        )

    if (project_root / "build.gradle").exists() or (project_root / "build.gradle.kts").exists():
        wrapper = project_root / "gradlew"
        gradle = str(wrapper) if wrapper.exists() else "gradle"
        return (
            (gradle, "compileJava", "-q")
            if mode == "typecheck"
            else (gradle, "build", "-q")
        )

    if (project_root / "pubspec.yaml").exists():
        return ("flutter", "analyze") if mode == "typecheck" else ("flutter", "build", "bundle")

    if (project_root / "angular.json").exists():
        return (("npx", "tsc", "--noEmit") if mode == "typecheck"
                else ("npx", "ng", "build", "--configuration", "development"))

    if (project_root / "package.json").exists():
        if mode == "typecheck":
            if (project_root / "tsconfig.json").exists() or (project_root / "tsconfig.app.json").exists():
                return ("npx", "tsc", "--noEmit")
            return None
        return ("npm", "run", "build")

    if (project_root / "go.mod").exists():
        return ("go", "vet", "./...") if mode == "typecheck" else ("go", "build", "./...")

    if (project_root / "Cargo.toml").exists():
        return ("cargo", "check") if mode == "typecheck" else ("cargo", "build")

    if any((project_root / name).exists()
           for name in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")):
        return (sys.executable, "-m", "compileall", "-q", ".")

    return None


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


def verify_project(project_root, mode, timeout):
    command = get_framework_verification_commands(project_root, mode)
    if command is None:
        return True, ""
    with telemetry.span("blackboard.verify", {"scope": "project", "mode": mode}) as current:
        code, output = _run_verification(command, project_root, timeout)
        if code is None:
            telemetry.mark_error(current, output)
            return False, output
        if code == 0:
            return True, ""
        reason = f"verification failed: {agent_runners.verify_tail(output)}"
        telemetry.mark_error(current, reason)
        return False, reason
