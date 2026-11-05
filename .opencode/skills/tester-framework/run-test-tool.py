#!/usr/bin/env python3
"""Run one test command, parse raw output, emit compact JSON to stdout.

Framework-agnostic by contract: the command runs WITHOUT a shell (argv only),
and pass/fail classification uses per-framework output patterns (Maven/Surefire,
Gradle, Jest/ts-jest, pytest, unittest, go test, cargo).

Usage:
  python3 run-test-tool.py --cwd <project_root> --cmd "<argv test command>" [--timeout 300]

Output JSON:
  status: passed | compile_error | assertion_failure | not_run | error
  exit_code, missing_symbols[], failures[{test, message}], counts{}, excerpt
  A "passed" status requires evidence of executed tests; a silent exit-0 run is
  reported as "not_run" so the orchestrator never mistakes an unexecuted suite
  for a green gate.
"""
import argparse
import json
import re
import shlex
import subprocess
import sys

MAX_EXCERPT_LINES = 40
MAX_LIST = 50

# These tokens need a real shell; with argv-only execution they would silently
# run the first command and ignore the rest, so they are refused up front.
SHELL_OPERATOR_TOKENS = ("&&", "||", ";", "|", "&", ">", "<", "$", "`")

# javac / maven / tsc: [ERROR] path.java:[12,5] cannot find symbol | error TS2554:
RE_COMPILE_HEAD = re.compile(
    r"cannot find symbol|cannot access|package .* does not exist|error: |error TS\d+"
)
# javac symbol line: "  symbol:   class Foo"
RE_SYMBOL = re.compile(r"^\s*symbol:\s+(?:class|variable|method|interface|enum|package)?\s*(.+?)\s*$")
# python: NameError / ImportError / ModuleNotFoundError
RE_PY_MISSING = re.compile(r"(?:NameError|ImportError|ModuleNotFoundError): (.+)")
# go: undefined: Foo
RE_GO_MISSING = re.compile(r"undefined: (\S+)")
# JUnit / Surefire failure header: "testName(Class)  Time elapsed: 0.1 s  <<< FAILURE!"
RE_JUNIT_FAIL = re.compile(r"^\s*(?:\[ERROR\]\s+)?([\w$.()\[\], ]+?)\s+(?:Time elapsed:.*)?<<<\s*(FAILURE|ERROR)!?")
# Jest / ts-jest: suite header "FAIL src/x.test.ts" and case line "  × creates user"
RE_JEST_SUITE = re.compile(r"^FAIL[ \t]+\S+")
RE_JEST_CASE = re.compile(r"^\s*[×✕✖]\s+(.+)$")
# go test: "--- FAIL: TestFoo (0.00s)"
RE_GO_FAIL = re.compile(r"^--- FAIL: (\S+)")
# Assertion messages
RE_ASSERT = re.compile(
    r"(AssertionError|AssertionFailedError|expected: |Expected:|expecting |Expecting |"
    r"E\s+assert|FAILED |AssertionError:|expect\()"
)
# Summary counts: "Tests run: 3, Failures: 1, Errors: 0"
RE_COUNTS = re.compile(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)")
# Cross-framework summaries: pytest ("1 failed, 2 passed"), jest ("Tests: 3 passed, 4 total"),
# cargo ("12 passed; 0 failed"), unittest ("Ran 10 tests")
RE_FAILED = re.compile(r"(\d+) failed")
RE_PASSED = re.compile(r"(\d+) passed")
RE_TOTAL = re.compile(r"(\d+) total")
RE_RAN = re.compile(r"Ran (\d+) tests")
# Proof that tests actually executed and succeeded (only consulted when exit code is 0).
RE_PASS_EVIDENCE = re.compile(
    r"BUILD SUCCESS"          # maven / gradle
    r"|\bPASS\b"              # go test summary
    r"|^[ \t]*ok[ \t]+\S"     # go test per-package
    r"|^OK$"                  # unittest summary
    r"|\d+ passed",           # pytest / jest / cargo
    re.IGNORECASE | re.MULTILINE,
)


def shell_guard(cmd):
    """Reject commands whose unquoted text needs a shell.

    Operators inside quotes are ordinary argv characters and are allowed; bare
    &&, ||, ;, |, redirects and $/` expansions (in or out of quotes) are refused
    because argv-only execution would run them differently than intended.
    """
    in_single = in_double = False
    i = 0
    while i < len(cmd):
        char = cmd[i]
        if in_single:
            in_single = char != "'"
        elif in_double:
            if char == '"':
                in_double = False
            elif char in ("$", "`"):
                return _guard_error(char)
        elif char == "'":
            in_single = True
        elif char == '"':
            in_double = True
        elif cmd.startswith(("&&", "||"), i):
            return _guard_error(cmd[i:i + 2])
        elif char in SHELL_OPERATOR_TOKENS:
            return _guard_error(char)
        i += 1
    try:
        shlex.split(cmd)
    except ValueError as exc:
        return "unbalanced quotes in --cmd: %s" % exc
    return None


