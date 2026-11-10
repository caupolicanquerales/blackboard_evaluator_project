#!/usr/bin/env python3
"""Write a text payload (`body`) to `targetFile` under the project root.

Usage: _text_write_exec.py <changes.json> <project_root>
Exit 0 and {"status":"ok"} on success; exit 1 with {"status":"error","reason":...} otherwise.
Validates before touching the disk: leading tabs (YAML forbids them for indentation) and,
when PyYAML is importable, a parse pass. Absent PyYAML the build gate remains the check.
"""
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"status": "error", "reason": "usage: _text_write_exec.py <changes.json> <project_root>"}))
        return 1
    changes_path, project_root = Path(sys.argv[1]), Path(sys.argv[2])
    try:
        changes = json.loads(changes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "reason": f"cannot read payload: {exc}"}))
        return 1
    body, target_rel = changes.get("body"), changes.get("targetFile")
    if not isinstance(body, str) or not isinstance(target_rel, str) or not target_rel:
        print(json.dumps({"status": "error", "reason": "payload needs string `body` and `targetFile`"}))
        return 1
    for number, line in enumerate(body.splitlines(), start=1):
        stripped = line.lstrip(" ")
        if stripped.startswith("\t"):
            print(json.dumps({"status": "error",
                              "reason": f"YAML line {number} is indented with a tab; use spaces"}))
            return 1
    try:
        import yaml  # noqa: F401
        yaml.safe_load(body)
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "reason": f"YAML is not parseable: {exc}"}))
        return 1
    target = project_root / target_rel
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
    except OSError as exc:
        print(json.dumps({"status": "error", "reason": f"cannot write {target}: {exc}"}))
        return 1
    print(json.dumps({"status": "ok", "target_file": str(target)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
