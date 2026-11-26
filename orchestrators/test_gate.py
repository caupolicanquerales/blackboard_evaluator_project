"""Green-phase test gate: re-runs the tester's recorded test command.

The tester (stage 1) executes the scoped test through the shared
``run-test-tool.py`` and persists its JSON (plus the exact command) to
``blackboard/red-phase/<id>.json``. After the code-weaver applies the coder's
body, the orchestrator re-runs that same command: a deterministic gate, no LLM
in the loop. A non-passing status becomes retry feedback for the coder inside
``execute_with_tdd``; after MAX_TDD_RETRIES the task moves to the error folder.
"""
import json
import re
import subprocess
import sys

import pathlib
import importlib.util
import shutil

import settings
import stacks
import tasks
import telemetry
import workspace


JAVA_LANG_NAMES = {
    "String", "Integer", "Long", "Double", "Float", "Boolean", "Byte", "Short", "Character",
    "Object", "Class", "System", "Thread", "Runnable", "Iterable", "Exception", "RuntimeException",
    "Error", "Number", "Math", "Void", "StringBuilder", "StringBuffer", "Comparable", "Enum", "Record",
    "Throwable", "CharSequence", "Cloneable", "AutoCloseable", "StackTraceElement", "Package",
    "NoSuchMethodException",
    # Complete java.lang throwable inventory: reflection signature tests write
    # `throws NoSuchFieldException` / `catch (AssertionError` against these built-ins;
    # a manual trickle of additions kept handing the closure gate a new one each run.
    "AbstractMethodError", "ArithmeticException", "ArrayIndexOutOfBoundsException",
    "ArrayStoreException", "AssertionError", "BootstrapMethodError", "ClassCastException",
    "ClassNotFoundException", "CloneNotSupportedException", "DataFormatError",
    "DuplicateFormatFlagsException", "EnumConstantNotPresentException",
    "ExceptionInInitializerError", "IllegalAccessError", "IllegalAccessException",
    "IllegalArgumentException", "IllegalFormatException", "IllegalMonitorStateException",
    "IllegalStateException", "IllegalThreadStateException", "IncompatibleClassChangeError",
    "IndexOutOfBoundsException", "InstantiationException", "InterruptedException",
    "LayerNotFoundException", "NegativeArraySizeException", "NoClassDefFoundError",
    "NoSuchFieldError", "NoSuchFieldException", "NoSuchMethodError", "NullPointerException",
    "NumberFormatException", "ReflectiveOperationException", "SecurityException",
    "StackOverflowError", "TypeNotPresentException", "UndeclaredThrowableException",
    "UnknownError", "UnsupportedOperationException", "VerifyError",
}


JDK_TYPES = {
    "UUID": "java.util", "List": "java.util", "Map": "java.util", "Set": "java.util",
    "Optional": "java.util", "Arrays": "java.util", "Collections": "java.util",
    "LocalDate": "java.time", "LocalDateTime": "java.time", "ZoneId": "java.time",
    "Instant": "java.time", "ChronoUnit": "java.time", "Duration": "java.time",
    "BigDecimal": "java.math", "Collectors": "java.util.stream", "Stream": "java.util.stream",
}

# The static lists above are SEEDS, never the truth: hand-enumerating a language's
# vocabulary is the treadmill that killed a run on `Throwable` (a java.lang type no
# one had typed yet). The authoritative inventory is derived ONCE from the installed
# JDK's module filesystem (jrt:) and cached; every consumer of JAVA_LANG_NAMES gets
# the derived superset. No JDK or a failed probe falls back to the seed silently -
# worst case returns to the pre-probe behavior, never a false gap.
_JLANG_PROBE = '''
import java.net.URI;
import java.nio.file.FileSystem;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

public class JLangTypes {
    public static void main(String[] args) throws Exception {
        FileSystem fs = FileSystems.getFileSystem(URI.create("jrt:/"));
        try (Stream<Path> s = Files.list(fs.getPath("/modules/java.base/java/lang"))) {
            s.map(p -> p.getFileName().toString())
             .filter(n -> n.endsWith(".class") && !n.contains("$"))
             .map(n -> n.substring(0, n.length() - 6))
             .sorted()
             .forEach(System.out::println);
        }
    }
}
'''


def java_lang_names():
    """JAVA_LANG_NAMES plus every top-level java.lang type of the installed JDK."""
    cache = settings.GATE_CACHE_DIR / "javalang-types.txt"
    names = set(JAVA_LANG_NAMES)
    try:
        names |= {n for n in cache.read_text(encoding="utf-8").split() if n}
        return names
    except OSError:
        pass
    import subprocess
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as td:
            src = pathlib.Path(td) / "JLangTypes.java"
            src.write_text(_JLANG_PROBE, encoding="utf-8")
            out = subprocess.run(["java", str(src)], capture_output=True, text=True, timeout=60)
        derived = {n for n in out.stdout.split() if n and n[0].isupper() and not n.islower()}
        if out.returncode == 0 and len(derived) >= 40:
            settings.GATE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text("\n".join(sorted(derived)), encoding="utf-8")
            names |= derived
    except (OSError, subprocess.SubprocessError):
        pass
    return names


_REPAIR_STATE = {}   # str(root) -> tree fingerprint the last repair pass ran on


_JAVA_NON_CODE = re.compile(
    r'"""(?:[^\\]|\\.)*?"""'          # text blocks
    r'|"(?:[^"\\\n]|\\.)*"'           # string literals
    r"|'(?:[^'\\\n]|\\.)*'"           # char literals
    r'|//[^\n]*'                      # line comments
    r'|/\*.*?\*/', re.S)               # block comments


def _strip_non_code(text):
    """Comment/string-blind view of a Java source. The used-name scanners MUST read
    only this view: scanning raw text let a word inside a prose comment
    ('// A lone late sample...') resolve to a unique classpath class
    (checkerframework `...units.qual.A`) and the engine INSERTED A REAL IMPORT
    into a main-tree file between gates, breaking the whole module compile
    (observed live, run6 12:10:00).
    """
    return _JAVA_NON_CODE.sub(" ", text)


