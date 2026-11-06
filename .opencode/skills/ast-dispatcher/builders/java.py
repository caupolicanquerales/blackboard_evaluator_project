"""Java builder: Maven or Gradle projects, executed through an AST extractor fat JAR.

The extractor location comes from the --tool-root option. Nothing is hardcoded here.
"""
import os
import re
from pathlib import Path

from base import AstBuilder, build_tool_project


MAX_FACTS = 20
MAX_USAGE_LINES = 40


def _split_top_level(args_text: str) -> list[str]:
    """Split a call's argument list at top-level commas (nested parens/braces kept)."""
    parts, depth, current = [], 0, []
    for ch in args_text:
        if ch in "(<[{":
            depth += 1
        elif ch in ")>]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if "".join(current).strip():
        parts.append("".join(current).strip())
    return parts


def _args_after(text: str, open_index: int) -> str:
    """Raw argument text inside the balanced parentheses opening at `open_index`."""
    depth = 0
    for i in range(open_index, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_index + 1:i]
    return text[open_index + 1:]


def extract_java_contract(test_text: str, simple_type: str) -> dict | None:
    """The API a brand-new Java unit must implement, read mechanically from its own test.

    The production class cannot exist yet (that is the red phase), and the extractor JAR
    describes only classes already on disk: the executable specification is the test.
    Every construction, invocation and stub of the unit's type is collected so the coder
    writes exactly the API the tests demand instead of guessing signatures from bare names.
    """
    if not simple_type or not test_text.strip():
        return None
    constructors: list[list[str]] = []
    static_calls: list[dict] = []
    calls: list[dict] = []
    verified: list[str] = []
    for match in re.finditer(rf"\bnew\s+{simple_type}\s*\(", test_text):
        args = [a[:80] for a in _split_top_level(_args_after(test_text, match.end() - 1))][:8]
        if args not in constructors:
            constructors.append(args)
    for match in re.finditer(rf"\b{simple_type}\s*\.\s*([a-z]\w*)\s*\(", test_text):
        entry = {"method": match.group(1),
                 "args": [a[:80] for a in _split_top_level(_args_after(test_text, match.end() - 1))][:8]}
        if entry not in static_calls:
            static_calls.append(entry)
    variables = set(re.findall(rf"\b{simple_type}\s+([a-z]\w*)\b", test_text))
    for var in sorted(variables):
        for match in re.finditer(rf"\b{var}\s*\.\s*([a-z]\w*)\s*\(", test_text):
            entry = {"receiver": var, "method": match.group(1),
                     "args": [a[:80] for a in _split_top_level(_args_after(test_text, match.end() - 1))][:8]}
            line_start = test_text.rfind("\n", 0, match.start()) + 1
            line = test_text[line_start:test_text.find("\n", match.start())]
            lhs = re.search(rf"([A-Z][\w<>,\s.]*?)\s+\w+\s*=\s*{var}\.{match.group(1)}\(", line)
            if lhs:
                entry["returns"] = " ".join(lhs.group(1).split())
            stub = re.search(rf"{var}\.{match.group(1)}\([^;]*?\)\)?\s*\.thenReturn\((.+?)\)\s*[;,]", line)
            if stub:
                entry["stubbed_to"] = stub.group(1).strip()[:80]
            if entry not in calls:
                calls.append(entry)
        for match in re.finditer(rf"\bverify(?:NoMoreInteractions|Never)?\s*\([^)]*{var}[^)]*\)\s*(?:\.\w+\([^)]*\))?\s*\.\s*([a-z]\w*)\s*\(", test_text):
            if match.group(1) not in verified:
                verified.append(match.group(1))
    usage_lines = []
    for raw in test_text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("import ", "package ", "//")):
            continue
        if simple_type in line or any(re.search(rf"\b{v}\b", line) for v in variables):
            usage_lines.append(line[:160])
    contract = {"type": simple_type, "constructors": constructors[:MAX_FACTS],
                "static_calls": static_calls[:MAX_FACTS], "calls": calls[:MAX_FACTS],
                "verified": verified[:MAX_FACTS], "usage_lines": usage_lines[:MAX_USAGE_LINES]}
    if not (constructors or static_calls or calls or verified or usage_lines):
        return None
    return contract


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


