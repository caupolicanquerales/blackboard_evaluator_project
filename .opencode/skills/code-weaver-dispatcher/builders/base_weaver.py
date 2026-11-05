"""Strategy interface for code-weaver builders.

Each language has one module in this folder. The module exposes a module-level
BUILDER instance of a subclass of CodeWeaver. The dispatcher discovers those
modules at runtime; it never imports a language by name.
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path


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


class CodeWeaver(ABC):
    """Strategy: how to detect a language project and build its code-weaver command."""

    language: str = ""

    @abstractmethod
    def detect(self, root: Path) -> str | None:
        """Return the framework name when this weaver owns the project, else None."""

    @abstractmethod
    def build(self, root: Path, changes: dict, changes_path: Path,
              tool_root: Path | None) -> list[str] | None:
        """Return the argv that runs the weaver executable, or None when it cannot run.

        changes is the validated coder-changes payload; changes_path its JSON file,
        which self-contained weavers (e.g. the Java JAR) may consume directly.
        """
