"""Task closure: every production type the unit tests import must have a producer task.

The architect decomposes work by "units", but stage-1 tests import whole
collaborator graphs (ports, events, exceptions, repositories). Surefire compiles
the entire test source set for every run, so a single producer-less import turns
the whole domain permanently red. This module finds those gaps and can emit the
missing stage-2 producers (+ matching stage-3 evaluators) through the normal
validated queue writer.

Usage:
  python3 orchestrators/closure.py            # report gaps
  python3 orchestrators/closure.py --emit     # queue missing producer/refactor tasks

Requires a project root previously selected by an orchestrator run (default: the
first projects/<seed> layout is resolved through workspace at call time).
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

import settings
import task_queue
import tasks
import test_gate
import workspace

MAX_REPORT = 6


def _imported_classes(test_file: Path):
    """(class_name, package) pairs imported from the test file's own root package."""
    text = test_file.read_text(encoding="utf-8", errors="ignore")
    pkg = re.search(r"package ([\w.]+);", text)
    if not pkg:
        return
    root = ".".join(pkg.group(1).split(".")[:4])
    for line in text.splitlines():
        m = re.match(r"import (?:static )?([\w.]+);", line)
        if not m or not m.group(1).startswith(root + "."):
            continue
        segs = m.group(1).split(".")
        if segs[-1][:1].isupper():
            yield segs[-1], ".".join(segs[:-1])
        elif len(segs) >= 2 and segs[-2][:1].isupper():
            yield segs[-2], ".".join(segs[:-2])


