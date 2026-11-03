"""Go builder: modules with go.mod.

No AST executable is registered for Go yet, so build() returns None.
"""
from pathlib import Path

from base import AstBuilder


class GoBuilder(AstBuilder):
    language = "go"

    def detect(self, root: Path) -> str | None:
        return "none" if (root / "go.mod").is_file() else None

    def build(self, root: Path, ctx: dict, tool_root: Path | None) -> list[str] | None:
        return None


BUILDER = GoBuilder()
