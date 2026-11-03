"""Python builder: pip-style projects.

No AST executable is registered for Python yet, so build() returns None.
"""
from pathlib import Path

from base import AstBuilder

CONFIG_FILES = ("pyproject.toml", "requirements.txt", "setup.py")


class PythonBuilder(AstBuilder):
    language = "python"

    def detect(self, root: Path) -> str | None:
        for name in CONFIG_FILES:
            config = root / name
            if config.is_file():
                text = config.read_text(encoding="utf-8", errors="ignore").lower()
                return "fastapi" if "fastapi" in text else "none"
        return None

    def build(self, root: Path, ctx: dict, tool_root: Path | None) -> list[str] | None:
        return None


BUILDER = PythonBuilder()
