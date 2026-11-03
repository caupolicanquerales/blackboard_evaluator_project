"""TypeScript builder: Node projects with a TypeScript toolchain.

No AST executable is registered for TypeScript yet, so build() returns None.
"""
from pathlib import Path

from base import AstBuilder


class TypeScriptBuilder(AstBuilder):
    language = "typescript"

    def detect(self, root: Path) -> str | None:
        package = root / "package.json"
        if not package.is_file():
            return None
        text = package.read_text(encoding="utf-8", errors="ignore")
        if not ((root / "tsconfig.json").is_file() or "typescript" in text):
            return None
        return "nestjs" if "@nestjs/core" in text else "none"

    def build(self, root: Path, ctx: dict, tool_root: Path | None) -> list[str] | None:
        return None


BUILDER = TypeScriptBuilder()