def ensure_executable_jar(tool_root: Path) -> Path | None:
    """Resolve the extractor JAR, compiling the tool project when the clone has no target/.

    A fresh clone ships the extractor as sources only, so a missing JAR is normal:
    the build runs once here and the lookup is retried. A build that fails or yields
    no JAR is reported as unavailable, never as a stale path.
    """
    jar = resolve_executable_jar(tool_root)
    if jar is not None:
        return jar
    if not build_tool_project(tool_root):
        return None
    return resolve_executable_jar(tool_root)


class JavaBuilder(AstBuilder):
    language = "java"

    def test_contract(self, project_root: Path, ctx: dict) -> dict | None:
        """Precise Java extraction: overrides the language-neutral base with the test AST facts."""
        relative = ctx.get("test_path")
        target = ctx.get("target_class")
        if not isinstance(relative, str) or not relative.strip() or not target:
            return None
        test_file = project_root / relative
        if not test_file.is_file():
            return None
        try:
            text = test_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        return extract_java_contract(text, str(target).split(".")[-1])

    def detect(self, root: Path) -> str | None:
        pom = root / "pom.xml"
        if pom.is_file():
            return "spring" if "spring-boot" in _read(pom) else "none"
        for gradle in ("build.gradle", "build.gradle.kts"):
            build_file = root / gradle
            if build_file.is_file():
                return "spring" if "org.springframework.boot" in _read(build_file) else "none"
        return None

    def source_dir(self, project_root: Path) -> Path:
        return project_root / "src" / "main" / "java"

    def resolve_class(self, project_root: Path, target_class: str) -> str | None:
        """Fully qualified name of the target class.

        The queue exports the simple name; the extractor wants `package.Simple`
        and reads `src/main/java/<path>/<Simple>.java`, so a simple name is
        resolved by locating the file. A class that is not on disk yet (brand-new
        unit) has no context to extract, so None is returned.
        """
        if not target_class:
            return None
        src_dir = self.source_dir(project_root)
        if "." in target_class:
            relative = target_class.replace(".", "/") + ".java"
            return target_class if (src_dir / relative).is_file() else None
        matches = sorted(src_dir.rglob(f"{target_class}.java")) if src_dir.is_dir() else []
        if not matches:
            return None
        relative = matches[0].relative_to(src_dir).with_suffix("")
        return ".".join(relative.parts[:-1] + (relative.parts[-1],))

    def build(self, project_root: Path, ctx: dict, tool_root: Path | None) -> list[str] | None:
        target_class = ctx.get("target_class")
        target_method = ctx.get("target_method")
        if tool_root is None or not target_class or not target_method:
            return None
        jar = ensure_executable_jar(tool_root)
        if jar is None:
            return None
        resolved = self.resolve_class(project_root, target_class)
        if resolved is None:
            return None
        return [
            "java", "-jar", str(jar),
            "-s", str(self.source_dir(project_root)),
            "-t", resolved,
            "-m", target_method,
        ]

    def missing_command_reason(self, project_root: Path, ctx: dict, tool_root: Path | None) -> str:
        gaps = []
        if tool_root is None:
            gaps.append("--tool-root or $AST_TOOL_ROOT is not set")
        elif resolve_executable_jar(tool_root) is None:
            gaps.append(f"no extractor JAR under {tool_root} and its automatic build produced none "
                        "(run mvn -DskipTests package in that folder and check the [tool] lines)")
        if not ctx.get("target_class"):
            gaps.append("target_class unknown (task export missing)")
        elif self.resolve_class(project_root, ctx["target_class"]) is None:
            gaps.append(f"target class {ctx['target_class']} not in {self.source_dir(project_root)} yet")
        if not ctx.get("target_method"):
            gaps.append("target_method unknown (red-phase has no method hint)")
        return "; ".join(gaps)


BUILDER = JavaBuilder()
