#!/usr/bin/env python3
"""Validate and write the architect outputs into the blackboard.

Outputs:
- blackboard/execution-strategy.json  (command: strategy)
- blackboard/queue/T-xxx-<domain-slug>.json  (command: tasks)

The script is the only sanctioned writer for these files. Invalid payloads are
rejected, never repaired. Writes are atomic (temp file + os.replace) and
existing files are not overwritten unless --force is given.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_SOURCE = 2
EXIT_IO = 3

sys.dont_write_bytecode = True

DEFAULT_STRATEGY = "blackboard/complete/execution-strategy.json"
DEFAULT_TASKS_DIR = "blackboard/queue"

TASK_ID_PATTERN = re.compile(r"^T-\d{3}$")
TASK_KINDS = frozenset({"record", "class", "interface", "enum"})
TASK_LAYERS = frozenset(
    {
        "root",
        "domain",
        "application",
        "infrastructure",
        "interface",
        "presentation",
        "shared",
        "features",
    }
)

STRATEGY_KEYS = ("modules", "layers", "build_order", "risks")
STRATEGY_OPTIONAL_KEYS = ("persistence", "slug", "bounded_contexts", "module_layout")
MODULE_LAYOUT_KEYS = ("base_package", "packages", "integration")
TASK_KEYS = (
    "id",
    "depends_on",
    "path",
    "kind",
    "layer",
    "feature",
    "export",
    "intent",
    "ast_hints",
    "tdd",
    "acceptance",
)
AST_HINT_KEYS = ("package", "implements", "dependencies", "methods")
TDD_KEYS = ("test_path", "cases")
TDD_CASE_KEYS = ("method", "given", "when", "then")


def is_non_empty_str(value):
    return isinstance(value, str) and bool(value.strip())


def is_str_list(value):
    return isinstance(value, list) and all(is_non_empty_str(item) for item in value)


def check_exact_keys(payload, keys, label):
    if not isinstance(payload, dict):
        return f"{label} must be an object"
    missing = [key for key in keys if key not in payload]
    if missing:
        return f"{label} is missing key(s): {', '.join(missing)}"
    unexpected = sorted(set(payload) - set(keys))
    if unexpected:
        return f"{label} has unsupported key(s): {', '.join(unexpected)}"
    return None


def validate_relative_path(value, label):
    if not is_non_empty_str(value):
        return f"{label} must be a non-empty string"
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return f"{label} must be relative to the project root without '..' (got {value!r})"
    return None


def validate_strategy(payload):
    if not isinstance(payload, dict):
        return "strategy must be an object"
    missing = [key for key in STRATEGY_KEYS if key not in payload]
    if missing:
        return f"strategy is missing key(s): {', '.join(missing)}"
    unexpected = sorted(set(payload) - set(STRATEGY_KEYS) - set(STRATEGY_OPTIONAL_KEYS))
    if unexpected:
        return f"strategy has unsupported key(s): {', '.join(unexpected)}"
    for key in ("modules", "layers", "build_order", "risks"):
        if not is_str_list(payload[key]):
            return f"strategy.{key} must be a list of non-empty strings"
    if not payload["modules"]:
        return "strategy.modules must not be empty"
    if not payload["build_order"]:
        return "strategy.build_order must not be empty"
    if "slug" in payload and not is_non_empty_str(payload["slug"]):
        return "strategy.slug must be a non-empty string when present"
    if "bounded_contexts" in payload:
        if not is_str_list(payload["bounded_contexts"]) or not payload["bounded_contexts"]:
            return "strategy.bounded_contexts must be a non-empty list of non-empty strings"
    if "module_layout" in payload:
        layout = payload["module_layout"]
        reason = check_exact_keys(layout, MODULE_LAYOUT_KEYS, "strategy.module_layout")
        if reason:
            return reason
        if not is_non_empty_str(layout["base_package"]):
            return "strategy.module_layout.base_package must be a non-empty string"
        if not is_str_list(layout["packages"]) or not layout["packages"]:
            return "strategy.module_layout.packages must be a non-empty list of non-empty strings"
        if not is_non_empty_str(layout["integration"]):
            return "strategy.module_layout.integration must be a non-empty string"
    if "persistence" in payload:
        if not isinstance(payload["persistence"], dict) or not payload["persistence"]:
            return "strategy.persistence must be a non-empty object when present"
    return None


def validate_task(task, label):
    reason = check_exact_keys(task, TASK_KEYS, label)
    if reason:
        return reason
    if not (isinstance(task["id"], str) and TASK_ID_PATTERN.match(task["id"])):
        return f"{label}.id must match T-### (got {task['id']!r})"
    if not is_str_list(task["depends_on"]):
        return f"{label}.depends_on must be a list of task IDs"
    if task["id"] in task["depends_on"]:
        return f"{label}.depends_on must not contain its own id"
    reason = validate_relative_path(task["path"], f"{label}.path")
    if reason:
        return reason
    if task["kind"] not in TASK_KINDS:
        return f"{label}.kind must be one of {sorted(TASK_KINDS)} (got {task['kind']!r})"
    if task["layer"] not in TASK_LAYERS:
        return f"{label}.layer must be one of {sorted(TASK_LAYERS)} (got {task['layer']!r})"
    for key in ("feature", "export", "intent", "acceptance"):
        if not is_non_empty_str(task[key]):
            return f"{label}.{key} must be a non-empty string"

    hints = task["ast_hints"]
    reason = check_exact_keys(hints, AST_HINT_KEYS, f"{label}.ast_hints")
    if reason:
        return reason
    if not is_non_empty_str(hints["package"]):
        return f"{label}.ast_hints.package must be a non-empty string"
    for key in ("implements", "dependencies"):
        if not is_str_list(hints[key]):
            return f"{label}.ast_hints.{key} must be a list of non-empty strings"
    if not isinstance(hints["methods"], list) or not hints["methods"]:
        return f"{label}.ast_hints.methods must be a non-empty list"
    for index, method in enumerate(hints["methods"]):
        method_label = f"{label}.ast_hints.methods[{index}]"
        reason = check_exact_keys(method, ("signature", "returns"), method_label)
        if reason:
            return reason
        if not is_non_empty_str(method["signature"]) or not is_non_empty_str(method["returns"]):
            return f"{method_label}.signature and .returns must be non-empty strings"

    tdd = task["tdd"]
    reason = check_exact_keys(tdd, TDD_KEYS, f"{label}.tdd")
    if reason:
        return reason
    reason = validate_relative_path(tdd["test_path"], f"{label}.tdd.test_path")
    if reason:
        return reason
    if not isinstance(tdd["cases"], list) or not tdd["cases"]:
        return f"{label}.tdd.cases must be a non-empty list"
    for index, case in enumerate(tdd["cases"]):
        case_label = f"{label}.tdd.cases[{index}]"
        reason = check_exact_keys(case, TDD_CASE_KEYS, case_label)
        if reason:
            return reason
        for key in TDD_CASE_KEYS:
            if not is_non_empty_str(case[key]):
                return f"{case_label}.{key} must be a non-empty string"
    return None


def domain_slug(feature):
    """Filename-safe slug of the task domain (its `feature`)."""
    return re.sub(r"[^a-z0-9]+", "-", feature.lower()).strip("-")


def task_file_name(task):
    return f"{task['id']}-{domain_slug(task['feature'])}.json"


def existing_task_ids(output_dir):
    """IDs already written to the queue or complete folders (upstream domains)."""
    folders = [Path(output_dir), Path(output_dir).parent / "complete"]
    return {path.stem[:5] for folder in folders if folder.is_dir() for path in folder.glob("T-*.json")}


def validate_task_batch(tasks, external_ids=frozenset()):
    """Validate each task, then the batch: unique IDs, known dependencies, no cycles.

    Dependencies may point to tasks in this batch or to external_ids (upstream domains
    already queued or completed). External dependencies are not cycle-checked.
    """
    ids = {}
    for index, (source, task) in enumerate(tasks):
        label = f"task[{index}] ({source.name})"
        reason = validate_task(task, label)
        if reason:
            return reason
        if task["id"] in ids:
            return f"{label}.id {task['id']!r} duplicates another task"
        if task["id"] in external_ids:
            return f"{label}.id {task['id']!r} is already queued or completed"
        ids[task["id"]] = task

    for task_id, task in ids.items():
        unknown = [dep for dep in task["depends_on"] if dep not in ids and dep not in external_ids]
        if unknown:
            return f"{task_id}.depends_on references unknown task(s): {', '.join(unknown)}"

    remaining = {
        task_id: {dep for dep in task["depends_on"] if dep in ids}
        for task_id, task in ids.items()
    }
    while remaining:
        ready = [task_id for task_id, deps in remaining.items() if not deps]
        if not ready:
            return f"dependency cycle detected among: {', '.join(sorted(remaining))}"
        for task_id in ready:
            del remaining[task_id]
        for deps in remaining.values():
            deps.difference_update(ready)
    return None


def load_json(path):
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, f"input not found: {path}", EXIT_SOURCE
    except OSError as exc:
        return None, f"cannot read {path}: {exc}", EXIT_IO
    try:
        return json.loads(raw), None, EXIT_OK
    except json.JSONDecodeError as exc:
        return None, f"{path} is not valid JSON: {exc}", EXIT_INVALID


def atomic_write(target, payload, force):
    if target.exists() and not force:
        return f"refusing to overwrite existing file (use --force): {target}", EXIT_IO
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp_name, target)
    except OSError as exc:
        return f"cannot write {target}: {exc}", EXIT_IO
    return None, EXIT_OK


def cmd_strategy(args):
    payload, reason, code = load_json(Path(args.input).expanduser())
    if reason:
        print(f"[writer-architect] {reason}", file=sys.stderr)
        return code
    reason = validate_strategy(payload)
    if reason:
        print(f"[writer-architect] invalid strategy: {reason}", file=sys.stderr)
        return EXIT_INVALID
    reason, code = atomic_write(Path(args.output), payload, args.force)
    if reason:
        print(f"[writer-architect] {reason}", file=sys.stderr)
        return code
    print(f"[writer-architect] wrote {args.output}")
    return EXIT_OK


def cmd_tasks(args):
    input_dir = Path(args.input_dir).expanduser()
    if not input_dir.is_dir():
        print(f"[writer-architect] input directory not found: {input_dir}", file=sys.stderr)
        return EXIT_SOURCE
    sources = sorted(input_dir.glob("*.json"))
    if not sources:
        print(f"[writer-architect] no task JSON files in {input_dir}", file=sys.stderr)
        return EXIT_SOURCE

    tasks = []
    for source in sources:
        payload, reason, code = load_json(source)
        if reason:
            print(f"[writer-architect] {reason}", file=sys.stderr)
            return code
        tasks.append((source, payload))

    output_dir = Path(args.output_dir)
    reason = validate_task_batch(tasks, existing_task_ids(output_dir))
    if reason:
        print(f"[writer-architect] invalid task batch: {reason}", file=sys.stderr)
        return EXIT_INVALID

    for _, task in tasks:
        reason, code = atomic_write(output_dir / task_file_name(task), task, args.force)
        if reason:
            print(f"[writer-architect] {reason}", file=sys.stderr)
            return code
    print(f"[writer-architect] wrote {len(tasks)} task file(s) to {output_dir}")
    return EXIT_OK


def main():
    parser = argparse.ArgumentParser(
        description="Validate and write architect outputs (execution strategy and task files) to the blackboard.",
        epilog="Exit codes: 0 ok, 1 invalid payload, 2 source missing, 3 I/O error.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    strategy = subparsers.add_parser("strategy", help="validate and write execution-strategy.json")
    strategy.add_argument("--input", required=True, metavar="FILE", help="draft strategy JSON to validate")
    strategy.add_argument("--output", default=DEFAULT_STRATEGY, metavar="FILE", help=f"target (default: {DEFAULT_STRATEGY})")
    strategy.add_argument("--force", action="store_true", help="overwrite an existing target")
    strategy.set_defaults(func=cmd_strategy)

    tasks = subparsers.add_parser("tasks", help="validate a batch of task drafts and write T-xxx.json files")
    tasks.add_argument("--input-dir", required=True, metavar="DIR", help="directory with draft task JSON files")
    tasks.add_argument("--output-dir", default=DEFAULT_TASKS_DIR, metavar="DIR", help=f"target (default: {DEFAULT_TASKS_DIR})")
    tasks.add_argument("--force", action="store_true", help="overwrite existing task files")
    tasks.set_defaults(func=cmd_tasks)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
