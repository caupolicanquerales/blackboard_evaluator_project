"""YAML units: the payload carries the whole file text in `body`.

Spring configuration (`application.yml`) is not an AST unit: there is no weaver tool for
it and none is needed. The coder's brief for a config task asks for the full desired file,
so weaving is a validated full write of `body` to `targetFile`; content correctness belongs
to the following build gate (Spring parses the file at boot).
"""
import sys
from pathlib import Path

from base_weaver import CodeWeaver


class YamlWeaver(CodeWeaver):
    language = "yaml"

    def detect(self, root: Path) -> str | None:
        for resources in (root / "src" / "main" / "resources", root / "src" / "test" / "resources"):
            if resources.is_dir() and any(f.suffix in (".yml", ".yaml") for f in resources.rglob("*")):
                return "springboot"
        return None

    def build(self, root: Path, changes: dict, changes_path: Path,
              tool_root: Path | None) -> list[str] | None:
        if not isinstance(changes.get("body"), str) or not changes.get("body").strip():
            return None
        if not isinstance(changes.get("targetFile"), str) or not changes.get("targetFile"):
            return None
        exec_script = Path(__file__).resolve().with_name("_text_write_exec.py")
        if not exec_script.is_file():
            return None
        return [sys.executable, str(exec_script), str(changes_path), str(root)]

    def missing_command_reason(self, root: Path, changes: dict, changes_path: Path,
                               tool_root: Path | None) -> str:
        if not isinstance(changes.get("body"), str) or not changes.get("body").strip():
            return "yaml unit payload must carry the full file text in `body`"
        if not isinstance(changes.get("targetFile"), str) or not changes.get("targetFile"):
            return "yaml unit payload is missing `targetFile`"
        return ""


BUILDER = YamlWeaver()
