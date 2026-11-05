#!/usr/bin/env python3
"""Write coder output to blackboard/coder-changes/<task_id>.json.

Reads the coder payload (JSON object) from stdin, or from --input <file>.
Validates the schema defined in agent-coder, then writes the file.
Refuses to overwrite an existing file unless --retry is passed (orchestrator-requested retry).

Usage:
  python3 write-coder-changes.py --root <project_root> --task-id <id> --input <payload.json>
  cat payload.json | python3 write-coder-changes.py --root <project_root> --task-id <id>
  python3 write-coder-changes.py --root <project_root> --task-id <id> --retry --input <payload.json>

Exit codes:
  0  written
  1  invalid JSON or schema violation (nothing written)
  2  file already exists and --retry was not given (nothing written)

Output (stdout): {"written": "<path>", "task_id": "<id>", "executed": true}
"""
import argparse
import datetime
import json
import os
import sys

REQUIRED_STR = ("id", "project", "targetFile", "export", "method",
                "language", "framework", "skill", "signature", "returns", "body")
KINDS = ("class", "interface", "enum", "record", "exception")
REQUIRED_LIST = ("imports", "missing")


def validate(payload, task_id):
    """Return a list of human-readable schema errors. Empty list means valid."""
    errors = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    for key in REQUIRED_STR:
        if key not in payload:
            errors.append("missing key: %s" % key)
        elif not isinstance(payload[key], str):
            errors.append("%s must be a string" % key)
        elif key != "body" and not payload[key].strip():
            errors.append("%s must not be empty" % key)

    for key in REQUIRED_LIST:
        if key not in payload:
            errors.append("missing key: %s" % key)
        elif not isinstance(payload[key], list) or not all(isinstance(i, str) for i in payload[key]):
            errors.append("%s must be an array of strings" % key)

    for key in ("annotations", "methodAnnotations"):
        entries = payload.get(key)
        if entries is None:
            continue
        if not isinstance(entries, list) or not all(isinstance(a, str) and a.strip() for a in entries):
            errors.append("%s must be a non-empty array of annotation strings" % key)

    kind = payload.get("kind")
    if kind is not None and kind not in KINDS:
        errors.append("kind must be one of %s" % list(KINDS))
    members = payload.get("members", [])
    if not isinstance(members, list) or not all(isinstance(m, str) for m in members):
        errors.append("members must be an array of strings")
    elif members:
        payload["members"] = members

    if "stage" in payload and payload["stage"] != 2:
        errors.append("stage must be 2")

    if payload.get("id") not in (None, task_id):
        errors.append("payload id '%s' does not match --task-id '%s'" % (payload.get("id"), task_id))

    body = payload.get("body")
    if isinstance(body, str) and not body.strip() and not payload.get("members"):
        errors.append("body must not be empty unless members define the type")

    return errors


def main():
    ap = argparse.ArgumentParser(description="Write coder-changes file for one task.")
    ap.add_argument("--root", required=True, help="Project root containing blackboard/")
    ap.add_argument("--task-id", required=True, help="Task id, used as file name")
    ap.add_argument("--input", help="JSON file to read instead of stdin")
    ap.add_argument("--retry", action="store_true", help="Allow overwriting an existing file")
    args = ap.parse_args()

    raw = open(args.input, encoding="utf-8").read() if args.input else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"written": None, "error": "invalid JSON: %s" % exc}))
        return 1

    errors = validate(payload, args.task_id)
    if errors:
        print(json.dumps({"written": None, "error": "schema violation", "details": errors}))
        return 1

    folder = os.path.join(args.root, "blackboard", "coder-changes")
    path = os.path.join(folder, "%s.json" % args.task_id)

    if os.path.exists(path) and not args.retry:
        print(json.dumps({"written": None, "error": "file exists, use --retry to overwrite", "path": path}))
        return 2

    # Orchestrator signal fields, always set by the script (never trusted from the payload).
    payload["id"] = args.task_id
    payload["stage"] = 2
    payload["executed"] = True
    payload["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")

    print(json.dumps({"written": path, "task_id": args.task_id, "executed": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
