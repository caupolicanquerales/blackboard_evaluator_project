"""Go weaver: modules with go.mod.

No code-weaver executable is registered for Go yet, so build() returns None.
"""
from pathlib import Path

from base_weaver import CodeWeaver


class GoWeaver(CodeWeaver):
    language = "go"

    def detect(self, root: Path) -> str | None:
        return "none" if (root / "go.mod").is_file() else None

    def build(self, root: Path, changes: dict, changes_path: Path,
              tool_root: Path | None) -> list[str] | None:
        return None


BUILDER = GoWeaver()
