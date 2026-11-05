"""Strategy interface for AST builders.

Each language has one module in this folder. The module exposes a module-level
BUILDER instance of a subclass of AstBuilder. The dispatcher discovers those
modules at runtime; it never imports a language by name.
"""
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path

TOOL_BUILD_TIMEOUT_SECONDS = int(os.environ.get("TOOL_BUILD_TIMEOUT", "900"))

BUILD_MARKERS = ("pom.xml", "build.gradle", "build.gradle.kts")


def tool_project_dir(tool_root: Path) -> Path | None:
    """Project folder able to rebuild the tool, from a JAR path, a target/ or a project dir."""
    tool_root = tool_root.expanduser().resolve()
    if tool_root.is_file():
        parent = tool_root.parent
        return parent.parent if parent.name == "target" else None
    if tool_root.name == "target":
        return tool_root.parent if (tool_root.parent / "pom.xml").is_file() or \
            any((tool_root.parent / marker).is_file() for marker in BUILD_MARKERS) else None
    if (tool_root / "target").is_dir() or any((tool_root / marker).is_file() for marker in BUILD_MARKERS):
        return tool_root
    return None


def _build_command(project: Path) -> list[str] | None:
    """Maven or Gradle command that produces the tool artifact without running its tests."""
    if (project / "pom.xml").is_file():
        args = ["-q", "-DskipTests", "package"]
    elif (project / "build.gradle").is_file() or (project / "build.gradle.kts").is_file():
        args = ["-q", "build", "-x", "test"]
    else:
        return None
    script = "mvnw" if (project / "pom.xml").is_file() else "gradlew"
    wrapper = project / script
    if wrapper.is_file():
        return ([str(wrapper)] if os.access(wrapper, os.X_OK) else ["sh", str(wrapper)]) + args
    binary = "mvn" if (project / "pom.xml").is_file() else "gradle"
    return [binary, *args] if shutil.which(binary) else None


def build_tool_project(tool_root: Path, timeout: int = TOOL_BUILD_TIMEOUT_SECONDS) -> bool:
    """Compile the AST tool when its JAR is absent (a fresh clone ships sources only).

    Messages go to stderr: the dispatcher writes its JSON contract on stdout and any
    extra line there would corrupt it.
    """
    project = tool_project_dir(tool_root)
    command = _build_command(project) if project else None
    if command is None:
        print(f"[tool] no Maven/Gradle project found from {tool_root}; cannot generate the JAR",
              file=sys.stderr)
        return False
    print(f"[tool] {project.name}: JAR missing, building with {' '.join(command)}", file=sys.stderr)
    try:
        result = subprocess.run(command, cwd=str(project), capture_output=True, text=True,
                                timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[tool] build failed: {exc}", file=sys.stderr)
        return False
    if result.returncode != 0:
        tail = (result.stdout + "\n" + result.stderr).strip().splitlines()[-8:]
        print(f"[tool] build exit {result.returncode}: {' | '.join(tail)}", file=sys.stderr)
        return False
    return True


def load_project_env(start: Path | None = None) -> Path | None:
    """Load the nearest .env (walking up from start) into os.environ without overriding.

    Relative values of keys ending in _ROOT or _DIR resolve against the .env folder.
    """
    current = (start or Path(__file__)).resolve()
    for folder in [current, *current.parents]:
        env_file = folder / ".env"
        if env_file.is_file():
            base_dir = env_file.parent
            for raw in env_file.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = (part.strip() for part in line.split("=", 1))
                if key.endswith(("_ROOT", "_DIR")) and value and not Path(value).is_absolute():
                    value = str((base_dir / value).resolve())
                os.environ.setdefault(key, value)
            return env_file
    return None


class AstBuilder(ABC):
    """Strategy: how to detect a language project and build its AST command."""

    language: str = ""

    @abstractmethod
    def detect(self, root: Path) -> str | None:
        """Return the framework name when this builder owns the project, else None."""

    @abstractmethod
    def build(self, project_root: Path, ctx: dict, tool_root: Path | None) -> list[str] | None:
        """Return the argv that runs the AST executable, or None when it cannot run."""

    def missing_command_reason(self, project_root: Path, ctx: dict,
                               tool_root: Path | None) -> str:
        """Why build() returned None, as one actionable line; empty when unknown."""
        return ""
