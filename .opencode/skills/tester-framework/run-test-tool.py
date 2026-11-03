#!/usr/bin/env python3
"""Run one test command, parse raw output, emit compact JSON to stdout.

Usage:
  python3 run-test-tool.py --cwd <project_root> --cmd "<test command>" [--timeout 300]

Output JSON:
  status: passed | compile_error | assertion_failure | not_run | error
  exit_code, missing_symbols[], failures[{test, message}], counts{}, excerpt
"""
import argparse
import json
import re
import shlex
import subprocess
import sys

MAX_EXCERPT_LINES = 40
MAX_LIST = 50

# javac / maven: [ERROR] path.java:[12,5] cannot find symbol
RE_COMPILE_HEAD = re.compile(r"cannot find symbol|cannot access|package .* does not exist|error: ")
# javac symbol line: "  symbol:   class Foo"
RE_SYMBOL = re.compile(r"^\s*symbol:\s+(?:class|variable|method|interface|enum|package)?\s*(.+?)\s*$")
# python: NameError / ImportError / ModuleNotFoundError
RE_PY_MISSING = re.compile(r"(?:NameError|ImportError|ModuleNotFoundError): (.+)")
# go: undefined: Foo
RE_GO_MISSING = re.compile(r"undefined: (\S+)")
# JUnit / Surefire failure header: "testName(Class)  Time elapsed: 0.1 s  <<< FAILURE!"
RE_JUNIT_FAIL = re.compile(r"^\s*(?:\[ERROR\]\s+)?([\w$.()\[\], ]+?)\s+(?:Time elapsed:.*)?<<<\s*(FAILURE|ERROR)!?")
# Assertion messages
RE_ASSERT = re.compile(
    r"(AssertionError|AssertionFailedError|expected: |expecting |Expecting |"
    r"E\s+assert|FAILED |AssertionError:)"
)
# Summary counts: "Tests run: 3, Failures: 1, Errors: 0"
RE_COUNTS = re.compile(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)")
# pytest summary: "=== 2 failed, 1 passed in 0.1s ==="
RE_PYTEST = re.compile(r"(\d+) failed|(\d+) passed")


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

        m = RE_JUNIT_FAIL.match(line)
        if m:
            message = ""
            for follow in lines[i + 1:i + 4]:
                if RE_ASSERT.search(follow) or follow.strip():
                    message = follow.strip()
                    break
            failures.append({"test": m.group(1).strip(), "message": message[:300]})
        elif RE_ASSERT.search(line) and "Tests run" not in line:
            failures.append({"test": "", "message": line.strip()[:300]})

    counts = {}
    m = RE_COUNTS.search(output)
    if m:
        counts = {"run": int(m.group(1)), "failures": int(m.group(2)), "errors": int(m.group(3))}

    return compile_hit, unique(missing), failures[:MAX_LIST], counts


def excerpt(output):
    lines = [l for l in output.splitlines() if l.strip()]
    return lines[-MAX_EXCERPT_LINES:]


def classify(exit_code, compile_hit, missing, failures, counts):
    if exit_code == 0 and not failures and not compile_hit:
        return "passed"
    if compile_hit or missing:
        return "compile_error"
    if failures or counts.get("failures") or counts.get("errors"):
        return "assertion_failure"
    return "error"


def main():
    ap = argparse.ArgumentParser(description="Run one test command and emit structured JSON.")
    ap.add_argument("--cwd", required=True, help="Project root where the command runs")
    ap.add_argument("--cmd", required=True, help="Test command, e.g. './mvnw -q -Dtest=Foo test'")
    ap.add_argument("--timeout", type=int, default=300, help="Seconds before abort")
    args = ap.parse_args()

    exit_code, output = run(args.cmd, args.cwd, args.timeout)
    if exit_code is None:
        result = {"status": "not_run", "reason": output}
        print(json.dumps(result, indent=2))
        return 1

    compile_hit, missing, failures, counts = parse(output)
    status = classify(exit_code, compile_hit, missing, failures, counts)
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
