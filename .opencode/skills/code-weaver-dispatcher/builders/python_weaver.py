"""Python weaver: pip-style projects.

No code-weaver executable is registered for Python yet, so build() returns None.
"""
from pathlib import Path

from base_weaver import CodeWeaver

CONFIG_FILES = ("pyproject.toml", "requirements.txt", "setup.py")


class PythonWeaver(CodeWeaver):
    language = "python"

    def detect(self, root: Path) -> str | None:
        for name in CONFIG_FILES:
            config = root / name
            if config.is_file():
                text = config.read_text(encoding="utf-8", errors="ignore").lower()
                return "fastapi" if "fastapi" in text else "none"
        return None

    def build(self, root: Path, changes: dict, changes_path: Path,
              tool_root: Path | None) -> list[str] | None:
        return None


BUILDER = PythonWeaver()
