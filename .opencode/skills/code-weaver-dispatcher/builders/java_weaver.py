"""Java weaver: splices coder bodies into source files through the ast_weaver_java fat JAR.

The JAR location comes from the --tool-root option. Nothing is hardcoded here.
The JAR consumes the coder-changes payload itself (--changes-json), so this
builder only validates the file reference and resolves the executable.
"""
import os
from pathlib import Path

from base_weaver import CodeWeaver

JAR_NAME_KEY = "WEAVER_JAR_NAME"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def resolve_executable_jar(tool_root: Path) -> Path | None:
    """Accept a JAR path, a project folder with target/, or a target/ folder directly.

    When WEAVER_JAR_NAME is set (in .env), that exact file is used; otherwise the newest fat JAR.
    """
    if tool_root.is_file() and tool_root.suffix == ".jar":
        return tool_root
    target_dir = tool_root / "target" if (tool_root / "target").is_dir() else tool_root
    if not target_dir.is_dir():
        return None
    jar_name = os.environ.get(JAR_NAME_KEY, "").strip()
    if jar_name:
        named = target_dir / jar_name
        return named if named.is_file() else None
    candidates = [
        jar for jar in target_dir.glob("*.jar")
        if not jar.name.startswith("original-")
        and not jar.name.endswith(("-sources.jar", "-javadoc.jar", ".original"))
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda jar: jar.stat().st_mtime)


class JavaWeaver(CodeWeaver):
    language = "java"

    def detect(self, root: Path) -> str | None:
        pom = root / "pom.xml"
        if pom.is_file():
            return "spring" if "spring-boot" in _read(pom) else "none"
        for gradle in ("build.gradle", "build.gradle.kts"):
            build_file = root / gradle
            if build_file.is_file():
                return "spring" if "org.springframework.boot" in _read(build_file) else "none"
        return None

    def build(self, root: Path, changes: dict, changes_path: Path,
              tool_root: Path | None) -> list[str] | None:
        if tool_root is None:
            return None
        jar = resolve_executable_jar(tool_root)
        if jar is None:
            return None
        return [
            "java", "-jar", str(jar),
            "--root", str(root),
            "--changes-json", str(changes_path),
        ]


BUILDER = JavaWeaver()
