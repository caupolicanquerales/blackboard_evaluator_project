#!/usr/bin/env python3
"""Write red-phase JSON to blackboard/red-phase/<task_id>.json (create or overwrite).

Reads the run-test-tool JSON from stdin, or from --input <file>.

Usage:
  python3 run-test-tool.py ... | python3 write-red-phase.py --root <project_root> --task-id <id> [--cmd <test command>]

The optional --cmd records the exact test command so the orchestrator can re-run
the same scoped test in the green phase (stage 2) without asking the agent again.
"""
import argparse
import datetime
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser(description="Write red-phase result file.")
    ap.add_argument("--root", required=True, help="Project root containing blackboard/")
    ap.add_argument("--task-id", required=True, help="Task id, used as file name")
    ap.add_argument("--input", help="JSON file to read instead of stdin")
    ap.add_argument("--cmd", help="The test command executed by run-test-tool.py")
    args = ap.parse_args()

    raw = open(args.input, encoding="utf-8").read() if args.input else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"written": None, "error": "invalid JSON: %s" % exc}))
        return 1

    # Orchestrator signal: the test was executed, so the flow may continue.
    if args.cmd:
        payload["command"] = args.cmd
    payload["task_id"] = args.task_id
    payload["executed"] = True
    payload["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    folder = os.path.join(args.root, "blackboard", "red-phase")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "%s.json" % args.task_id)

    # "w" truncates existing files, so repeated loop runs overwrite cleanly.
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")

    print(json.dumps({"written": path, "task_id": args.task_id, "executed": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
