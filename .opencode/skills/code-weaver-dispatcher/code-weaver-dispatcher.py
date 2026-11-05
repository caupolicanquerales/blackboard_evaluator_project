#!/usr/bin/env python3
"""Code-weaver dispatcher: selects and runs the weaver executable for a task.

Called by the orchestrator right after agent-coder reports that its job is done.

Usage:
  python3 .opencode/skills/code-weaver-dispatcher/code-weaver-dispatcher.py --root <blackboard_root> --task-id <id> \
      [--project-root <generated_project_root>] [--tool-root <weaver_dir_or_jar>] [--language <name>] \
      [--framework <name>] [--timeout <seconds>] [--builders-dir <dir>] [--list-builders]

Flow:
  1. Load every weaver builder module in builders/ at runtime (Strategy + Registry).
  2. Read and validate <root>/blackboard/coder-changes/<id>.json written by agent-coder.
  3. Select the builder by the payload "language" (or --language override),
     falling back to project detection.
  4. Ask the builder for the command, run it, write blackboard/weave-results/<id>.json
     with "executed": true, and print the run summary as JSON to stdout.

--root holds blackboard/; --project-root (default: same as --root) is where the
payload's targetFile is resolved and where the weaver executable is pointed at.

Exit codes: 0 weaved, 1 not weaved (unsupported/error), 2 invalid input.
Standard library only.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "builders"))
from base_weaver import CodeWeaver, load_project_env  # noqa: E402

load_project_env(Path(__file__))  # WEAVER_TOOL_ROOT and WEAVER_JAR_NAME come from the project .env

BUILDERS_DIR = Path(__file__).resolve().parent / "builders"
NON_BUILDER_MODULES = {"base_weaver"}
DEFAULT_TIMEOUT_SECONDS = 600
REQUIRED_STR_KEYS = ("targetFile", "export", "method", "body")


def discover_builders(directory: Path) -> tuple[list[CodeWeaver], list[str]]:
    """Load each builder module in the folder at runtime; each module exposes BUILDER.

    A module that fails to import is reported and skipped: one broken builder
    must not stop dispatch for the remaining languages.
    """
    builders, errors = [], []
    for path in sorted(directory.glob("*.py")):
        if path.stem.startswith("_") or path.stem in NON_BUILDER_MODULES:
            continue
        spec = importlib.util.spec_from_file_location(f"code_weaver_{path.stem}", path)
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
        if isinstance(builder, CodeWeaver):
            builders.append(builder)
        else:
            errors.append(f"{path.name}: no BUILDER instance of CodeWeaver")
    return builders, errors


class BuilderRegistry:
    """Registry of weaver builders, keyed by language. Selection delegates detection to each strategy."""

    def __init__(self, builders: list[CodeWeaver], errors: list[str] | None = None):
        self._builders = builders
        self.errors = errors or []

    @classmethod
    def load(cls, directory: Path) -> "BuilderRegistry":
        builders, errors = discover_builders(directory)
        return cls(builders, errors)

    def names(self) -> list[str]:
        return [builder.language for builder in self._builders]

    def by_language(self, language: str) -> CodeWeaver | None:
        return next((b for b in self._builders if b.language == language), None)

    def select(self, root: Path, language: str | None,
               framework: str | None) -> tuple[CodeWeaver | None, str | None]:
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


def load_coder_changes(root: Path, task_id: str) -> tuple[dict | None, str | None]:
    """Read and validate <root>/blackboard/coder-changes/<id>.json from agent-coder."""
    path = root / "blackboard" / "coder-changes" / f"{task_id}.json"
    if not path.is_file():
        return None, f"coder-changes file not found: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"coder-changes file unreadable: {exc}"
    if not isinstance(payload, dict) or not payload:
        return None, "coder-changes file is empty or not an object"
    missing = [key for key in REQUIRED_STR_KEYS
               if not isinstance(payload.get(key), str) or not payload[key].strip()]
    members = payload.get("members") or []
    if missing and not (missing == ["body"] and isinstance(members, list) and members):
        return None, f"coder-changes missing or empty keys: {missing}"
    if not isinstance(members, list):
        return None, "members must be an array of strings"
    return payload, None


def resolve_target_file(root: Path, changes: dict) -> tuple[Path | None, str | None]:
    """The target must stay inside the project root; missing files are created by the weaver."""
    target = (root / changes["targetFile"]).resolve()
    if not str(target).startswith(str(root)):
        return None, f"targetFile escapes project root: {changes['targetFile']}"
    if target.is_dir() or not target.suffix:
        return None, f"targetFile is not a source file path: {changes['targetFile']}"
    return target, None


def write_weave_result(root: Path, task_id: str, result: dict) -> Path:
    """Persist the weaver run to blackboard/weave-results/<id>.json with executed: true."""
    out_dir = root / "blackboard" / "weave-results"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{task_id}.json"
    payload = {
        "task_id": task_id,
        "status": result.get("status"),
        "target_file": result.get("target_file", ""),
        "language": result.get("language"),
        "framework": result.get("framework"),
        "command": result.get("command"),
        "exit_code": result.get("exit_code"),
        "stdout": (result.get("stdout") or "").strip(),
        "stderr": (result.get("stderr") or "").strip(),
        "reason": result.get("reason", ""),
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


def _cached_success(root: Path, task_id: str, project_root: Path, changes: dict,
                    changes_path: Path) -> dict | None:
    """Skip re-running the weaver when the last weave is still valid.

    Valid means: recorded status ok, target file present at the recorded path, and
    the payload has not been rewritten since the weave (coder retry bumps mtime and
    correctly forces a re-weave)."""
    result_file = root / "blackboard" / "weave-results" / f"{task_id}.json"
    payload_file = root / "blackboard" / "coder-changes" / f"{task_id}.json"
    if not result_file.is_file() or not payload_file.is_file():
        return None
    try:
        previous = json.loads(result_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(previous, dict) or previous.get("status") != "ok" or not previous.get("executed"):
        return None
    if payload_file.stat().st_mtime_ns > result_file.stat().st_mtime_ns:
        return None
    target = (project_root / changes["targetFile"]).resolve()
    if not target.is_file():
        return None
    recorded = previous.get("target_file")
    if recorded and recorded != str(target):
        return None
    return {"task_id": task_id, "root": str(root), "project_root": str(project_root),
            "target_file": str(target), "status": "ok", "exit_code": previous.get("exit_code"),
            "stdout": "(cached successful weave)", "stderr": "", "language": previous.get("language"),
            "framework": previous.get("framework"), "command": previous.get("command"),
            "_result_file": result_file}


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


def dispatch(options: Options) -> dict:
    root, project_root, task_id = options.root, options.project_root, options.task_id
    registry = BuilderRegistry.load(options.builders_dir)
    result = {"task_id": task_id, "root": str(root), "project_root": str(project_root)}
    if registry.errors:
        result["builder_errors"] = registry.errors

    changes, reason = load_coder_changes(root, task_id)
    if changes is None:
        result["status"] = "error"
        result["reason"] = reason
        return result

    target_file, reason = resolve_target_file(project_root, changes)
    if target_file is None:
        result["status"] = "error"
        result["reason"] = reason
        return result
    result["target_file"] = str(target_file)

    payload_language = changes.get("language")
    language = (options.language
                or (payload_language.strip().lower() if isinstance(payload_language, str) else None)
                or None)
    builder, framework = registry.select(project_root, language, options.framework)
    if builder is None:
        result["status"] = "unsupported"
        result["reason"] = (f"no builder matched language '{language}'; registered: {registry.names()}"
                            if language else f"no builder matched; registered: {registry.names()}")
        return result
    result["language"] = builder.language
    result["framework"] = framework

    changes_path = (root / "blackboard" / "coder-changes" / f"{task_id}.json").resolve()
    previous = _cached_success(root, task_id, project_root, changes, changes_path)
    if previous is not None:
        previous["result_file"] = str(previous.pop("_result_file"))
        return previous

    try:
        argv = builder.build(project_root, changes, changes_path, options.tool_root)
    except Exception as exc:  # noqa: BLE001
        result["status"] = "error"
        result["reason"] = f"{builder.language} builder crashed: {exc}"
        return result
    if argv is None:
        result["status"] = "unsupported"
        result["reason"] = (
            f"{builder.language} weaver produced no command "
            "(check --tool-root, weaver executable or $WEAVER_JAR_NAME)"
        )
        return result

    result["command"] = argv
    result.update(run(argv, project_root, options.timeout))
    result["result_file"] = str(write_weave_result(root, task_id, result))
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch the code-weaver executable by language and framework.")
    parser.add_argument("--root", help="Repository root holding blackboard/")
    parser.add_argument("--project-root", help="Generated project root (default: --root)")
    parser.add_argument("--task-id", help="Task id whose coder-changes payload must be woven")
    parser.add_argument("--tool-root", default=os.environ.get("WEAVER_TOOL_ROOT"),
                        help="Weaver tool directory or JAR (default: $WEAVER_TOOL_ROOT)")
    parser.add_argument("--language", help="Force a builder by language, skipping payload language and detection")
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
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
