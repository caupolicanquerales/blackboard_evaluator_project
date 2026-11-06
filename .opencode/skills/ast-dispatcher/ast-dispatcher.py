#!/usr/bin/env python3
"""AST dispatcher: selects and runs the AST executable for a project.

Called by the orchestrator right after agent-tester reports that its job is done.

Usage:
  python3 .opencode/skills/ast-dispatcher/ast-dispatcher.py --root <blackboard_root> --task-id <id> \
      [--project-root <generated_project_root>] [--tool-root <ast_tool_dir_or_jar>] [--language <name>] \
      [--framework <name>] [--timeout <seconds>] [--builders-dir <dir>] [--list-builders]

Flow:
  1. Load every builder module in builders/ at runtime (Strategy + Registry).
  2. Select the builder whose detect() matches the project, or the --language override.
  3. Merge the task context from <root>/blackboard/queue/<id>.json (target class,
     key "export") and <root>/blackboard/red-phase/<id>.json (target method).
  4. Ask the builder for the command, run it, write blackboard/ast-context/<id>.json
     with "executed": true, and print the run summary as JSON to stdout.

Exit codes: 0 executed, 1 not executed (unsupported/error), 2 invalid root.
Standard library only.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "builders"))
from base import AstBuilder, load_project_env  # noqa: E402

load_project_env(Path(__file__))  # AST_TOOL_ROOT and AST_JAR_NAME come from the project .env

BUILDERS_DIR = Path(__file__).resolve().parent / "builders"
NON_BUILDER_MODULES = {"base"}
DEFAULT_TIMEOUT_SECONDS = 600

# The tester names every test as `method_condition_expected` (java-junit5 skill).
RE_METHOD_CALL = re.compile(r"\b([a-z][A-Za-z0-9_]*)\s*\(")


def discover_builders(directory: Path) -> tuple[list[AstBuilder], list[str]]:
    """Load each builder module in the folder at runtime; each module exposes BUILDER.

    A module that fails to import is reported and skipped: one broken builder
    must not stop dispatch for the remaining languages.
    """
    builders, errors = [], []
    for path in sorted(directory.glob("*.py")):
        if path.stem.startswith("_") or path.stem in NON_BUILDER_MODULES:
            continue
        spec = importlib.util.spec_from_file_location(f"ast_builder_{path.stem}", path)
        if spec is None or spec.loader is None:
            errors.append(f"{path.name}: no importable module")
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")
            continue
        builder = getattr(module, "BUILDER", None)
        if isinstance(builder, AstBuilder):
            builders.append(builder)
        else:
            errors.append(f"{path.name}: no BUILDER instance of AstBuilder")
    return builders, errors


class BuilderRegistry:
    """Registry of builders, keyed by language. Selection delegates detection to each strategy."""

    def __init__(self, builders: list[AstBuilder], errors: list[str] | None = None):
        self._builders = builders
        self.errors = errors or []

    @classmethod
    def load(cls, directory: Path) -> "BuilderRegistry":
        builders, errors = discover_builders(directory)
        return cls(builders, errors)

    def names(self) -> list[str]:
        return [builder.language for builder in self._builders]

    def by_language(self, language: str) -> AstBuilder | None:
        return next((b for b in self._builders if b.language == language), None)

    def select(self, root: Path, language: str | None,
               framework: str | None) -> tuple[AstBuilder | None, str | None]:
        """Return (builder, framework). An explicit language skips detection."""
        if language:
            builder = self.by_language(language)
            if builder is None:
                return None, None
            return builder, framework or builder.detect(root) or "none"
        for builder in self._builders:
            detected = builder.detect(root)
            if detected:
                return builder, framework or detected
        return None, None


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _clean_name(value) -> str | None:
    """Normalize a possible method name: drop parameters and whitespace."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value.split("(")[0].strip() or None


def _method_from_symbols(missing: list) -> str | None:
    """First missing symbol that looks like a method (lowerCamelCase), without parentheses."""
    for item in missing:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str) and name and name[0].islower():
            cleaned = _clean_name(name)
            if cleaned:
                return cleaned
    return None


