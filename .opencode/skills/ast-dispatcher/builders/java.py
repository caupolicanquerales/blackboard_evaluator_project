"""Java builder: Maven or Gradle projects, executed through an AST extractor fat JAR.

The extractor location comes from the --tool-root option. Nothing is hardcoded here.
"""
import os
from pathlib import Path

from base import AstBuilder


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


JAR_NAME_KEY = "AST_JAR_NAME"


def resolve_executable_jar(tool_root: Path) -> Path | None:
    """Accept a JAR path, a project folder with target/, or a target/ folder directly.

    When AST_JAR_NAME is set (in .env), that exact file is used; otherwise the newest fat JAR.
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


class JavaBuilder(AstBuilder):
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

    def build(self, root: Path, ctx: dict, tool_root: Path | None) -> list[str] | None:
        target_class = ctx.get("target_class")
        target_method = ctx.get("target_method")
        if tool_root is None or not target_class or not target_method:
            return None
        jar = resolve_executable_jar(tool_root)
        if jar is None:
            return None
        return [
            "java", "-jar", str(jar),
            "-s", str(root / "src" / "main" / "java"),
            "-t", target_class,
            "-m", target_method,
        ]


BUILDER = JavaBuilder()
