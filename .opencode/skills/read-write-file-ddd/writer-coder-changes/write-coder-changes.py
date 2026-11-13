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
# The complete payload schema. Keys OUTSIDE it are refused, never ignored: a silently
# dropped field turns a tool-contract gap into endless "agent capability" failures
# (a coder once shipped the right fix twice and the weave dropped it twice).
OPTIONAL_KEYS = ("kind", "members", "annotations", "methodAnnotations",
                 "extends", "implements", "stage", "executed", "recorded_at")
ALLOWED_KEYS = frozenset(REQUIRED_STR) | frozenset(REQUIRED_LIST) | frozenset(OPTIONAL_KEYS)


def _decl_head(text):
    """(tokens_before_paren, paren_index) of a signature/member, ignoring parens
    nested inside generic angle brackets (e.g. "Function<A, B> apply(...)")."""
    depth_angle = 0
    for i, ch in enumerate(text):
        if ch == "<":
            depth_angle += 1
        elif ch == ">" and depth_angle:
            depth_angle -= 1
        elif ch == "(" and depth_angle == 0:
            return text[:i].replace(",", " ").split(), i
    return text.replace(",", " ").split(), -1


def _binding_is_static(head_tokens, is_constructor):
    """True when a declaration's pre-paren tokens carry the 'static' modifier.
    An ENUM's implicit valueOf is never emitted as a member, so no special case:
    the TABLE is the only binding truth (instance unless it spells 'static')."""
    return "static" in head_tokens


def load_task_contract(root, task_id):
    """The task record's ast_hints table from queue/complete/error, or None.

    Absent record or absent table (legacy board) disables the drift check - the
    guard must refuse drift it can prove, never guess bindings it cannot see.
    """
    for folder in ("queue", "complete", "error"):
        base = os.path.join(root, "blackboard", folder)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if not name.startswith(task_id + "-") or not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(base, name), encoding="utf-8") as fh:
                    task = json.load(fh)
            except (OSError, json.JSONDecodeError):
                return None
            hints = task.get("ast_hints") if isinstance(task, dict) else None
            return hints if isinstance(hints, dict) else None
    return None


def table_drift_errors(payload, hints):
    """Refuse payload declarations whose 'static' modifier differs from the pinned
    table entry for the same member name.

    Live defect 2026-11-12: the table pins `String headerName()` (instance) and the
    coder shipped `public static String headerName()`. Instance-reference syntax
    (`context.headerName()`) COMPILES against statics, so the unit's own frozen test
    went green - while a sibling frozen test that STUBS the member on a mock can
    never pass for any payload. The impersonation is invisible per-unit and fatal
    cross-unit; the writer is where both sides are visible at once, in-session,
    free to fix."""
    errors = []
    if not isinstance(hints, dict):
        return errors
    entries = {}
    for method in hints.get("methods") or []:
        if not isinstance(method, dict):
            continue
        sig = str(method.get("signature") or "")
        head, _ = _decl_head(sig)
        if not head:
            continue
        name = head[-1]
        entries[name] = (sig, _binding_is_static(head, False))
    for name, (table_sig, table_static) in entries.items():
        # primary triple
        if str(payload.get("method") or "").strip() == name:
            p_head, p_paren = _decl_head(str(payload.get("signature") or ""))
            p_static = _binding_is_static(p_head, False)
            if p_static != table_static:
                errors.append(
                    "signature drift: payload spells '%s' as %s but the pinned ast_hints "
                    "table entry is '%s' (%s) - emit the signature EXACTLY as the table "
                    "binds it: a member the table spells without 'static' must NOT become "
                    "static (instance-reference syntax hides the drift from this unit's "
                    "own test while sibling tests that stub it on a mock fail forever)"
                    % (name, "static" if p_static else "INSTANCE",
                       table_sig, "static" if table_static else "instance binding"))
        # members array (declaration strings)
        for member in payload.get("members") or []:
            if not isinstance(member, str) or "(" not in member:
                continue
            m_head, _ = _decl_head(member)
            if not m_head or m_head[-1] != name:
                continue
            if _binding_is_static(m_head, False) != table_static:
                errors.append(
                    "members[] drift: '%s' is spelled %s but the table binds it %s ('%s') "
                    "- reproduce the table's binding exactly"
                    % (member.strip()[:80], "static" if _binding_is_static(m_head, False)
                       else "instance", "static" if table_static else "instance", table_sig))
    return errors


def validate(payload, task_id):
    """Return a list of human-readable schema errors. Empty list means valid."""
    errors = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    unknown = sorted(str(key) for key in payload if str(key) not in ALLOWED_KEYS)
    if unknown:
        errors.append("unknown payload key(s): " + ", ".join(unknown)
                      + " - not part of the schema and never ignored; schema keys: "
                      + ", ".join(sorted(ALLOWED_KEYS)))

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

    # Supertype clauses: the frozen test can demand IS-A (isInstanceOf(Port.class), DI by
    # port type); the weaver lands them on the type header. Validate so a malformed guess
    # is refused here, not silently dropped at weave time.
    ext = payload.get("extends")
    if ext is not None and not isinstance(ext, str):
        errors.append("extends must be a string (the supertype the type extends; omit or empty for none)")
    impl = payload.get("implements")
    if impl is not None:
        if not isinstance(impl, list) or not all(isinstance(s, str) and s.strip() for s in impl):
            errors.append("implements must be an array of supertype names")

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
    if not errors:
        # Table-drift guard: the pinned ast_hints is the single API truth - refuse
        # bindings that differ from it while the session can still fix them for free.
        errors = table_drift_errors(payload, load_task_contract(args.root, args.task_id))
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