def _method_from_test_name(test: str) -> str | None:
    """Apply the tester naming convention: `method_condition_expected`, optionally class-qualified."""
    candidate = test.rsplit(".", 1)[-1].split("_", 1)[0].strip()
    return candidate if candidate and candidate[0].islower() else None


def _method_from_failures(failures: list) -> str | None:
    """First method hinted by a failure: explicit keys, the test-name convention, then call syntax."""
    for item in failures:
        if isinstance(item, dict):
            for key in ("method", "target_method", "name"):
                cleaned = _clean_name(item.get(key))
                if cleaned:
                    return cleaned
            test = item.get("test")
            if isinstance(test, str) and test.strip():
                cleaned = _method_from_test_name(test.strip())
                if cleaned:
                    return cleaned
            text = json.dumps(item)
        else:
            text = str(item)
        match = RE_METHOD_CALL.search(text)
        if match:
            return match.group(1)
    return None


def _method_from_queue(queue: dict) -> str | None:
    """Queue intent: the first ast_hints method signature, then the first tdd case method."""
    hints = queue.get("ast_hints") if isinstance(queue.get("ast_hints"), dict) else {}
    for entry in hints.get("methods") or []:
        if isinstance(entry, dict):
            signature = entry.get("signature")
            if isinstance(signature, str) and signature.strip():
                method = signature.split("(")[0].split()[-1].strip()
                if method:
                    return method
    tdd = queue.get("tdd") if isinstance(queue.get("tdd"), dict) else {}
    for case in tdd.get("cases") or []:
        if isinstance(case, dict):
            cleaned = _clean_name(case.get("method"))
            if cleaned:
                return cleaned
    return None


RE_TEST_METHOD = re.compile(r"\bvoid\s+([a-z][A-Za-z0-9_]*)\s*\(")
LIFECYCLE_HELPERS = {"setup", "teardown", "beforeeach", "aftereach", "init", "cleanup", "main"}


def _method_from_test_file(project_root: Path, queue: dict) -> str | None:
    """First method under test, from the tester's own naming convention.

    The tester names every case `method_condition_expected` (java-junit5 skill), so a
    red phase that only reports missing TYPES still says which production method the
    unit is about: only underscore-convention names qualify, and lifecycle helpers
    (setUp/tearDown) are never the unit. Only the unit's test file is read, never a
    sibling's.
    """
    relative = queue.get("path")
    if not isinstance(relative, str) or not relative.strip():
        return None
    test_file = project_root / relative
    if not test_file.is_file():
        return None
    names = [n for n in RE_TEST_METHOD.findall(_read_text(test_file))
             if n.split("_", 1)[0].strip().lower() not in LIFECYCLE_HELPERS]
    conventional = [n for n in names if "_" in n]
    for name in conventional or names:
        candidate = name.split("_", 1)[0].strip()
        if candidate and candidate[0].islower():
            return candidate
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _target_method(red: dict, queue: dict, project_root: Path | None = None,
                   test_task: dict | None = None) -> str | None:
    """Resolve the method: missing_symbols, then failures, then queue intent, then test name.

    The test-name fallback reads the tester's file, so it uses `test_task` (the stage-1
    record) rather than the production task whose `path` points at the code under build.
    """
    return (_method_from_symbols(red.get("missing_symbols") or [])
            or _method_from_failures(red.get("failures") or [])
            or _method_from_queue(queue)
            or _clean_name(queue.get("target_method") or queue.get("method"))
            or (_method_from_test_file(project_root, test_task or queue) if project_root else None))


def _task_files(root: Path) -> list[Path]:
    """Every task record: queue first, then complete and error."""
    return sorted((root / "blackboard" / "queue").glob("*.json")) \
        + sorted((root / "blackboard" / "complete").glob("T*.json")) \
        + sorted((root / "blackboard" / "error").glob("T*.json"))