def _kind_hint(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith("event"):
        return "domain event (record) carrying the fields the tests construct"
    if lowered.endswith("port") or "publisher" in lowered:
        return "domain port interface with exactly the methods the tests invoke or stub"
    if lowered.endswith("repository"):
        return "repository port interface with the find/save operations the tests stub"
    if lowered.endswith("exception"):
        return "domain exception thrown where the tests expect it"
    if lowered.endswith("status") or lowered.endswith("state") or lowered.endswith("hold"):
        return "domain enum/aggregate the tests reference"
    return "domain collaborator defined from its test usages only"


TYPE_POSITIONS = (
    r"new\s+([A-Z]\w*)\s*[(<]",
    r"\b([A-Z]\w*)\s+[a-z_$]\w*\s*[=,)]",
    # declaration positions the plain patterns miss: a method return type
    # (`public ValidationStatus validate(`) or a field (`ValidationStatus status;`).
    # JDK/imports in these positions are subtracted below or by the blocklists.
    r"\b([A-Z]\w*)\s+[a-z_$][\w$]*\s*[(;]",
    r"([A-Z]\w*)\.class",
    r"instanceof\s+([A-Z]\w*)",
    r"catch\s*\(\s*([A-Z]\w*)",
    r"throws\s+([A-Z]\w*)",
    r"isInstanceOf\(\s*([A-Z]\w*)",
    r"forClass\(\s*([A-Z]\w*)\.class",
)

# `java.util.function.BiFunction.class` is a JDK type used fully qualified: no import
# statement exists to filter it, and no domain task may ever own it.
JDK_QUALIFIED_RE = re.compile(r"\b(?:java|javax|jakarta)\.[\w.]*\.([A-Z]\w*)\b")


def source_files(folder: Path) -> list:
    """Source files of any supported language under a folder (Java layout is not assumed)."""
    return test_gate.source_files(folder)


def _declared_in_file(text: str) -> set:
    return set(re.findall(r"\b(?:class|interface|enum|record)\s+([A-Z]\w*)", text))


STRING_LITERAL_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
LINE_COMMENT_RE = re.compile(r"//[^\n]*")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def _code_only(text: str) -> str:
    """Drop literals and comments: SQL inside a string is not a reference to a Java type."""
    return LINE_COMMENT_RE.sub("", BLOCK_COMMENT_RE.sub("", STRING_LITERAL_RE.sub('""', text)))


def _is_type_shape(name: str) -> bool:
    """A Java type is CamelCase; an ALL-CAPS token is a SQL keyword or a constant."""
    return tasks.is_type_shape(name)


def _used_without_import(text: str, imported_or_same: set, declared: set, external: set | None = None) -> set:
    """Uppercase names appearing in type position that the file neither imports nor declares."""
    found = set()
    code = _code_only(text)
    for pattern in TYPE_POSITIONS:
        found |= set(re.findall(pattern, code))
    found -= set(JDK_QUALIFIED_RE.findall(code))
    # ANY dotted chain qualifies its segments: `org.mockito.InOrder inOrder = ...` and
    # `Outer.Inner` are fully-qualified / outer-qualified uses, not bare
    # references needing an import (the old java-only strip missed every dependency FQN
    # and the closure gate aborted as if a task were missing for a MOCKITO class).
    qualified = {m.group(1) for m in re.finditer(r"(?<=[a-z0-9_$])\.([A-Z]\w*)", code)}
    qualified |= {m.group(1) for m in re.finditer(r"\b([A-Z]\w*)\.[a-z_]", code)}
    qualified |= {m.group(2) for m in re.finditer(r"\b([A-Z]\w*)\.([A-Z]\w*)\b", code)}
    blocklist = {"Test", "BeforeEach", "AfterEach", "BeforeAll", "AfterAll", "Nested",
                 "DisplayName", "TempDir", "Timeout", "RepeatedTest", "EnumSource",
                 "CsvSource", "MethodSource", "ValueSource", "Mock"}
    blocklist |= {"UUID", "List", "Map", "Set", "Optional", "LocalDate",
                  "LocalDateTime", "ZoneId", "LocalTime", "Instant", "Duration", "BigDecimal",
                  "BigInteger", "ChronoUnit", "Collectors", "Stream",
                  "IllegalArgumentException", "IllegalStateException",
                  "NullPointerException", "UnsupportedOperationException", "NumberFormatException",
                  "ClassCastException", "ArithmeticException", "IndexOutOfBoundsException",
                  "ConcurrentModificationException", "TimeoutException"}
    # java.lang is never importable-by-name in a test and never needs a producer task:
    # StringBuilder there was reported as an unclosed import of the domain.
    blocklist |= test_gate.JAVA_LANG_NAMES
    return {name for name in (found - imported_or_same - declared - blocklist - qualified
                            - (external or set()))
            if _is_type_shape(name)}


def _outer_types(produced: set, index: dict, slug: str, main_stems: set) -> set:
    """Names that can host a nested type: real task exports and existing source files."""
    exports = {name for task in index.values()
               if task.get("project") == slug and isinstance(task.get("stage"), int)
               and task["stage"] == settings.TDD_STAGE
               and (name := tasks.exported_product(task))}
    return exports | main_stems


def _is_nested_type(package: str, cls: str, outer: set) -> bool:
    """True when `cls` is imported as Outer.Inner, i.e. its package ends in an owned type.

    A nested enum is part of the unit that owns its outer class, not a file of its own:
    emitting it as a producer task would create `Outer/Inner.java` and duplicate ownership.
    """
    parts = [part for part in package.split(".") if part]
    return len(parts) >= 2 and parts[-1] in outer and parts[-1] != cls


def gaps(service_root: Path, slug: str, index: dict) -> list:
    """Stack-dispatched producer-less reference scan for one domain.

    Java keeps full fidelity (`_java_gaps`); Python and TypeScript get conservative
    strategies that only report references grounded in the project's OWN tree. Unknown
    stacks return nothing: closure must never fabricate work it cannot ground. Every gap
    dict carries a `layout` key so the emitted task lands in the right source layout.
    """
    if (service_root / "src" / "test" / "java").is_dir() or (service_root / "pom.xml").is_file() \
            or (service_root / "build.gradle").is_file() or (service_root / "build.gradle.kts").is_file():
        return _java_gaps(service_root, slug, index)
    if any((service_root / marker).exists() for marker in ("pyproject.toml", "setup.py", "requirements.txt")) \
            or any(next((service_root / d).rglob("*.py"), None) is not None
                   for d in ("src", "app", "backend") if (service_root / d).is_dir()):
        return _python_gaps(service_root, slug, index)
    if (service_root / "package.json").is_file() and (service_root / "src").is_dir():
        return _ts_gaps(service_root, slug, index)
    return []


def _python_gaps(service_root: Path, slug: str, index: dict) -> list:
    """`from pkg.mod import Thing` / `import pkg.mod` with no module or symbol behind them.

    Stdlib AST only - no grammar guessing. A reference is a gap only when its dotted module
    roots in a top-level package of THIS project, and neither an existing production module
    defines the symbol nor a queued stage-2 producer exports it. The gap's `package` is the
    dotted module; `class` is the missing symbol (or the missing module's own tail).
    """
    import ast
    main_roots = [c for c in (service_root / "src", service_root / "app", service_root / "backend")
                  if c.is_dir()]
    defined, module_paths, module_files = set(), set(), {}
    for root in main_roots:
        for f in root.rglob("*.py"):
            if any(part in ("tests", "test", "__pycache__") for part in f.parts):
                continue
            try:
                dotted = ".".join(f.relative_to(root).with_suffix("").parts)
            except ValueError:
                continue
            if not dotted or dotted.split(".")[0] == "tests":
                continue
            module_paths.add(dotted)
            module_files[dotted] = f.relative_to(service_root).as_posix()
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            except (SyntaxError, OSError):
                continue
            for node in getattr(tree, "body", []):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined.add((dotted, node.name))
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    for alias in node.names:
                        defined.add((dotted, alias.asname or alias.name.split(".")[0]))
    top_packages = {p.split(".")[0] for p in module_paths if p}
    producers = {tasks.exported_product(t) for t in index.values()
                 if t.get("project") == slug and isinstance(t.get("stage"), int)
                 and t["stage"] == settings.TDD_STAGE and tasks.exported_product(t)}
    missing = {}
    test_files = []
    for d in ("tests", "src/tests", "test"):
        folder = service_root / d
        if folder.is_dir():
            test_files += list(folder.rglob("test_*.py"))
    for f in test_files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    continue  # test-local relative import: no production producer expected
                module = node.module or ""
                names = [a.asname or a.name.split(".")[0] for a in node.names if a.name != "*"]
            elif isinstance(node, ast.Import):
                module, names = "", []
                for alias in node.names:
                    if alias.name.split(".")[0] in top_packages:
                        module, names = alias.name, [alias.asname or alias.name.split(".")[0]]
            else:
                continue
            if not module or module.split(".")[0] not in top_packages:
                continue
            if module in module_paths:
                for name in names:
                    if (module, name) in defined or name in producers or (module, name) in missing:
                        continue
                    missing[(module, name)] = {"class": name, "package": module,
                                               "test": f.name, "layout": "python",
                                               "file_path": module_files.get(module)}
            elif (module, module) not in missing:
                missing[(module, module)] = {"class": module.split(".")[-1], "package": module,
                                             "test": f.name, "layout": "python",
                                             "file_path": _python_new_module_path(module, module_files)}
    return list(missing.values())


TS_RELATIVE_RE = re.compile(r"^\.{1,3}[\w./-]*$")


def _python_new_module_path(module: str, module_files: dict) -> str:
    """Best path for a module that does not exist yet: attach it to the nearest existing
    ancestor (sibling-module dir or package dir), else mirror under the roots in use."""
    parts = module.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:cut])
        tail = "/".join(parts[cut:]) + ".py"
        if prefix in module_files and module_files[prefix].endswith(".py"):
            return module_files[prefix][:-3] + "/" + tail
        inner = prefix + "."
        hosts = [p for m, p in module_files.items() if m.startswith(inner)]
        if hosts:
            return hosts[0].rsplit("/", 1)[0] + "/" + tail
    root = next((p.split("/")[0] for p in module_files.values()), "src")
    return "/".join([root, *parts]) + ".py"


