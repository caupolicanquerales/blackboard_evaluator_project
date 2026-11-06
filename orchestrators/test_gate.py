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

import settings
import telemetry
import workspace


JAVA_LANG_NAMES = {
    "String", "Integer", "Long", "Double", "Float", "Boolean", "Byte", "Short", "Character",
    "Object", "Class", "System", "Thread", "Runnable", "Iterable", "Exception", "RuntimeException",
    "Error", "Number", "Math", "Void", "StringBuilder", "StringBuffer", "Comparable", "Enum", "Record",
}


JDK_TYPES = {
    "UUID": "java.util", "List": "java.util", "Map": "java.util", "Set": "java.util",
    "Optional": "java.util", "Arrays": "java.util", "Collections": "java.util",
    "LocalDate": "java.time", "LocalDateTime": "java.time", "ZoneId": "java.time",
    "Instant": "java.time", "ChronoUnit": "java.time", "Duration": "java.time",
    "BigDecimal": "java.math", "Collectors": "java.util.stream", "Stream": "java.util.stream",
}


def repair_test_imports(project_root):
    """Deterministically add missing same-project imports to test files.

    Testers sometimes reference a production type that lives in another package
    without importing it; javac then reports the unit's own class as missing and
    no coder run can fix it. Adding an import never changes behavior: it only
    resolves a name the test already uses. Returns the number of files repaired.
    """
    main_root = project_root / "src" / "main" / "java"
    test_root = project_root / "src" / "test" / "java"
    if not main_root.is_dir() or not test_root.is_dir():
        return 0

    declared_main = {}
    for f in main_root.rglob("*.java"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        pkg = re.search(r"package ([\w.]+);", text)
        if not pkg:
            continue
        for name in re.findall(r"\b(?:class|interface|enum|record)\s+([A-Z]\w*)", text):
            declared_main.setdefault(name, set()).add(pkg.group(1))

    repaired = 0
    for tf in test_root.rglob("*.java"):
        src = tf.read_text(encoding="utf-8", errors="ignore")
        pkg_match = re.search(r"package ([\w.]+);", src)
        if not pkg_match:
            continue
        test_pkg = pkg_match.group(1)
        own_declared = set(re.findall(r"\b(?:class|interface|enum|record)\s+([A-Z]\w*)", src))
        imported_simple = set(re.findall(r"import (?:static )?[\w.]*?\.([A-Z]\w*);", src))
        additions = []
        for cls in sorted(set(re.findall(r"\b([A-Z]\w*)\b", src))):
            if cls in JAVA_LANG_NAMES or cls in imported_simple or cls in own_declared:
                continue
            packages = declared_main.get(cls)
            if not packages or len(packages) != 1:
                continue
            pkg = next(iter(packages))
            if pkg == test_pkg or f"import {pkg}.{cls};" in src:
                continue
            additions.append(f"import {pkg}.{cls};")
        for cls, jdk_pkg in JDK_TYPES.items():
            if cls in JAVA_LANG_NAMES or cls in imported_simple or cls in own_declared:
                continue
            if cls in declared_main:
                continue
            if re.search(r"\b" + cls + r"\b", src):
                additions.append(f"import {jdk_pkg}.{cls};")
        if additions:
            new_src = src.replace(pkg_match.group(0) + "\n", pkg_match.group(0) + "\n" + "\n".join(additions) + "\n", 1)
            tf.write_text(new_src, encoding="utf-8")
            repaired += 1
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


def _failure_detail(result):
    """Compact summary of a non-passing run-test-tool result, safe for retry feedback.

    Includes up to three javac BLAME blocks (file:[line,col], symbol, location): without
    them a coder re-emits an unchanged payload because it cannot see WHICH call on WHICH
    type failed - each blind re-emit costs a session plus a full module build.
    """
    counts = result.get("counts") or {}
    parts = [f"status={result.get('status')}", f"exit_code={result.get('exit_code')}"]
    if counts:
        parts.append(f"tests={counts.get('run', '?')} failures={counts.get('failures', 0)} errors={counts.get('errors', 0)}")
    missing = result.get("missing_symbols") or []
    if missing:
        parts.append("missing=" + ", ".join(str(item)[:80] for item in missing[:3]))
    blame = _blame_lines(result)
    if blame:
        parts.append("blame: " + " || ".join(blame))
    for failure in (result.get("failures") or [])[:2]:
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
FILE_REFERENCE_RE = re.compile(rf"([^\s:()\[\]]+\.{SOURCE_EXT})[\s\[\(:]+(\d+)\s*[,:]\s*(\d+)?")

# Phrases that mark a CASCADING error (a symbol missing because a FOREIGN file is broken),
# not a structural defect of the blamed file itself.
CASCADE_PHRASES = ("cannot find symbol", "undefined:", "is not defined", "cannot find name",
                   "no module named", "could not resolve", "not found", "unresolved reference",
                   "cannot resolve")

SOURCE_SUFFIXES = {".java", ".kt", ".kts", ".scala", ".groovy", ".ts", ".tsx", ".js", ".jsx",
                   ".mjs", ".cjs", ".go", ".py", ".rs", ".rb", ".php", ".c", ".h", ".cc",
                   ".cpp", ".hpp", ".cs", ".m", ".swift", ".vue", ".svelte"}


def error_locations(result, limit=8):
    """[(file basename, message tail)] for every source-file location in the excerpt."""
    found = []
    for line in (result.get("excerpt") or []):
        if len(found) >= limit:
            break
        text = str(line)
        for match in FILE_REFERENCE_RE.finditer(text):
            name = match.group(1).split("/")[-1].lstrip(".")
            tail = text[match.end():].replace("[ERROR]", "").strip().lstrip("]): ").strip()[:80]
            found.append((name, tail))
            break
    return found


def is_cascade(message):
    lowered = (message or "").lower()
    return any(phrase in lowered for phrase in CASCADE_PHRASES)


def source_files(folder):
    """Every source file under a folder, in any supported language (never build output)."""
    if not folder.is_dir():
        return []
    return [f for f in folder.rglob("*")
            if f.suffix in SOURCE_SUFFIXES and f.is_file()
            and not {".git", "target", "build", "dist", "node_modules", "__pycache__", ".venv", "venv"}
            & set(f.parts)]


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


def _synthesized_command(task, record):
    """Legacy red-phase records predate command capture: rebuild the scoped command
    from the stage-1 task path (`.../AccountStateTest.java` -> `./mvnw -Dtest=AccountStateTest test`)."""
    if isinstance(record, dict):
        command = record.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
    import task_queue
    index = task_queue.load_index()
    for dep in task.get("dependsOn", []):
        t1 = index.get(dep)
        if t1 and str(dep).startswith("T1-") and isinstance(t1.get("path"), str):
            stem = pathlib.Path(t1["path"]).name.removesuffix(".java")
            root = workspace.project_root_for(task["project"])
            if (root / "pom.xml").is_file():
                return f"./mvnw -Dtest={stem} test"
            if (root / "package.json").is_file():
                return f"npx jest {stem}"
            if (root / "go.mod").is_file():
                return f"go test -run {stem} ./..."
            return f"python3 -m pytest {t1['path']}"
    return None


def _fingerprint(task):
    """Cheap identity of everything the recorded test depends on: payload, main tree, test tree."""
    payload = settings.ROOT / "blackboard" / "coder-changes" / f"{task['id']}.json"
    root = workspace.project_root_for(task["project"])
    def tree_sig(folder):
        files = source_files(folder)
        return [len(files), max((f.stat().st_mtime_ns for f in files), default=0)]
    return json.dumps({
        "payload": payload.stat().st_mtime_ns if payload.is_file() else 0,
        "main": tree_sig(root / "src" / "main"),
        "test": tree_sig(root / "src" / "test"),
    }, sort_keys=True)


def _read_memo(task):
    path = settings.GATE_CACHE_DIR / f"{task['id']}.json"
    if not path.is_file():
        return None
    try:
        memo = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return memo if isinstance(memo, dict) and memo.get("fingerprint") == _fingerprint(task) else None


def _write_memo(task, reason, result):
    settings.GATE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    memo = {"fingerprint": _fingerprint(task), "reason": reason,
            "result": result if isinstance(result, dict) else None}
    (settings.GATE_CACHE_DIR / f"{task['id']}.json").write_text(
        json.dumps(memo, ensure_ascii=False) + "\n", encoding="utf-8")


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
    fixed = repair_test_imports(workspace.project_root_for(task["project"]))
    if fixed:
        print(f"[test] {task['id']} repaired missing imports in {fixed} test file(s)")
    memo = _read_memo(task)
    if memo is not None:
        print(f"[test] {task['id']} cached verdict (tree unchanged)")
        return memo.get("reason"), memo.get("result")
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
        if result.get("status") == "passed":
            counts = result.get("counts") or {}
            print(f"[test] {task['id']} green ({counts.get('run', '?')} tests passed)")
            _write_memo(task, None, result)
            return None, result
        reason = f"test gate: {_failure_detail(result)}"
        telemetry.mark_error(current, reason)
        print(f"[test] {task['id']} {reason}")
        _write_memo(task, reason, result)
        return reason, result