def _producer_of(root: Path, tester_id: str) -> dict:
    """The stage-2 task that implements the unit tested by `tester_id`.

    A tester task exports the TEST class; the AST context the coder needs describes
    the production class, which is the export of the stage-2 task depending on it.
    """
    for file in _task_files(root):
        task = _read_json(file)
        if task.get("stage") == 2 and tester_id in (task.get("dependsOn") or []):
            return task
    return {}


def load_task_context(root: Path, task_id: str, project_root: Path | None = None) -> dict:
    """Merge queue (target class) and red-phase (missing method) records for the task.

    The queue file is normally still in blackboard/queue while agent-tester runs, but
    on a resume the tester task is already in blackboard/complete, so both are read.
    """
    queue = _read_json(root / "blackboard" / "queue" / f"{task_id}.json")
    if not queue:
        # Queue files carry the domain slug ("<id>-<project>.json"), and the dispatch runs
        # while the task is STILL in the queue: the slug-named fallback must cover queue too,
        # or stage-1 tasks resolve to {}, the producer lookup is skipped and no context lands.
        for folder in (root / "blackboard" / "queue", root / "blackboard" / "complete",
                       root / "blackboard" / "error"):
            for candidate in sorted(folder.glob(f"{task_id}-*.json")):
                queue = _read_json(candidate)
                if queue:
                    break
            if queue:
                break
    red = _read_json(root / "blackboard" / "red-phase" / f"{task_id}.json")
    producer = _producer_of(root, task_id) if queue.get("stage") == 1 else queue
    target_class = (producer.get("export") or producer.get("target_class")
                    or queue.get("export") or queue.get("target_class") or red.get("target_class"))
    return {
        "target_class": target_class,
        "target_method": _target_method(red, producer or queue, project_root, queue),
        "test_path": queue.get("path") if queue.get("stage") == 1 else None,
        "sources": {"queue": bool(queue), "red_phase": bool(red), "producer": bool(producer)},
    }