def _ts_gaps(service_root: Path, slug: str, index: dict) -> list:
    """TypeScript named imports from RELATIVE specifiers with no export behind them.

    Bare specifiers (`@nestjs/common`) are third-party and never gaps. A relative import is
    a gap when its target file (`.ts/.tsx/.js/index.ts` resolution) is missing, or exists
    without that named export while no queued producer writes it. The gap keeps the raw
    specifier and the importing folder so the emitted path lands beside its consumers.
    """
    src = service_root / "src"
    main_files = [f for f in src.rglob("*.ts") if not f.name.endswith((".spec.ts", ".test.ts"))]
    exports = set()
    for f in main_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        exports |= set(re.findall(r"export\s+(?:default\s+)?(?:abstract\s+)?"
                                  r"(?:class|interface|enum|type|const|function)\s+(\w+)", text))
        for group in re.findall(r"export\s*\{([^}]+)\}", text):
            exports |= {part.strip().split(" as ")[-1].strip() for part in group.split(",") if part.strip()}
    producers = {tasks.exported_product(t) for t in index.values()
                 if t.get("project") == slug and isinstance(t.get("stage"), int)
                 and t["stage"] == settings.TDD_STAGE and tasks.exported_product(t)}
    missing = {}
    for f in src.rglob("*.spec.ts"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for group, spec in re.findall(
                r"import\s*(?:type\s*)?\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", text):
            if not TS_RELATIVE_RE.match(spec):
                continue
            target = str(f.parent / spec)
            resolved = next((Path(target + ext) for ext in ("", ".ts", ".tsx", ".js", "/index.ts")
                             if Path(target + ext).is_file()), None)
            from_dir = str(f.parent.relative_to(service_root))
            if resolved is None:
                tail = spec.split("/")[-1]
                import posixpath
                missing.setdefault((spec, tail), {"class": tail, "package": spec,
                                                  "test": f.name, "layout": "typescript",
                                                  "file_path": posixpath.normpath(
                                                      str(f.parent / spec)) .replace(
                                                      str(service_root) + "/", "") + ".ts"})
                continue
            for part in group.split(","):
                name = part.strip().split(" as ")[0].strip()
                if not name or name in exports or name in producers:
                    continue
                missing.setdefault((spec, name), {"class": name, "package": spec,
                                                  "test": f.name, "layout": "typescript",
                                                  "file_path": resolved.relative_to(service_root).as_posix()})
    return list(missing.values())
def _java_gaps(service_root: Path, slug: str, index: dict) -> list:
    """Types this domain's Java tests reference (imports or type positions) with no producer.

    Coverage is per (class, package): Java imports are fully qualified, so a producer
    in one package never satisfies an import from another. Keying by simple name let
    the first package win and livelocked every test importing the same name elsewhere.
    """
    test_root = service_root / "src" / "test" / "java"
    main_root = service_root / "src" / "main" / "java"
    if not test_root.is_dir():
        return []
    produced_pairs = set()
    outer_names = set()
    for task in index.values():
        if task.get("project") == slug and isinstance(task.get("stage"), int) \
                and task["stage"] == settings.TDD_STAGE:
            name = tasks.exported_product(task)
            if not name:
                continue
            path = str(task.get("path", "")).replace("\\", "/")
            match = re.search(r"src/main/[^/]+/(.+)/[^/]+$", path)
            produced_pairs.add((name, match.group(1).replace("/", ".") if match else ""))
            outer_names.add(name)
    main_stems = set()
    if main_root.is_dir():
        for f in source_files(main_root):
            pkg = str(f.parent.relative_to(main_root)).replace("/", ".")
            produced_pairs.add((f.stem, pkg))
            main_stems.add(f.stem)
            # Nested types (record Row declared inside Box.java) ARE
            # declared here: a stem-only scan made every nested collaborator look like
            # an unscheduled hole and aborted healthy drains.
            for name in _declared_in_file(f.read_text(encoding="utf-8", errors="ignore")):
                if name != f.stem:
                    produced_pairs.add((name, pkg))
    produced = {name for name, _ in produced_pairs}
    outer = outer_names | main_stems
    external = set(test_gate.external_type_index(service_root)) - produced
    missing = {}
    seen_declared = {}

    def declared_in_tree(f, tree_root):
        cached = seen_declared.get(tree_root)
        if cached is None:
            cached = {d: _declared_in_file(d.read_text(encoding="utf-8", errors="ignore"))
                      for d in source_files(tree_root)}
            seen_declared[tree_root] = cached
        return cached.get(f, set()) | {
            n for other, names in cached.items()
            if other != f and other.parent == f.parent for n in names}

    for tree_root in (test_root, main_root):
        for f in source_files(tree_root):
            text = f.read_text(encoding="utf-8", errors="ignore")
            pkg_match = re.search(r"package ([\w.]+);", text)
            own_pkg = pkg_match.group(1) if pkg_match else ""
            imported_simple = set(re.findall(r"import (?:static )?[\w.]*?\.([A-Z]\w*);", text))
            declared = declared_in_tree(f, tree_root)
            for cls, pkg in _imported_classes(f):
                if (cls, pkg) in produced_pairs or (cls, pkg) in missing or _is_nested_type(pkg, cls, outer):
                    continue
                if cls in external:  # dependency-provided type: a missing import, not a hole
                    continue
                missing[(cls, pkg)] = {"class": cls, "package": pkg, "test": f.name}
            for cls in _used_without_import(text, imported_simple | produced, declared, external):
                key = (cls, own_pkg)
                if key not in missing and not _is_nested_type(own_pkg, cls, outer):
                    missing[key] = {"class": cls, "package": own_pkg, "test": f.name}
    return list(missing.values())


def _snake(name: str) -> str:
    """CamelCase to snake_case for python module/file names."""
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def _build_task(stage: int, task_id: str, slug: str, gap: dict, scaffold_id: str, tester_id: str | None) -> dict:
    layout = gap.get("layout", "java")
    if layout == "python":
        rel_path = gap.get("file_path") or "src/" + gap["package"].replace(".", "/") + "/" + _snake(gap["class"]) + ".py"
        pkg_label = gap["package"]
    elif layout == "typescript":
        rel_path = gap.get("file_path") or "src/" + gap["package"].lstrip("./") + ".ts"
        pkg_label = gap["package"]
    else:
        pkg_path = gap["package"].replace(".", "/")
        rel_path = f"src/main/java/{pkg_path}/{gap['class']}.java"
        pkg_label = gap["package"]
    import posixpath
    rel_path = posixpath.normpath(rel_path)
    segments = set(rel_path.split("/"))
    layer = ("application" if "application" in segments else
             "infrastructure" if "infrastructure" in segments else
             "interface" if segments & {"interface", "api", "rest"} else
             "domain" if "domain" in segments else
             "application" if layout == "java" and ".application" in "." + pkg_label else "domain")
    depends = [scaffold_id] + ([tester_id] if tester_id else [])
    return {
        "id": task_id,
        "targetAgent": settings.STAGE_AGENTS[stage],
        "stage": stage,
        "dependsOn": depends,
        "path": rel_path,
        "kind": settings.STAGE_KINDS[stage][0],
        "layer": layer,
        "ast_hints": {"package": pkg_label or slug, "implements": [],
                      "dependencies": [], "methods": []},
        "feature": None,
        "export": gap["class"],
        "intent": (f"Bounded context {slug}: define {gap['class']} ({_kind_hint(gap['class'])}) in "
                   f"package {gap['package']}. Contract is fixed by its usage in {gap['test']}; "
                   "implement the smallest correct type that satisfies every usage."),
        "project": slug,
    }


def emit_all(report=print) -> int:
    root = workspace.get_project_root()
    emitted = 0
    for service in sorted((root / settings.PROJECTS_SUBDIR).glob("*")) if (root / settings.PROJECTS_SUBDIR).is_dir() else []:
        slug = service.name
        for gap in gaps(service, slug, task_queue.load_index(include_error=True)):
            scaffold_id = task_queue.scaffold_task_id(slug)
            index = task_queue.load_index(include_error=True)
            tester_id = next((t["id"] for _, t in sorted(index.items())
                              if t.get("project") == slug and t.get("stage") == settings.TESTER_STAGE
                              and gap["test"] in str(t.get("path", ""))), None)
            if tester_id is None:
                # The reference came from a woven MAIN file (a coder collaborated with a
                # type nobody scheduled): inherit the tester of the unit that OWNS that
                # file, so the producer's contract is anchored to a real red record.
                ref_stem = Path(str(gap["test"])).stem
                owner = next((t for _, t in sorted(index.items())
                              if t.get("project") == slug and t.get("stage") == settings.TDD_STAGE
                              and Path(str(t.get("path", ""))).stem == ref_stem), None)
                if owner:
                    tester_id = next((str(dep) for dep in owner.get("dependsOn", [])
                                      if str(dep).startswith("T1-")), None)
            t2_id = task_queue.next_task_id(settings.TDD_STAGE)
            batch = [_build_task(settings.TDD_STAGE, t2_id, slug, gap, scaffold_id, tester_id)]
            t3_id = task_queue.next_task_id(3)
            t3 = _build_task(3, t3_id, slug, gap, scaffold_id, tester_id)
            t3["dependsOn"] = [t2_id]
            batch.append(t3)
            tmp = Path(tempfile.mkdtemp(prefix="closure-"))
            paths = []
            for task in batch:
                p = tmp / f"{task['id']}-{slug}.json"
                p.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
                paths.append(str(p))
            reason = task_queue.emit_tasks(paths)
            if reason:
                report(f"[closure] skipped {slug}/{gap['class']}: {reason}")
                continue
            emitted += len(batch)
    return emitted


def main() -> int:
    ap = argparse.ArgumentParser(description="Report or close task-closure gaps (test imports without producers).")
    ap.add_argument("--emit", action="store_true", help="queue the missing stage-2/3 tasks")
    ap.add_argument("--project-root", help="generated project root (default: orchestrator layout under projects/)")
    args = ap.parse_args()
    if args.project_root:
        workspace.set_project_root(args.project_root)

    total = 0
    root = workspace.get_project_root()
    services = sorted((root / settings.PROJECTS_SUBDIR).glob("*")) if (root / settings.PROJECTS_SUBDIR).is_dir() else []
    for service in services:
        found = gaps(service, service.name, task_queue.load_index(include_error=True))
        total += len(found)
        names = [g["class"] for g in found][:MAX_REPORT]
        print(f"{service.name:16} gaps={len(found):2} {names}")
    if args.emit:
        print("---- emitting ----")
        print("emitted tasks:", emit_all())
    return 0 if total or args.emit else 1


if __name__ == "__main__":
    sys.exit(main())
