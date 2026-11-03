#!/usr/bin/env python3
"""AST dispatcher: selects and runs the AST executable for a project.

Called by the orchestrator right after agent-tester reports that its job is done.

Usage:
  python3 .opencode/skills/ast-dispatcher/ast-dispatcher.py --root <project_root> --task-id <id> \
      [--tool-root <ast_tool_dir_or_jar>] [--language <name>] [--framework <name>] \
      [--timeout <seconds>] [--builders-dir <dir>] [--list-builders]

Flow:
  1. Load every builder module in builders/ at runtime (Strategy + Registry).
  2. Select the builder whose detect() matches the project, or the --language override.
  3. Merge the task context from <root>/blackboard/queue/<id>.json (target class,
     key "export") and <root>/blackboard/red-phase/<id>.json (target method).
  4. Ask the builder for the command, run it, write blackboard/ast-context/<id>.json
     with "executed": true, and print the run summary as JSON to stdout.

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


def discover_builders(directory: Path) -> list[AstBuilder]:
    """Load each builder module in the folder at runtime; each module exposes BUILDER."""
    builders = []
    for path in sorted(directory.glob("*.py")):
        if path.stem.startswith("_") or path.stem in NON_BUILDER_MODULES:
            continue
        spec = importlib.util.spec_from_file_location(f"ast_builder_{path.stem}", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        builder = getattr(module, "BUILDER", None)
        if isinstance(builder, AstBuilder):
            builders.append(builder)
    return builders


class BuilderRegistry:
    """Registry of builders, keyed by language. Selection delegates detection to each strategy."""

    def __init__(self, builders: list[AstBuilder]):
        self._builders = builders

    def names(self) -> list[str]:
        return [builder.language for builder in self._builders]

    def by_language(self, language: str) -> AstBuilder | None:
        return next((b for b in self._builders if b.language == language), None)

    def select(self, root: Path, language: str | None, framework: str | None) -> tuple[AstBuilder | None, str | None]:
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


RE_METHOD_CALL = re.compile(r"\b([a-z][A-Za-z0-9_]*)\s*\(")


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _method_from_symbols(missing: list) -> str | None:
    """First missing symbol that looks like a method (lowerCamelCase), without parentheses."""
    for item in missing:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str) and name and name[0].islower():
            return name.split("(")[0].strip()
    return None


def _method_from_failures(failures: list) -> str | None:
    """Assertion failures: take the first method name called in the failure text or the item's method field."""
    for item in failures:
        if isinstance(item, dict):
            for key in ("method", "target_method", "name"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    return value.split("(")[0].strip()
            text = json.dumps(item)
        else:
            text = str(item)
        match = RE_METHOD_CALL.search(text)
        if match:
            return match.group(1)
    return None


def _target_method(red: dict, queue: dict) -> str | None:
    """Resolve the method: missing_symbols, then failures (assertion case), then queue intent."""
    method = _method_from_symbols(red.get("missing_symbols") or [])
    if method is None:
        method = _method_from_failures(red.get("failures") or [])
    if method is None:
        for key in ("target_method", "method"):
            value = queue.get(key)
            if isinstance(value, str) and value:
                method = value.split("(")[0].strip()
                break
    return method


def load_task_context(root: Path, task_id: str) -> dict:
    """Merge queue (target class) and red-phase (missing method) records for the task."""
    queue = _read_json(root / "blackboard" / "queue" / f"{task_id}.json")
    red = _read_json(root / "blackboard" / "red-phase" / f"{task_id}.json")
    target_class = queue.get("export") or queue.get("target_class") or red.get("target_class")
    return {
        "target_class": target_class,
        "target_method": _target_method(red, queue),
        "sources": {"queue": bool(queue), "red_phase": bool(red)},
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
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return path


def run(argv: list, cwd: Path, timeout: int) -> dict:
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
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
    task_id: str
    tool_root: Path | None
    language: str | None
    framework: str | None
    timeout: int
    builders_dir: Path


def dispatch(options: Options) -> dict:
    root, task_id = options.root, options.task_id
    registry = BuilderRegistry(discover_builders(options.builders_dir))
    result = {"task_id": task_id, "root": str(root)}

    builder, framework = registry.select(root, options.language, options.framework)
    if builder is None:
        result["status"] = "unsupported"
        result["reason"] = f"no builder matched; registered: {registry.names()}"
        return result
    result["language"] = builder.language
    result["framework"] = framework

    ctx = load_task_context(root, task_id)
    argv = builder.build(root, ctx, options.tool_root)
    if argv is None:
        result["status"] = "unsupported"
        result["reason"] = (
            f"{builder.language} builder produced no command "
            "(check --tool-root, executable, target_class and target_method)"
        )
        return result

    result["command"] = argv
    result.update(run(argv, root, options.timeout))
    result["context_file"] = str(write_ast_context(root, task_id, result))
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch the AST executable by language and framework.")
    parser.add_argument("--root", help="Project root directory")
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
        registry = BuilderRegistry(discover_builders(args.builders_dir))
        print(json.dumps({"builders": registry.names()}, indent=2))
        return 0

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"status": "error", "reason": f"root not found: {root}"}))
        return 2

    options = Options(
        root=root,
        task_id=args.task_id,
        tool_root=Path(args.tool_root).resolve() if args.tool_root else None,
        language=args.language,
        framework=args.framework,
        timeout=args.timeout,
        builders_dir=args.builders_dir.resolve(),
    )
    result = dispatch(options)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