def repair_test_imports(project_root):
    """Deterministically fix missing or malformed same-project imports in Java sources.

    Testers sometimes reference a production type that lives in another package
    without importing it; javac then reports the unit's own class as missing and
    no coder run can fix it. Nested types are worse: a `record` nested inside a
    top-level type's file is importable ONLY through its enclosing class, so
    `import p.RawSampleDto;` never resolves and a bare same-package use does not
    compile either. Coders repeat the same mistakes in MAIN sources, and a wrong
    import there classifies as a cascade the retry loop defers forever. Adding or
    re-routing an import never changes behavior: it only resolves a name the file
    already uses. Returns the number of files repaired.

    The pass is a pure function of the tree BYTES, so it is gated on the content
    fingerprint: an unchanged tree since the previous pass provably yields no
    changes - the whole-tree scan is skipped, per every unit's gate call.
    """
    root = pathlib.Path(project_root)
    fp = _tree_fingerprint(root)
    if _REPAIR_STATE.get(str(root)) == fp:
        return 0
    main_root = root / "src" / "main" / "java"
    test_root = root / "src" / "test" / "java"
    if not main_root.is_dir() or not test_root.is_dir():
        return 0
    jlang = java_lang_names()   # derived java.lang superset (post-guard: cold passes only)

    top_main = {}     # package -> names declared AS the file's own top-level type
    nested_main = {}  # (package, name) -> enclosing file stems holding the nested type
    for f in main_root.rglob("*.java"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        pkg = re.search(stacks.PACKAGE_REGEX, text)
        if not pkg:
            continue
        declared = re.findall(r"\b(?:class|interface|enum|record)\s+([A-Z]\w*)", text)
        top_main.setdefault(pkg.group(1), set()).add(f.stem)
        for name in declared:
            if name != f.stem:
                nested_main.setdefault((pkg.group(1), name), set()).add(f.stem)
    # Queued producers that have not been woven yet are still the SCHEDULED home of a
    # type: repair must be able to route imports there, not only at files on disk.
    try:
        import task_queue
        for task in task_queue.load_index().values():
            if not isinstance(task, dict) or task.get("stage") != settings.TDD_STAGE:
                continue
            path = str(task.get("path", "")).replace("\\", "/")
            m = re.match(r"src/main/[^/]+/(.+)/([^/]+)\.java$", path)
            if m:
                top_main.setdefault(m.group(1).replace("/", "."), set()).add(m.group(2))
    except Exception:  # noqa: BLE001 - scheduled overlay is best effort
        pass

    external_index = external_type_index(root)

    # Rerouting needs the name to have a UNIQUE home inside the project's own package
    # namespace. `own_packages` membership is NOT required - a fabricated import package
    # (the tester inventing `p.ingestion.domain` for a type scheduled in `p.intake.domain`)
    # is precisely the case that is not declared anywhere; the >=3-segment shared prefix
    # against the unique home is what separates it from third-party imports.
    def _common_prefix_len(a: str, b: str) -> int:
        shared = 0
        for left, right in zip(a.split("."), b.split(".")):
            if left != right:
                break
            shared += 1
        return shared

    def _reroute(match):
        pkg, name = match.group(1), match.group(2)
        if name in top_main.get(pkg, set()):
            return match.group(0)
        outers = nested_main.get((pkg, name), set())
        if len(outers) == 1:
            return f"import {pkg}.{next(iter(outers))}.{name};"
        if outers:
            return match.group(0)  # ambiguous enclosing type: leave it to the agents
        homes = {p for p, names in top_main.items() if name in names}
        if len(homes) == 1:
            home = next(iter(homes))
            if home != pkg and _common_prefix_len(pkg, home) >= 3:
                return f"import {home}.{name};"
        return match.group(0)

    repaired = 0
    for tree_root in (test_root, main_root):
        for tf in tree_root.rglob("*.java"):
            src = tf.read_text(encoding="utf-8", errors="ignore")
            pkg_match = re.search(stacks.PACKAGE_REGEX, src)
            if not pkg_match:
                continue
            own_pkg = pkg_match.group(1)
            original = src
            src, _n = re.subn(r"^import ([\w.]+)\.([A-Z]\w*);$", _reroute, src, flags=re.M)
            rewrote = src != original
            code = _strip_non_code(src)   # name scanners read code ONLY (see _strip_non_code)
            own_declared = set(re.findall(r"\b(?:class|interface|enum|record)\s+([A-Z]\w*)", code))
            imported_simple = set(re.findall(r"import (?:static )?[\w.]*?\.([A-Z]\w*);", code))
            additions = []
            for cls in sorted(set(re.findall(r"\b([A-Z]\w*)\b", code))):
                if cls in jlang or cls in imported_simple or cls in own_declared:
                    continue
                if cls in top_main.get(own_pkg, set()):
                    continue  # same-package top-level: already in scope
                candidates = {f"import {pkg}.{cls};" for pkg, names in top_main.items() if cls in names}
                candidates |= {f"import {pkg}.{outer}.{cls};"
                               for (pkg, name), outers in nested_main.items() if name == cls
                               for outer in outers}
                if len(candidates) != 1:
                    continue  # absent (real gap) or ambiguous (two owners): leave it to the agents
                stmt = next(iter(candidates))
                if stmt in src:
                    continue
                if any(re.search(rf"\b{outer}\.{cls}\b", code)
                       for outer in {o for (p, n), os_ in nested_main.items() if n == cls for o in os_}):
                    continue  # already referenced through its outer type: no import needed
                additions.append(stmt)
            for cls, jdk_pkg in JDK_TYPES.items():
                if cls in jlang or cls in imported_simple or cls in own_declared:
                    continue
                if any(name == cls for (_p, name) in nested_main) or \
                   any(cls in names for names in top_main.values()):
                    continue
                if re.search(r"\b" + cls + r"\b", code):
                    additions.append(f"import {jdk_pkg}.{cls};")
            # Unambiguous dependency-provided types used bare (tester/coder forgot the
            # import): add the FQCN the classpath actually offers. Ambiguous simple
            # names stay with the agents - a guessed package compiles against the
            # wrong library, which is worse than the compile error the loop reacts to.
            for cls in sorted(set(re.findall(r"\b([A-Z]\w*)\b", code))):
                if cls in jlang or cls in imported_simple or cls in own_declared:
                    continue
                if any(name == cls for (_p, name) in nested_main) or \
                   any(cls in names for names in top_main.values()):
                    continue
                fqs = external_index.get(cls) or ()
                if len(fqs) == 1 and re.search(r"(?<![\w.])" + cls + r"\b", code) \
                        and f"import {fqs[0]};" not in src:
                    additions.append(f"import {fqs[0]};")
            if rewrote:
                tf.write_text(src, encoding="utf-8")
            if additions:
                src = src.replace(pkg_match.group(0) + "\n",
                                  pkg_match.group(0) + "\n" + "\n".join(additions) + "\n", 1)
                tf.write_text(src, encoding="utf-8")
            if rewrote or additions:
                repaired += 1
    _REPAIR_STATE[str(root)] = _tree_fingerprint(root)
    return repaired


def _tester_id(task):
    """The stage-1 id whose red-phase record gates this unit (the record is keyed by it)."""
    return next((str(dep) for dep in task.get("dependsOn", [])
                 if str(dep).startswith("T1-")), None)


def red_phase_record(task):
    """The tester's persisted result, or None when absent/unreadable (stage 1 gates presence).

    The red-phase record lives on the repository blackboard (what the tester writes
    through its writer script) and is keyed by the stage-1 task, not by the unit.
    """
    path = settings.RED_PHASE_DIR / f"{_tester_id(task) or task['id']}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _failure_detail(result, task=None):
    """Compact summary of a non-passing run-test-tool result, safe for retry feedback.

    Includes javac BLAME blocks (file:[line,col], symbol, location): without them a coder
    re-emits an unchanged payload because it cannot see WHICH call on WHICH type failed -
    each blind re-emit costs a session plus a full module build. When `task` is given,
    lines that name THIS unit's file or exported type are ranked first: the coder can act
    only on failures its payload owns, and a head of peer-unit lines is what makes it
    conclude "payload unchanged" while its own fixable error sits below the truncation.
    """
    counts = result.get("counts") or {}
    parts = [f"status={result.get('status')}", f"exit_code={result.get('exit_code')}"]
    if task:
        # The unit's OWN demanded surface first: blame lists below are dominated by
        # peer files and truncation buries the one call the coder can actually fix
        # (a unit was once charged for a member its type lacked while the text only
        # ever showed foreign missing types - blind re-emits followed). Structured field,
        # no toolchain grammar; the runner quotes the failing call itself into
        # `context`, so the coder sees the exact expression, not just its position.
        own_type = tasks.exported_product(task) or ""
        own_lines, seen_members = [], set()
        for d in (result.get("member_demands") or []):
            if not isinstance(d, dict) or d.get("owner") != own_type:
                continue
            member = str(d.get("member") or "")[:80]
            if not member or member in seen_members:
                continue
            seen_members.add(member)
            ctx = str(d.get("context") or "")[:120]
            own_lines.append(member + (f"  [at: {ctx}]" if ctx else ""))
        if own_lines:
            parts.append(f"YOUR TYPE {own_type} MUST PROVIDE: " + "; ".join(own_lines[:6]))
    if counts:
        parts.append(f"tests={counts.get('run', '?')} failures={counts.get('failures', 0)} errors={counts.get('errors', 0)}")
    missing = result.get("missing_symbols") or []
    if missing:
        parts.append("missing=" + ", ".join(str(item)[:80] for item in missing[:6]))
    blame = _blame_lines(result, limit=10)
    if task:
        own_name = str(task.get("path", "")).split("/")[-1]
        own_type = tasks.exported_product(task) or ""
        blame.sort(key=lambda entry: 0 if (own_name and own_name in entry)
                                    or (own_type and own_type in entry) else 1)
        blame = blame[:6]
    if blame:
        parts.append("blame: " + " || ".join(blame))
    named = [f for f in (result.get("failures") or []) if isinstance(f, dict) and f.get("test")]
    anonymous = [f for f in (result.get("failures") or []) if isinstance(f, dict) and not f.get("test")]
    for failure in (named + anonymous)[:3]:
        if isinstance(failure, dict):
            parts.append(f"failed {failure.get('test', '?')}: {failure.get('message', '')}")
    reason = result.get("reason")
    if reason:
        parts.append(str(reason)[:200])
    excerpt = result.get("excerpt") or []
    if excerpt and len(parts) == 1:
        parts.append("output tail: " + " | ".join(str(line) for line in excerpt[-4:]))
    return "; ".join(parts)


# Compile/test error locations across toolchains: javac "Foo.java:[12,3]", tsc "foo.ts(12,5)",
# go "main.go:12:5", pytest "test_foo.py:12:5", kotlinc "Foo.kt: (12, 3)". One generic pattern
# so the orchestrator's blame/defer logic is not Maven-only: any source file + line (+col).
SOURCE_EXT = (r"(?:java|kt|kts|scala|groovy|ts|tsx|js|jsx|mjs|cjs|go|py|rs|rb|php|c|h|cc|cpp|hpp|cs|m|swift|vue|svelte)")
FILE_REFERENCE_RE = re.compile(rf"([^\s:()\[\]]+\.{SOURCE_EXT})[\s\[\(:]+(\d+)\s*[,:]?\s*(\d+)?")

# Phrases that mark a CASCADING error (a symbol missing because a FOREIGN file is broken),
# not a structural defect of the blamed file itself.
SOURCE_SUFFIXES = {".java", ".kt", ".kts", ".scala", ".groovy", ".ts", ".tsx", ".js", ".jsx",
                   ".mjs", ".cjs", ".go", ".py", ".rs", ".rb", ".php", ".c", ".h", ".cc",
                   ".cpp", ".hpp", ".cs", ".m", ".swift", ".vue", ".svelte"}

# Verdict identity must cover EVERY file a build reads, not only compilable sources:
# a re-woven application.yml/.sql/.properties moves no java/py/ts byte, so a memo
# fingerprinted on sources alone replays the PREVIOUS red for the fixed config file
# forever (caught live 2026-11-12: T2-002's two-document yml re-weave was "verified"
# by a cached verdict in 0.2s and re-quarantined without ever running the suite).
FINGERPRINT_SUFFIXES = SOURCE_SUFFIXES | {".yml", ".yaml", ".properties", ".xml", ".sql",
                                          ".ini", ".toml", ".cfg", ".conf", ".env"}


# ---- O1 (2026-11-25 verdict contract): the test tool owns every decision input ----
# The engine binds deferral/charge/reopen decisions ONLY to typed verdict fields
# (status, missing_symbols, missing_packages, member_demands, problem_kinds,
# bean_demands, mock_impossible, blamed_files, package_symbol_demands, unit_match)
# or to registry/filesystem facts. Message text survives for DISPLAY (_failure_detail,
# coder feedback) - never for a decision that can bill a token. Every cache boundary
# below enforces the version stamp the tool carries, so a verdict written under an
# older schema can never re-decide under the newer engine: it is dropped and the
# build re-runs (deterministic, session-free).

_RUNNER_MODULE = None


def _runner_module():
    """Import run-test-tool.py as a module (cached) - ONE source for VERDICT_VERSION
    and the parse() normalizer, so the engine can never drift from the tool's schema."""
    global _RUNNER_MODULE
    if _RUNNER_MODULE is None:
        spec = importlib.util.spec_from_file_location("run_test_tool", settings.RUN_TEST_TOOL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _RUNNER_MODULE = module
    return _RUNNER_MODULE


def verdict_is_typed(result):
    return isinstance(result, dict) and "verdict_version" in result


def parse_verdict_text(text, cwd):
    """Normalize raw build output through the TOOL'S OWN parser (used by the
    verification gate, which runs a build without going through the CLI)."""
    rtt = _runner_module()
    (compile_hit, missing, missing_packages, failures, counts, demands, problems,
     beans, mocks, pkg_demands, blamed) = rtt.parse(text, str(cwd))
    status = rtt.classify(1, compile_hit, missing, failures, counts, text)
    verdict = {"verdict_version": rtt.VERDICT_VERSION, "status": status,
               "exit_code": 1, "missing_symbols": missing,
               "missing_packages": missing_packages, "failures": failures,
               "counts": counts, "blamed_files": blamed}
    if demands:
        verdict["member_demands"] = demands
    if problems:
        verdict["problem_kinds"] = problems
    if beans:
        verdict["bean_demands"] = beans
    if mocks:
        verdict["mock_impossible"] = mocks
    if pkg_demands:
        verdict["package_symbol_demands"] = pkg_demands
    return verdict


_SKIP_DIRS = {".git", "target", "build", "dist", "node_modules", "__pycache__", ".venv", "venv"}


def source_files(folder):
    """Every source file under a folder, in any supported language (never build output).

    os.walk with in-place directory pruning: the old rglob("*") enumerated every file
    under target/ (thousands) before filtering, and this runs on every fingerprint /
    repair / wave call - per attempt. Pruned walk visits ~only the real sources.
    """
    import os
    root = pathlib.Path(folder)
    if not root.is_dir():
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if pathlib.Path(fn).suffix in SOURCE_SUFFIXES:
                out.append(pathlib.Path(dirpath, fn))
    return sorted(out)


def fingerprint_files(folder):
    """source_files() plus config/resource artifacts - the full input set of a build
    and therefore of a verdict (see FINGERPRINT_SUFFIXES)."""
    import os
    root = pathlib.Path(folder)
    if not root.is_dir():
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if pathlib.Path(fn).suffix in FINGERPRINT_SUFFIXES:
                out.append(pathlib.Path(dirpath, fn))
    return sorted(out)


def _blame_lines(result, limit=3):
    """(file:line[,col] message [+ javac symbol/location detail]) blocks, toolchain-agnostic."""
    lines = [str(line) for line in (result.get("excerpt") or [])]
    blame = []
    for index, line in enumerate(lines):
        if len(blame) >= limit:
            break
        match = FILE_REFERENCE_RE.search(line)
        if not match:
            continue
        name = match.group(1).split("/")[-1].lstrip(".")
        col = f",{match.group(3)}" if match.group(3) else ""
        tail = line[match.end():].replace("[ERROR]", "").strip()[:60]
        entry = f"{name}:{match.group(2)}{col} {tail}"
        for follow in lines[index + 1:index + 3]:
            stripped = follow.replace("[ERROR]", "").strip()
            if stripped.startswith(("symbol:", "location:")):
                entry += " " + stripped[:90]
        blame.append(entry[:200])
    return blame


def canonicalize_tree(project_root):
    """O4 (2026-11-25 single-owner boundary): every engine-owned, deterministic,
    behavior-free tree normalization runs HERE, and EVERY fingerprint is taken after
    it. The old shape - repairs called ad hoc at some gate paths, fingerprints taken
    at others - made an engine repair indistinguishable from an agent's tree change
    (the rollback-hole check fired on OUR import pass). Canonicalize-then-hash means
    the hashed tree is always the canonical tree: idempotent, fingerprint-stable,
    and one honest place to see what the engine itself touches."""
    n = _count(ensure_wrapper_executables(project_root))
    n += _count(repair_test_imports(project_root))
    return n


def _count(result):
    """Normalize a normalizer's return (count or file list) to a count."""
    if isinstance(result, int):
        return result
    return len(result or [])


def ensure_wrapper_executables(project_root):
    """Restore the exec bit on build wrappers a scaffold produced or moved without it.

    Generated-in-Docker trees routinely lose +x on `mvnw`/`gradlew`; the gate's recorded
    command is `./mvnw ...` and EXEC_ERROR: Permission denied is then charged to the CODER
    as a unit failure (3 burned sessions per unit + cascade quarantines). This is tooling
    hygiene the engine owes every stack, not an edit of unit content: bit only, never text.
    """
    fixed = []
    for wrapper in stacks.WRAPPER_FILES:
        f = pathlib.Path(project_root) / wrapper
        if f.is_file() and not f.stat().st_mode & 0o111:
            try:
                f.chmod(f.stat().st_mode | 0o755)
                fixed.append(wrapper)
            except OSError:
                pass
    if fixed:
        print(f"[perm] {project_root.name}: restored exec bit on {', '.join(fixed)}")
    return fixed


_EXT_INDEX_CACHE = {}   # (marker path, mtime_ns) -> parsed index, per process


def external_type_index(project_root):
    """simple name -> list of fully qualified names provided by dependency JARs.

    Built ONCE per build-manifest (cached at blackboard/external-index.json AND
    in-process: the 1.3 MB parse must not repeat per gate). Non-JVM stacks return
    {} (their gap strategies are import-path based and need no such blocklist).
    """
    import zipfile
    import hashlib
    project_root = pathlib.Path(project_root)
    marker = next((project_root / m for m in stacks.JAVA_MARKERS
                   if (project_root / m).is_file()), None)
    if marker is None:
        return {}
    try:
        stamp_mtime = marker.stat().st_mtime_ns
    except OSError:
        return {}
    cache_hit = _EXT_INDEX_CACHE.get((str(marker), stamp_mtime))
    if cache_hit is not None:
        return cache_hit
    cache = settings.BLACKBOARD / "external-index.json"
    stamp = hashlib.sha1(marker.read_bytes()).hexdigest()
    if cache.is_file():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cached.get("stamp") == stamp:
                index = cached.get("index") or {}
                _EXT_INDEX_CACHE[(str(marker), stamp_mtime)] = index
                return index
        except (OSError, json.JSONDecodeError):
            pass
    cp_file = pathlib.Path("/tmp/opencode") / f"cp-{stamp}.txt"
    if not cp_file.is_file():
        runner = stacks.classpath_probe_runner(project_root)
        try:
            subprocess.run(runner + ["-q", "dependency:build-classpath",
                                     f"-Dmdep.outputFile={cp_file}"],
                           cwd=str(project_root), stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            return {}
    if not cp_file.is_file():
        return {}
    index = {}
    for entry in cp_file.read_text().split(":"):
        if not entry.endswith(".jar") or not pathlib.Path(entry).is_file():
            continue
        try:
            with zipfile.ZipFile(entry) as zf:
                for name in zf.namelist():
                    if not name.endswith(".class") or "/" not in name:
                        continue
                    if "$" in name or name.startswith("META-INF") or name == "module-info.class":
                        continue
                    fq = name[:-len(".class")].replace("/", ".")
                    simple = fq.rsplit(".", 1)[-1]
                    index.setdefault(simple, set()).add(fq)
        except (OSError, zipfile.BadZipFile):
            continue
    index = {k: sorted(v) for k, v in index.items() if k[:1].isupper()}
    try:
        _atomic_write(cache, json.dumps({"stamp": stamp, "index": index}))
    except OSError:
        pass
    _EXT_INDEX_CACHE[(str(marker), stamp_mtime)] = index
    return index


def command_from_test_path(test_path, project_root):
    """The scoped test-command shapes the tester skills produce, from a test file path
    alone (None when no shape fits). Shared by green-gate synthesis and the
    deterministic red recovery: the ONE toolchain registry (stacks.ROWS) knows every
    shape, nothing guesses twice."""
    return stacks.scoped_test_command(test_path, project_root)


def _synthesized_command(task, record):
    """Legacy red-phase records predate command capture: rebuild the scoped command
    from the stage-1 task path via `command_from_test_path` - ONE shape table for
    every language. (The old inline chain stripped only the `.java` suffix from the
    stem, so a Kotlin/TS/Go/Python twin produced `AccountStateTest.kt` as a selector
    and duplicated build-file detection the table already owns.)"""
    if isinstance(record, dict):
        command = record.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
    import task_queue
    index = task_queue.load_index()
    root = workspace.project_root_for(task["project"])
    for dep in task.get("dependsOn", []):
        t1 = index.get(dep)
        if t1 and str(dep).startswith("T1-") and isinstance(t1.get("path"), str):
            command = command_from_test_path(t1["path"], root)
            if command:
                return command
    return None


def _fingerprint(task):
    """Cheap identity of everything the recorded test depends on: payload, main tree, test tree."""
    payload = settings.ROOT / "blackboard" / "coder-changes" / f"{task['id']}.json"
    root = workspace.project_root_for(task["project"])
    def tree_sig(folder):
        files = source_files(folder)
        return [len(files), max((f.stat().st_mtime_ns for f in files), default=0)]
    return json.dumps({
        # Bumping this forces ONE rebuild after feedback-tool semantics change (e.g. the
        # run-test-tool assertion-message upgrade; v4: normalized member_demands; v5:
        # member_demands widened to `location: variable ... of type T` receivers and
        # nested-type `class` symbols, so a verdict cached before the field exists or in
        # its narrower first shape cannot be mistaken for "no demands"). Without it the
        # memo serves stale logs to retrying coders forever, silently defeating the
        # upgrade. v6: problem_kinds joined the verdict schema (kind-driven attribution
        # must never replay a pre-kind verdict). v7: bean_demands joined (a context-boot
        # deferral must not replay a verdict that never carried the demand). v3: content
        # fingerprint + wave verdicts (per-file list, not global max-mtime). v9:
        # excerpt_all joined (attribution must see the FULL blame evidence; a verdict
        # cached before the field exists would keep the filtered digest's blind charge).
        # v10: parse_counts aggregates per-class surefire lines - the first-match form
        # hid a failing class's errors behind an innocent class's zero-count line.
        # v11: member_demands widened to `variable` (the enum-constant gap: only when the
        # located class is NOT the failing file's own type) and nested owners kept as
        # `OUTER.Inner`; engine attribution and the classpath-hole classification changed
        # with it - every memoized verdict computed under the old evidence view is stale.
        "memo_version": 11,
        "payload": payload.stat().st_mtime_ns if payload.is_file() else 0,
        "tree": _tree_fingerprint(root),
    }, sort_keys=True)


def _read_memo(task):
    path = settings.GATE_CACHE_DIR / f"{task['id']}.json"
    if not path.is_file():
        return None
    try:
        memo = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not (isinstance(memo, dict) and memo.get("fingerprint") == _fingerprint(task)):
        return None
    # O1: a verdict recorded before the current schema is not a fact about the
    # CURRENT engine's fields - drop it; the re-run costs a build, never a session
    if isinstance(memo.get("result"), dict) and not verdict_is_typed(memo["result"]):
        return None
    return memo


def last_adjudicated(task):
    """The unit's most recent FRESH gate verdict ({'reason','result'}), or None.

    The drain consults this at quarantine time to decide whether the failing unit's
    payload is proven harmless to the shared tree (see tdd_engine): the value must
    come from the CURRENT tree bytes, so a stale memo returns None - reverting is
    then the safe default.
    """
    return _read_memo(task)


def _atomic_write(path, text):
    """Write-then-rename: a SIGTERM between bytes can only leave the COMPLETE old
    file or the COMPLETE new one (2026-11-25 review: direct write_text in the cache
    writers is the same crash class _fork_boot_corruption heals FOR THE TREE - a
    truncated JSON gate cache poisons every later read until manual archaeology)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)   # os.replace under the hood: atomic on the same filesystem


def _write_memo(task, reason, result):
    settings.GATE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    memo = {"fingerprint": _fingerprint(task), "reason": reason,
            "result": result if isinstance(result, dict) else None}
    _atomic_write(settings.GATE_CACHE_DIR / f"{task['id']}.json",
                  json.dumps(memo, ensure_ascii=False) + "\n")


_FP_CACHE = {}      # str(root) -> (stat-signature, content-fingerprint)


def read_memo(task):
    """Public: the unit's memoized gate verdict if it still matches its fingerprint."""
    return _read_memo(task)


def verdict_tree_stale(task):
    """True when the unit's last recorded verdict no longer describes the current TREE.

    Compares only the tree component: quarantine discards the payload, which would make
    the full fingerprint (and thus `read_memo`) permanently stale for restored units -
    the world-moved question is strictly about the source tree.
    """
    path = settings.GATE_CACHE_DIR / f"{task['id']}.json"
    if not path.is_file():
        return True
    try:
        memo = json.loads(path.read_text(encoding="utf-8"))
        recorded = json.loads(memo.get("fingerprint") or "{}").get("tree")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return True
    if not recorded:
        return True
    root = workspace.project_root_for(task.get("project", ""))
    return recorded != _tree_fingerprint(root)


def _tree_fingerprint(project_root):
    """Content identity of everything a module-wide build compiles.

    SHA-1 of the file BYTES (not mtimes: an mtime signature invalidates on every touch,
    including byte-identical restore-then-reweave, which turned the wave cache back into
    a full rebuild per unit). Two tiers so callers may hammer it every attempt: a cheap
    stat signature (path,size,mtime_ns) guards an in-process cache of the expensive
    byte-hash. Toolchain-neutral - any source suffix the runner understands.
    """
    import hashlib
    root = pathlib.Path(project_root)
    files = sorted(fingerprint_files(root), key=lambda p: str(p))
    sig = []
    for f in files:
        try:
            st = f.stat()
            sig.append((str(f), st.st_size, st.st_mtime_ns))
        except OSError:
            sig.append((str(f), -1, 0))
    key = str(root)
    cached = _FP_CACHE.get(key)
    if cached and cached[0] == sig:
        return cached[1]
    digest = hashlib.sha1()
    for f, size, _ in sig:
        digest.update(str(f).encode("utf-8", "ignore"))
        digest.update(b"\0")
        if size < 0:
            digest.update(b"unreadable")
            continue
        try:
            digest.update(hashlib.sha1(pathlib.Path(f).read_bytes()).digest())
        except OSError:
            digest.update(b"unreadable")
    fp = digest.hexdigest()[:16]
    _FP_CACHE[key] = (sig, fp)
    return fp


def _compile_probe_command(suite_command):
    """A cheap compile-only shape of the suite command, when one exists per toolchain.

    While the module does not compile, every unit's wave verdict is the same compile
    error - learning it must not cost a whole test-suite boot (surefire, Spring
    contexts). The probe mirrors `_suite_command`'s recognized shapes; anything else
    returns None and the caller pays the full suite, as before.
    """
    toks = str(suite_command or "").split()
    if not toks:
        return None
    if "./mvnw" in suite_command or " mvn " in f" {suite_command} ":
        new = ["test-compile" if t == "test" else t for t in toks]
        for i, tok in enumerate(new):
            if tok.endswith("mvnw") or tok.endswith("mvn"):
                new.insert(i + 1, "-q")
                break
        return " ".join(new)
    if toks[:2] == ["go", "test"]:
        return " ".join(["go", "vet"] + toks[2:])
    if toks[:2] == ["npx", "jest"]:
        return "npx tsc --noEmit"
    if toks[:3] == ["python3", "-m", "pytest"]:
        return " ".join(["python3", "-m", "pytest", "--collect-only", "-q"] + toks[3:])
    return None


def _suite_command(command):
    """Generalize a unit's recorded scoped test command to the whole-suite command.

    Mirrors exactly the shapes `_synthesized_command` (and the tester skills) produce:
    maven `-Dtest=X`, go `-run X`, `npx jest <pattern>`, `python3 -m pytest <path>::...`.
    Anything unrecognized returns None: the caller keeps the per-unit scoped run, so
    an unsupported stack degrades to today's behavior, never to a wrong verdict.
    """
    toks = str(command or "").split()
    if not toks:
        return None
    if any(t.startswith("-Dtest=") for t in toks):
        rest = [t for t in toks if not t.startswith("-Dtest=")]
        return " ".join(rest) if "test" in rest else None
    if "-run" in toks:
        i = toks.index("-run")
        rest = toks[:i] + toks[i + 2:]
        return " ".join(rest) if rest else None
    if toks[:2] == ["npx", "jest"]:
        return " ".join(toks[:2] + [t for t in toks[2:] if t.startswith("-")])
    if toks[:3] == ["python3", "-m", "pytest"]:
        folder = next((t.split("::")[0].rsplit("/", 1)[0] for t in toks[3:] if not t.startswith("-")), "")
        return " ".join(toks[:3] + [folder or "tests"] + [t for t in toks[3:] if t.startswith("-")])
    return None


def _ident_tail(name):
    """Simple-name tail of ANY identifier shape: path, FQCN, file://basename.

    Extension order matters: `pricing.spec.ts` -> `pricing` (file), while
    `com.x.FooTest` -> `FooTest` (package tail). Splitting on "." naively turns
    both into the file extension and silently breaks selector matching.
    """
    s = str(name).replace("\\", "/").rsplit("/", 1)[-1]
    s = re.sub(r"\.(spec|test)\.[cm]?[jt]sx?$", "", s)
    s = re.sub(r"\.(py|go|java|kt|kts|scala|groovy|js|jsx|mjs|cjs|ts|tsx|rs|rb)$", "", s)
    if "." in s:
        s = s.rsplit(".", 1)[-1]
    return s


def _tool_result(root, command, timeout):
    tool_command = [sys.executable, str(settings.RUN_TEST_TOOL), "--cwd", str(root),
                    "--cmd", command, "--timeout", str(timeout)]
    completed = subprocess.run(tool_command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=timeout + 30,
                               cwd=str(settings.ROOT))
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _tree_wide_failure(data) -> bool:
    """Is this module build's verdict a fact about the TREE, not about any one class?

    A decisive non-pass status with zero per-class evidence - compile output, surefire
    boot crash, toolchain error before any test ran - does not vary with `-Dtest` scope:
    every unit's own scoped build re-derives byte-identical output. Those verdicts are
    shared across the wave; statuses WITH class evidence (assertion_failure/passed) keep
    their per-class routing. Toolchain-neutral: speaks only the runner's status contract.
    """
    if not isinstance(data, dict) or data.get("classes"):
        return False
    return data.get("status") in ("compile_error", "error")


# The wave verdict cache's grammar version. It must move WITH the run-test-tool
# normalization: a wave stored under the old parser carries verdicts WITHOUT the
# member_demands the new attribution requires, and `_shared_verdict` replays them to
# every unit of the tree - all evidence present, zero charges, mutual deferral forever
# (2026-11-18 live: memo_version moved to 11 and the per-unit memos refreshed, but the
# v9 wave kept serving the pre-demand verdict and the drain stayed at processed 0).
# v10: variable demands + OUTER.Inner owners joined the evidence (see memo_version v11).
WAVE_GRAMMAR = "v10"


def _shared_verdict(data, task):
    """The wave's decisive failure as any unit's own gate verdict: the same fields it
    would have seen in its own (byte-identical) scoped build."""
    shared = {k: data.get(k) for k in ("status", "exit_code", "missing_symbols",
                                       "missing_packages", "failures", "counts",
                                       "excerpt", "member_demands", "problem_kinds",
                                       "bean_demands", "blamed_files", "verdict_version",
                                       "package_symbol_demands", "mock_impossible", "stack_files")}
    shared = {k: v for k, v in shared.items() if v is not None}
    return f"test gate: {_failure_detail(shared, task)}", shared


def _write_wave(data, stamp):
    data["_stamp"] = stamp
    settings.GATE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wave_files = sorted(settings.GATE_CACHE_DIR.glob("wave-*.json"), key=lambda f: f.stat().st_mtime)
    for stale in wave_files[:-5]:
        stale.unlink(missing_ok=True)
    _atomic_write(settings.GATE_CACHE_DIR / f"wave-{stamp}.json", json.dumps(data))


def _run_suite_once(root, suite_command, stamp):
    """Cheap compile probe first: while the module does not compile, every unit's
    verdict is the SAME compile error, and a `test-compile`/`tsc`/`collect-only`
    probe says it in a fraction of a full-suite boot. Only a module that COMPILES
    earns the expensive per-class verdicts."""
    probe = _compile_probe_command(suite_command)
    if probe:
        print(f"[gate ] wave compile probe: {probe}")
        try:
            data = _tool_result(root, probe, settings.TEST_GATE_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired):
            data = None
        # A decisive probe verdict (compile error OR toolchain failure before any test
        # class ran) is the whole module's answer: booting the suite to rediscover the
        # identical failure would burn a second full build per tree state.
        if _tree_wide_failure(data):
            _write_wave(data, stamp)
            return data
    print(f"[gate ] wave build for {root.name}: {suite_command}")
    data = _tool_result(root, suite_command, settings.WAVE_GATE_TIMEOUT)
    if not isinstance(data, dict):
        return None
    _write_wave(data, stamp)
    return data


def _wave_is_current(data):
    """O1: the same version door the memo uses, for the shared wave cache."""
    return isinstance(data, dict) and verdict_is_typed(data)


def wave_gate_verdict(task, command):
    """(reason, result) from ONE module-wide build shared by every unit's green gate,
    or None to fall back to the per-unit scoped run.

    Surefire/pytest/jest go compile the WHOLE module, so N scoped runs prove nothing
    more than one suite run + per-class verdicts (which run-test-tool parses into
    result["classes"]; this engine layer never looks at toolchain syntax). Verdicts are
    cached per content fingerprint of the trees: a sibling re-weave costs exactly one
    rebuild that refreshes every unit at once. Decisive tree-wide failures (compile
    errors, toolchain boots that die before any class runs) are shared verbatim -
    every unit would see the same failure in its own build.
    """
    if task.get("stage") != settings.TDD_STAGE:
        return None
    root = workspace.project_root_for(task["project"])
    fp = _tree_fingerprint(root)
    stamp = f"{task['project']}-{WAVE_GRAMMAR}-{fp}"
    cache_file = settings.GATE_CACHE_DIR / f"wave-{stamp}.json"
    data = None
    if cache_file.is_file():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        # O1: a wave written before the current verdict schema is not evidence the
        # current engine can read - drop it; the rebuild costs a compile, no session
        if data is not None and not _wave_is_current(data):
            data = None
    # A cached tree-wide failure serves EVERY unit regardless of how the unit's own
    # command is shaped: the fact is about the tree, not the selector. (This is also
    # where a scoped fallback that primed its decisive verdict gets reused for free.)
    if data is not None and _tree_wide_failure(data):
        if data.get("status") == "error" and not (data.get("counts") or {}).get("run") \
                and _fork_boot_corruption(root):
            cache_file.unlink(missing_ok=True)
            # corrupted fork boot is not a tree fact: drop the cached wave and fall to
            # the scoped per-unit gate, which wipes the build output and re-runs as a
            # zero-session repair (green_test_result) instead of laundering one killed
            # build into every unit's verdict - and do NOT rebuild the suite HERE on
            # the still-corrupted output; the scoped path heals first.
            return None
        return _shared_verdict(data, task)
    suite = _suite_command(command)
    if not suite:
        return None
    if data is None or not _wave_is_current(data):
        try:
            data = _run_suite_once(root, suite, stamp)
        except (OSError, subprocess.TimeoutExpired) as exc:
            # NOT a fact about the tree - the toolchain could not run HERE. Returning a
            # not_run verdict would hand green_test_result a memoizable environmental
            # phantom (a wave primed under a wrong cwd replays forever as "cached
            # verdict"); fall to the unit's own scoped gate path instead, where a
            # persistent environment fault aborts loudly through the EXEC_ERROR contract.
            print(f"[gate ] {task['id']} wave build could not run: {str(exc)[:120]}")
            return None
    if not isinstance(data, dict) or data.get("status") == "not_run":
        return None
    if data.get("status") == "error" and not (data.get("counts") or {}).get("run") \
            and _fork_boot_corruption(root):
        # fresh suite run died at fork boot on a corrupted output: same refusal as the
        # cached door - the scoped gate heals (wipe + rerun) before any unit sees a verdict
        return None
    if _tree_wide_failure(data):
        return _shared_verdict(data, task)
    classes = data.get("classes") or {}
    if not classes:
        return None
    # O2 (2026-11-25): the selector->class join is FRAMEWORK GRAMMAR and lives in the
    # tool - unit_match names the one key the scoped command selected, or none. The
    # engine no longer fuzzy-matches stems: ambiguity falls to the unit's own scoped
    # build (costs a compile, never a wrong attribution).
    match = data.get("unit_match") or {}
    key = str(match.get("class_key") or "")
    if key not in classes:
        return None
    if classes[key] == "passed":
        counts = data.get("counts") or {}
        print(f"[gate ] {task['id']} wave verdict: green ({key})")
        return None, {"status": "passed", "counts": counts}
    unit_failures = [f for f in (data.get("failures") or [])
                     if isinstance(f, dict) and (str(f.get("class") or "") == key
                     or (not f.get("class") and str(f.get("test") or "").startswith(key + ".")))]
    digest = str((data.get("unit_match") or {}).get("selector") or key)
    excerpt = [line for line in (data.get("excerpt") or []) if digest.lower() in str(line).lower()]
    shared = {"status": "assertion_failure", "exit_code": data.get("exit_code", 1),
              "failures": unit_failures or [{"test": key, "message": ""}],
              "counts": data.get("counts") or {}, "missing_symbols": [], "missing_packages": []}
    # Attribution reads the FULL tree evidence; the selector-filtered excerpt is only the
    # coder-facing digest. Dropping main-file blame lines here used to blind
    # _blocked_by_peers into charging a demand-owner for a peer file's compile error
    # (seed-002 rerun 14:03: T2-017 billed 3 attempts for the wiring unit's call site).
    if data.get("excerpt"):
        shared["excerpt_all"] = data["excerpt"]
    # attribution fields ride along when the wave run produced them: the engine's
    # deferral decisions read ONLY these normalized fields (the tool owns syntax).
    for field in ("bean_demands", "member_demands", "problem_kinds",
                  "blamed_files", "package_symbol_demands", "mock_impossible",
                  "stack_files", "unit_match"):
        if data.get(field):
            shared[field] = data[field]
    if excerpt:
        shared["excerpt"] = excerpt
    print(f"[gate ] {task['id']} wave verdict: red ({key})")
    return f"test gate: {_failure_detail(shared, task)}", shared


_CORRUPT_FORK_MARKS = ("Truncated class file", "Error while running fork",
                       "The forked VM terminated without properly saying goodbye")


# Regenerable build-output directories a killed build can leave half-written. The
# NAMES are toolchain facts; the table lives in ONE place and only ever drives
# DELETE-AND-REBUILD of derived output - a source directory can never appear here
# because healing refuses paths the fingerprint set would treat as tree facts.
_BUILD_OUTPUT_DIRS = ("target", "build", "out")   # maven, gradle, generic


def _fork_boot_corruption(project_root):
    """True when a KILLED build left poisoned derived output the next build will inhale.

    A build interrupted mid-write leaves a half-written artifact - a .class under
    target/ that kills every forked test JVM at CLASS LOADING (Maven/Surefire), the
    same crash in Gradle's build/test-results dumps, or a truncated TypeScript
    incremental cache (.tsbuildinfo) that makes tsc die before running anything
    (2026-11-25 review: the recovery existed only for Surefire dumpstreams, so a
    SIGTERM inside a Gradle or tsc build became everybody's phantom defect). Every
    shape is TOOLING evidence, not a unit defect: status=error with zero tests run
    plus this probe means heal free by wiping the derived output and re-running -
    charging it to units (or memoizing it as a tree-wide fact) converts one killed
    build into a whole board of false identical failures (live 2026-11-18).
    """
    root = pathlib.Path(project_root)
    for pattern in ("target/surefire-reports/**/*.dumpstream",
                    "build/test-results/**/*.dumpstream"):
        try:
            dumps = sorted(root.glob(pattern), key=lambda f: f.stat().st_mtime_ns)[-2:]
        except OSError:
            continue
        if any(mark in f.read_text(encoding="utf-8", errors="ignore")
               for f in dumps for mark in _CORRUPT_FORK_MARKS):
            return True
    # TypeScript's incremental cache is JSON; a kill mid-write truncates it and tsc
    # then errors at READ time, before any test exists. Unparsable = poisoned.
    for info in _pruned_files(root, ".tsbuildinfo"):
        try:
            json.loads(info.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError):
            return True
    return False


def _pruned_files(root, suffix):
    """Files under root with `suffix`, skipping build/dependency folders."""
    out = []
    for dirpath, dirnames, filenames in __import__("os").walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        out.extend(pathlib.Path(dirpath, fn) for fn in filenames if fn.endswith(suffix))
    return sorted(out)


def heal_interrupted_build(project_root):
    """Delete the poisoned derived output a killed build left behind (the ONE place
    the engine wipes build directories); returns the names/paths healed. Source
    bytes are never touched - this is cache surgery, fingerprint-invisible."""
    root = pathlib.Path(project_root)
    healed = []
    for name in _BUILD_OUTPUT_DIRS:
        d = root / name
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            healed.append(name)
    for info in _pruned_files(root, ".tsbuildinfo"):
        try:
            info.unlink()
            healed.append(info.name)
        except OSError:
            pass
    return healed


def green_test_result(task):
    """Run the recorded test; return (reason_or_None, tool_result_or_None).

    Skips quietly (None, None) when the red-phase record holds no command: older
    records predate command capture and the build gate still applies.
    """
    record = red_phase_record(task)
    command = _synthesized_command(task, record)
    if not command:
        print(f"[test] {task['id']} no recorded or derivable test command; green test gate skipped")
        return None, None

    tool_command = [
        sys.executable, str(settings.RUN_TEST_TOOL),
        "--cwd", str(workspace.project_root_for(task["project"])),
        "--cmd", command,
        "--timeout", str(settings.TEST_GATE_TIMEOUT),
    ]
    fixed = canonicalize_tree(workspace.project_root_for(task["project"]))
    if fixed:
        print(f"[test] {task['id']} repaired missing imports in {fixed} test file(s)")
    memo = _read_memo(task)
    if memo is not None:
        print(f"[test] {task['id']} cached verdict (tree unchanged)")
        return memo.get("reason"), memo.get("result")
    wave = wave_gate_verdict(task, command)
    if wave is not None:
        _write_memo(task, wave[0], wave[1])
        return wave
    print(f"[test] {task['id']} re-running recorded test: {command}")
    with telemetry.span("blackboard.test_gate", {"task": task["id"]}) as current:
        try:
            completed = subprocess.run(
                tool_command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=settings.TEST_GATE_TIMEOUT + 30,
                cwd=str(settings.ROOT),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            reason = f"test gate could not run: {exc}"
            telemetry.mark_error(current, reason)
            print(f"[test] {task['id']} {reason}")
            return reason, None
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            reason = f"test gate produced unparseable output: {completed.stdout.strip()[:400]}"
            telemetry.mark_error(current, reason)
            print(f"[test] {task['id']} gate output is not JSON")
            return reason, None
        if not isinstance(result, dict):
            return f"test gate produced unexpected output: {str(result)[:400]}", None
        if (result.get("status") == "error" and not (result.get("counts") or {}).get("run")
                and _fork_boot_corruption(workspace.project_root_for(task["project"]))):
            # The empty fork is a tooling wound, not a verdict: heal it BEFORE memo, wave
            # publish or ledger signature can launder it into a tree-wide fact.
            print(f"[test] {task['id']} fork boot dies on corrupted build output: "
                  "wiping target/build derived output and re-running the gate once "
                  "(zero-session repair)")
            heal_interrupted_build(workspace.project_root_for(task["project"]))
            try:
                completed = subprocess.run(
                    tool_command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True,
                    timeout=settings.TEST_GATE_TIMEOUT + 30, cwd=str(settings.ROOT))
                rerun = json.loads(completed.stdout)
                if isinstance(rerun, dict):
                    result = rerun
            except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
                pass
        if result.get("status") == "passed":
            counts = result.get("counts") or {}
            print(f"[test] {task['id']} green ({counts.get('run', '?')} tests passed)")
            _write_memo(task, None, result)
            return None, result
        if _tree_wide_failure(result):
            # This scoped build just proved a tree-wide verdict: publish it to the wave
            # cache so every sibling unit at this fingerprint shares it for free instead
            # of re-deriving byte-identical output with its own full build.
            root = workspace.project_root_for(task["project"])
            _write_wave(result, f"{task['project']}-{WAVE_GRAMMAR}-{_tree_fingerprint(root)}")
        reason = f"test gate: {_failure_detail(result, task)}"
        telemetry.mark_error(current, reason)
        print(f"[test] {task['id']} {reason}")
        if result.get("status") != "not_run":
            _write_memo(task, reason, result)
        return reason, result