def _guard_error(found):
    return ("--cmd runs argv without a shell; no bare &&, ;, |, redirects or $ expansion: %s" % found)


def run(cmd, cwd, timeout):
    try:
        proc = subprocess.run(
            shlex.split(cmd), cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return proc.returncode, proc.stdout + "\n" + proc.stderr
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %ss" % timeout
    except (FileNotFoundError, OSError) as exc:
        return None, "EXEC_ERROR: %s" % exc


def unique(items):
    seen, out = set(), []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out[:MAX_LIST]


def _follow_message(lines, i):
    for follow in lines[i + 1:i + 4]:
        if follow.strip():
            return follow.strip()[:300]
    return ""


def parse(output):
    lines = output.splitlines()
    missing, failures, compile_hit = [], [], False

    for i, line in enumerate(lines):
        if RE_COMPILE_HEAD.search(line):
            compile_hit = True
            for follow in lines[i + 1:i + 4]:
                m = RE_SYMBOL.match(follow)
                if m:
                    missing.append(m.group(1))
        m = RE_PY_MISSING.search(line)
        if m:
            compile_hit = True
            missing.append(m.group(1).strip())
        m = RE_GO_MISSING.search(line)
        if m:
            compile_hit = True
            missing.append(m.group(1))

        matched_failure = False
        m = RE_JUNIT_FAIL.match(line)
        if m:
            failures.append({"test": m.group(1).strip(), "message": _follow_message(lines, i)})
            matched_failure = True
        else:
            m = RE_GO_FAIL.match(line)
            if m:
                failures.append({"test": m.group(1), "message": _follow_message(lines, i)})
                matched_failure = True
            elif RE_JEST_SUITE.match(line):
                failures.append({"test": line.strip(), "message": _follow_message(lines, i)})
                matched_failure = True
            else:
                m = RE_JEST_CASE.match(line)
                if m:
                    failures.append({"test": m.group(1).strip(), "message": _follow_message(lines, i)})
                    matched_failure = True
        if not matched_failure and RE_ASSERT.search(line) and "Tests run" not in line:
            failures.append({"test": "", "message": line.strip()[:300]})

    return compile_hit, unique(missing), failures[:MAX_LIST], parse_counts(output)


def parse_counts(output):
    m = RE_COUNTS.search(output)
    if m:
        return {"run": int(m.group(1)), "failures": int(m.group(2)), "errors": int(m.group(3))}
    failed = RE_FAILED.search(output)
    passed = RE_PASSED.search(output)
    if failed or passed:
        failures = int(failed.group(1)) if failed else 0
        passed_n = int(passed.group(1)) if passed else 0
        total = RE_TOTAL.search(output)
        run_n = int(total.group(1)) if total else failures + passed_n
        return {"run": run_n, "failures": failures, "errors": 0}
    ran = RE_RAN.search(output)
    if ran:
        return {"run": int(ran.group(1)), "failures": 0, "errors": 0}
    return {}


def excerpt(output):
    lines = [l for l in output.splitlines() if l.strip()]
    return lines[-MAX_EXCERPT_LINES:]


def classify(exit_code, compile_hit, missing, failures, counts, output):
    if compile_hit or missing:
        return "compile_error"
    if failures or counts.get("failures") or counts.get("errors"):
        return "assertion_failure"
    if exit_code != 0:
        return "error"
    if counts.get("run") or RE_PASS_EVIDENCE.search(output):
        return "passed"
    return "not_run"


def main():
    ap = argparse.ArgumentParser(description="Run one test command and emit structured JSON.")
    ap.add_argument("--cwd", required=True, help="Project root where the command runs")
    ap.add_argument("--cmd", required=True, help="Test command as argv, e.g. './mvnw -Dtest=Foo test' (must print its test summary)")
    ap.add_argument("--timeout", type=int, default=300, help="Seconds before abort")
    args = ap.parse_args()

    blocked = shell_guard(args.cmd)
    if blocked:
        print(json.dumps({"status": "not_run", "reason": blocked}, indent=2))
        return 1

    exit_code, output = run(args.cmd, args.cwd, args.timeout)
    if exit_code is None:
        result = {"status": "not_run", "reason": output}
        print(json.dumps(result, indent=2))
        return 1

    compile_hit, missing, failures, counts = parse(output)
    status = classify(exit_code, compile_hit, missing, failures, counts, output)
    result = {
        "status": status,
        "exit_code": exit_code,
        "missing_symbols": missing,
        "failures": failures,
        "counts": counts,
    }
    if status != "passed":
        result["excerpt"] = excerpt(output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