def write_ast_context(root: Path, task_id: str, result: dict) -> Path:
    """Persist the extractor output to blackboard/ast-context/<id>.json with executed: true."""
    out_dir = root / "blackboard" / "ast-context"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{task_id}.json"
    stdout = (result.get("stdout") or "").strip()
    try:
        extracted = json.loads(stdout) if stdout else None
    except json.JSONDecodeError:
        extracted = stdout
    payload = {
        "task_id": task_id,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "context": extracted,
        "stderr": result.get("stderr", ""),
        "executed": True,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def run(argv: list, cwd: Path, timeout: int) -> dict:
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except OSError as exc:
        return {"status": "error", "exit_code": None, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired:
        return {"status": "error", "exit_code": None, "stdout": "", "stderr": "timeout"}
    return {
        "status": "ok" if proc.returncode == 0 else "error",
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


@dataclass(frozen=True)
class Options:
    root: Path
    project_root: Path
    task_id: str
    tool_root: Path | None
    language: str | None
    framework: str | None
    timeout: int
    builders_dir: Path


def _apply_contract(result: dict, root: Path, task_id: str, ctx: dict, builder, reason: str) -> bool:
    """Write the test-derived contract into result + blackboard/ast-context; False if none exists.

    The test IS the executable specification when the extractor has nothing (or nothing
    valid) to read: each language builder reads its own syntax from it (the base offers a
    neutral fallback), so the stage-2 coder never codes from bare symbol names.
    """
    contract = builder.test_contract(Path(result["project_root"]), ctx)
    if contract is None:
        return False
    synth = {"status": "test_contract", "exit_code": 0,
             "stdout": json.dumps(contract, ensure_ascii=False), "stderr": ""}
    result["status"] = "test_contract"
    result["reason"] = reason
    result["context"] = contract
    result["context_file"] = str(write_ast_context(root, task_id, synth))
    return True


def dispatch(options: Options) -> dict:
    root, project_root, task_id = options.root, options.project_root, options.task_id
    registry = BuilderRegistry.load(options.builders_dir)
    result = {"task_id": task_id, "root": str(root), "project_root": str(project_root)}
    if registry.errors:
        result["builder_errors"] = registry.errors

    builder, framework = registry.select(project_root, options.language, options.framework)
    if builder is None:
        result["status"] = "unsupported"
        result["reason"] = f"no builder matched; registered: {registry.names()}"
        return result
    result["language"] = builder.language
    result["framework"] = framework

    ctx = load_task_context(root, task_id, project_root)
    try:
        argv = builder.build(project_root, ctx, options.tool_root)
    except Exception as exc:  # noqa: BLE001
        result["status"] = "error"
        result["reason"] = f"{builder.language} builder crashed: {exc}"
        return result
    if argv is None:
        detail = ""
        try:
            detail = builder.missing_command_reason(project_root, ctx, options.tool_root)
        except Exception:  # noqa: BLE001
            detail = ""
        if _apply_contract(result, root, task_id, ctx, builder,
                           "production class not written yet: contract extracted from the unit's own test "
                           f"({ctx.get('test_path')})"):
            return result
        result["status"] = "unsupported"
        result["context"] = None
        result["reason"] = (f"{builder.language} builder produced no command: "
                            f"{detail or 'no extractor inputs could be resolved'}")
        return result

    result["command"] = argv
    result.update(run(argv, project_root, options.timeout))
    if result.get("status") != "ok" and _apply_contract(
            result, root, task_id, ctx, builder,
            "extractor could not read the production source; contract extracted from the unit's own test "
            f"({ctx.get('test_path')}) instead"):
        return result
    result["context_file"] = str(write_ast_context(root, task_id, result))
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch the AST executable by language and framework.")
    parser.add_argument("--root", help="Repository root holding blackboard/")
    parser.add_argument("--project-root", help="Generated project root to scan (default: --root)")
    parser.add_argument("--task-id", help="Task name executed by agent-tester")
    parser.add_argument("--tool-root", default=os.environ.get("AST_TOOL_ROOT"),
                        help="AST tool directory or JAR (default: $AST_TOOL_ROOT)")
    parser.add_argument("--language", help="Force a builder by language, skipping detection")
    parser.add_argument("--framework", help="Override the detected framework")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Run timeout in seconds")
    parser.add_argument("--builders-dir", type=Path, default=BUILDERS_DIR, help="Folder with builder modules")
    parser.add_argument("--list-builders", action="store_true", help="Print registered builders and exit")
    args = parser.parse_args(argv)
    if not args.list_builders and (not args.root or not args.task_id):
        parser.error("--root and --task-id are required")
    return args


def main() -> int:
    args = parse_args()

    if args.list_builders:
        registry = BuilderRegistry.load(args.builders_dir.resolve())
        summary = {"builders": registry.names()}
        if registry.errors:
            summary["errors"] = registry.errors
        print(json.dumps(summary, indent=2))
        return 0

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"status": "error", "reason": f"root not found: {root}"}))
        return 2

    project_root = Path(args.project_root).resolve() if args.project_root else root
    if not project_root.is_dir():
        print(json.dumps({"status": "error", "reason": f"project root not found: {project_root}"}))
        return 2

    options = Options(
        root=root,
        project_root=project_root,
        task_id=args.task_id,
        tool_root=Path(args.tool_root).resolve() if args.tool_root else None,
        language=args.language,
        framework=args.framework,
        timeout=args.timeout,
        builders_dir=args.builders_dir.resolve(),
    )
    result = dispatch(options)
    print(json.dumps(result, indent=2))
    # "unsupported" means there is nothing to extract and no test to read either.
    # "test_contract" is the greenfield outcome: the contract landed in blackboard/ast-context,
    # derived mechanically from the unit's test. Both are informational, not dispatcher failures.
    return 0 if result.get("status") in ("ok", "unsupported", "test_contract") else 1


if __name__ == "__main__":
    sys.exit(main())
