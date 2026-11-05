#!/usr/bin/env python3
"""Write an agent-evaluator result to blackboard/evaluate-results/<task_id>.json.

Reads the evaluation payload (JSON object) from stdin or from --input <file>.
The payload must carry the full run-test-tool JSON of the final test run under
`final_test`; the writer refuses anything not green, so a task can only be
completed with a persisted, verified refactoring outcome.

Usage:
  python3 write-evaluate-results.py --root <project_root> --task-id <id> --input <payload.json>
  cat payload.json | python3 write-evaluate-results.py --root <project_root> --task-id <id>

Exit codes:
  0  written
  1  invalid JSON or schema violation (nothing written)
  2  final_test is missing or not green (nothing written)

Output (stdout): {"written": "<path>", "task_id": "<id>", "executed": true}
"""
import argparse
import datetime
import json
import os
import sys

REQUIRED_STR = ("project", "targetFile", "stack", "skill", "summary")
REQUIRED_LIST = ("findings", "changes", "reverts")


def validate(payload):
    """Return a list of human-readable schema errors. Empty list means valid."""
    errors = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    for key in REQUIRED_STR:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append("%s must be a non-empty string" % key)

    for key in REQUIRED_LIST:
        value = payload.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append("%s must be an array of strings" % key)

    final_test = payload.get("final_test")
    if not isinstance(final_test, dict):
        errors.append("final_test must be the run-test-tool JSON object")
    return errors


def main():
    ap = argparse.ArgumentParser(description="Write agent-evaluator result file.")
    ap.add_argument("--root", required=True, help="Project root containing blackboard/")
    ap.add_argument("--task-id", required=True, help="Task id, used as file name")
    ap.add_argument("--input", help="JSON file to read instead of stdin")
    args = ap.parse_args()

    raw = open(args.input, encoding="utf-8").read() if args.input else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"written": None, "error": "invalid JSON: %s" % exc}))
        return 1

    errors = validate(payload)
    if errors:
        print(json.dumps({"written": None, "error": "schema violation", "details": errors}))
        return 1

    status = payload["final_test"].get("status")
    if status != "passed":
        print(json.dumps({"written": None,
                          "error": "final_test.status must be 'passed'",
                          "status": status}))
        return 2

    # Orchestrator signal fields, always set by the script (never trusted from the payload).
    payload["task_id"] = args.task_id
    payload["stage"] = 3
    payload["executed"] = True
    payload["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    folder = os.path.join(args.root, "blackboard", "evaluate-results")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "%s.json" % args.task_id)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")

    print(json.dumps({"written": path, "task_id": args.task_id, "executed": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
