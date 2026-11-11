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
  member_demands[{member, owner, kind}] when a compiler says a KNOWN type lacks a
  member/constructor (javac symbol/location pairs, tsc TS2339, AttributeError,
  go field/method undefined) - normalized here so the engine can attribute the gap
  to the unit exporting `owner` without reading any toolchain grammar.
  problem_kinds[{file, line, kind, supertypes?}] classifying every positioned compile
  error as supertype | missing-symbol | other (phrase tables live HERE): the engine's
  cascade-vs-structural and moving-port deferral decisions read this field, and the
  blamed file's declared `supertypes` ride along for supertype entries.
  bean_demands[simpleTypeName] when a context boot failed demanding a bean that does
  not exist yet (Spring phrasing parsed HERE only): the engine defers the demanding
  unit while the bean belongs to a peer's exported product.
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
    r"cannot find symbol|cannot access|package .* does not exist|No module named|"
    r"[Cc]annot find module|could not import|no required module provides|error: |error TS\d+"
    r"|does not override|incorrectly implements|does not implement|does not satisfy"
)
# javac symbol line: "  symbol:   class Foo"
RE_SYMBOL = re.compile(r"^\s*symbol:\s+(?:class|variable|method|interface|enum|package)?\s*(.+?)\s*$")
# Member demands on a KNOWN receiver type, normalized to `member_demands`:
# [{"member": name, "owner": TYPE, "kind": method|constructor|property|attribute}].
# Toolchain grammar lives HERE (this tool owns it) so the orchestrator can attribute
# "the gap sits on MY exported type" without ever reading a compiler's output shape:
# javac pairs `symbol: method compute(X)` with `location: class com.x.Box<T>`; tsc prints
# "Property 'x' does not exist on type 'Y'"; python AttributeError names the object's
# class; go names "undefined (type Foo has no field or method x)".
RE_JAVAC_MEMBER = re.compile(r"^\s*symbol:\s+(method|constructor|variable|class)\s+(.+?)\s*$")
RE_POSITIONED_FILE = re.compile(
    r"(\S+\.(?:java|kt|kts|scala|groovy|ts|tsx|js|jsx|mjs|cjs|go|py|rs|rb|php|c|h|cc|cpp|hpp|cs|swift))"
    r":?[\[(](\d+)")
RE_JAVAC_LOCATION = re.compile(r"^\s*location:\s*(?:class|interface|record|enum)\s+(\S+)")
# `location: variable NAME of type com.x.Receiver<...>`: javac's phrasing when the receiver
# object resolves but the member on its TYPE does not. A `symbol: class Nested` under a
# `location: class Outer` names a NESTED type of the owner (Outer.Nested), never a gap in
# the file that referenced it - attribution goes to Outer's producer either way.
RE_JAVAC_LOCATION_VARIABLE = re.compile(
    r"^\s*location:\s*variable\s+\S+\s+of\s+type\s+(\S+)")
RE_TSC_PROPERTY = re.compile(r"Property ['\"]([\w]+)['\"] does not exist on type ['\"]([\w.\[\]<>]+)['\"]")
RE_PY_ATTRIBUTE = re.compile(r"AttributeError: ['\"](\w+)['\"] object has no attribute ['\"](\w+)['\"]")
RE_GO_FIELD = re.compile(r"([\w]+) undefined \(type ([\w.\-]+) has no field or method ([\w]+)\)")
# Context-boot demands: "No qualifying bean of type 'x.Y' available" (Spring) - the
# engine needs the SIMPLE TYPE NAME as a normalized field, never this phrasing.
RE_MISSING_BEAN = re.compile(r"No qualifying bean of type '([\w.$]+)'")
# Problem kinds per compile-error location, normalized to `problem_kinds`:
# [{"file": NAME, "line": N, "kind": supertype|missing-symbol|other}]. The engine's
# cascade-vs-structural and supertype-conflict decisions read this FIELD instead of
# scanning message text; every toolchain's phrasing is tabled HERE, at the tool that
# owns syntax. `supertypes` (the blamed file's declared supertype names) rides along
# for supertype-kind entries so ownership questions never need source grammar either.
PROBLEM_KIND_PATTERNS = (
    ("supertype", re.compile(r"does not override|from a supertype|incorrectly implements"
                             r"|does not implement|does not satisfy", re.I)),
    ("missing-symbol", re.compile(r"cannot find symbol|cannot access|Cannot find name"
                                  r"|undefined:|NameError|error TS2304", re.I)),
)
RE_TYPE_SUPERTYPES = re.compile(
    r"\b(?:implements|extends)\s+([\w.]+(?:\s*,\s*[\w.]+)*)")
# A missing PACKAGE/MODULE (not a symbol) means the dependency is not on the classpath/module
# path and no coder payload can add it: the orchestrator aborts on these instead of burning
# sessions. Every toolchain phrasing is normalized HERE, so consumers read one field.
RE_MISSING_PACKAGE = re.compile(
    r"package ([a-z][\w.]*) does not exist"                 # javac
    r"|No module named ['\"]([\w.]+)['\"]"                  # python
    r"|[Cc]annot find module ['\"]([^'\"]+)['\"]"           # tsc / node
    r"|could not import ([\w./\-]+)"                        # go
    r"|no required module provides package ([\w./\-]+)"      # go
)
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
# Surefire console summary (NOT the .txt style): the failure/error sections list each
# case as `Class.method[:line] » ExceptionKind message`. Without this branch the wave
# verdicts carry UNNAMED, MESSAGE-LESS failures and retrying coders iterate blind (the
# T2-003 pair-defect evidence: `errors=3` shown as an empty message).
RE_JUNIT_SUMMARY = re.compile(
    r"^\s*(?:\[ERROR\]\s+)?((?:[A-Za-z_$][\w$]*\.)+[A-Za-z_$][\w$]*)(?::\d+)?\s+\u00bb\s+(\S.*)$")
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


def unique_demands(items):
    """`unique` for dict entries: identity is (member, owner, kind), kept hashable."""
    seen, out = set(), []
    for item in items:
        key = (item.get("member"), item.get("owner"), item.get("kind"))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:MAX_LIST]


def unique_problems(items):
    seen, out = set(), []
    for item in items:
        key = (item.get("file"), item.get("line"), item.get("kind"))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:MAX_LIST]


def _follow_message(lines, i):
    """Meaningful lines under a failure header.

    Surefire prints the exception class on the first line (`org.opentest4j.AssertionFailedError:`)
    and the expected/actual detail BELOW it: returning only the first line hands a retrying coder
    a class name, which is why assertion-level failures exhaust the 3 attempts unchanged. Collect
    up to 4 non-empty lines, stop at stack frames, cap the message.
    """
    collected = []
    for follow in lines[i + 1:i + 16]:
        text = follow.strip()
        if not text:
            continue
        if text.startswith(("at ", "Caused by", "Suppressed", "[ERROR] Tests run", "=== ", "--- ")):
            break
        collected.append(text[:120])
        if sum(len(item) for item in collected) >= 300:
            break
    return " | ".join(collected)[:320]


def parse(output, root=None):
    # Maven's logger wraps some plugin/javac detail lines in `[ERROR] ` and leaves others
    # raw; anchored symbol/location parsing must see both alike. Positions are preserved
    # (the raw `output` still feeds the coder-facing excerpt).
    lines = [re.sub(r"^\s*\[ERROR\]\s*", "", l) for l in output.splitlines()]
    missing, missing_packages, failures, compile_hit = [], [], [], False
    # Normalized "type X is missing a member/constructor" facts, extracted from whatever
    # compiler phrased them. The engine attributes these to a unit by exported type name.
    demands = []
    # Normalized problem-kind ledger: see PROBLEM_KIND_PATTERNS above.
    problems = []
    # Context-boot bean demands, normalized to simple type names (index 7).
    beans = []

    def owner_of(type_name):
        head = type_name.split("<", 1)[0]
        return head.rsplit(".", 1)[-1].rstrip(";,)")

    def declared_supertypes(path_text):
        import os
        candidate = path_text if os.path.isabs(path_text) else os.path.join(root or "", path_text)
        try:
            with open(candidate, encoding="utf-8", errors="ignore") as handle:
                source = handle.read()
        except OSError:
            return []
        names = []
        for match in RE_TYPE_SUPERTYPES.finditer(source):
            for part in match.group(1).split(","):
                name = part.strip().split("<")[0].split(".")[-1].strip()
                if name and name not in names:
                    names.append(name)
        return names[:8]

    def source_context(header_line):
        """Quote the failing source line at the position the log names.

        Any toolchain that prints `file:[line,col]` works - the line number addresses
        the file the build just read, so the coder sees the exact expression that does
        not compile instead of burning a tool call re-grepping the frozen test.
        """
        m = RE_POSITIONED_FILE.search(header_line)
        if not m:
            return None
        try:
            with open(m.group(1), encoding="utf-8", errors="ignore") as fh:
                for n, ln in enumerate(fh, 1):
                    if n == int(m.group(2)):
                        return ln.strip()[:160] or None
        except OSError:
            return None
        return None

    def javac_location_owner(idx):
        # symbol:/location: pairs may interleave a `kind:` line; stop at the next block.
        # Two location shapes: `location: class com.x.Box<T>` (reference inside/through
        # Box) and `location: variable v of type com.x.Box<...>` (receiver resolves,
        # member on its type does not). Both name Box as the surface that must change.
        for follow in lines[idx + 1:idx + 4]:
            m = RE_JAVAC_LOCATION.match(follow) or RE_JAVAC_LOCATION_VARIABLE.match(follow)
            if m:
                return owner_of(m.group(1))
            if RE_JAVAC_MEMBER.match(follow) or RE_COMPILE_HEAD.search(follow):
                return None
        return None

    for i, line in enumerate(lines):
        if RE_COMPILE_HEAD.search(line):
            compile_hit = True
            head = RE_POSITIONED_FILE.search(line)
            if head:
                kind = next((k for k, pattern in PROBLEM_KIND_PATTERNS
                             if pattern.search(line)), "other")
                entry = {"file": head.group(1).rsplit("/", 1)[-1].lstrip("."),
                         "line": int(head.group(2)), "kind": kind}
                if kind == "supertype":
                    sup = declared_supertypes(head.group(1))
                    if sup:
                        entry["supertypes"] = sup
                problems.append(entry)
            for offset, follow in enumerate(lines[i + 1:i + 4]):
                m = RE_SYMBOL.match(follow)
                if m:
                    missing.append(m.group(1))
                member = RE_JAVAC_MEMBER.match(follow)
                if member and member.group(1) in ("method", "constructor", "class"):
                    owner = javac_location_owner(i + offset + 1)
                    if owner:
                        entry = {"member": member.group(2), "owner": owner,
                                 "kind": member.group(1)}
                        ctx = source_context(line)
                        if ctx:
                            entry["context"] = ctx
                        demands.append(entry)
            m = RE_MISSING_PACKAGE.search(line)
            if m:
                pkg = next((g for g in m.groups() if g), None)
                if pkg:
                    missing_packages.append(pkg)
        m = RE_PY_MISSING.search(line)
        if m:
            compile_hit = True
            missing.append(m.group(1).strip())
        m = RE_GO_MISSING.search(line)
        if m:
            compile_hit = True
            missing.append(m.group(1))
        m = RE_TSC_PROPERTY.search(line)
        if m:
            demands.append({"member": m.group(1), "owner": owner_of(m.group(2)),
                            "kind": "property"})
        m = RE_PY_ATTRIBUTE.search(line)
        if m:
            demands.append({"member": m.group(2), "owner": m.group(1), "kind": "attribute"})
        m = RE_GO_FIELD.search(line)
        if m:
            demands.append({"member": m.group(3), "owner": owner_of(m.group(2)),
                            "kind": "method"})
        bean = RE_MISSING_BEAN.search(line)
        if bean:
            beans.append(bean.group(1).rsplit(".", 1)[-1])

        matched_failure = False
        m = RE_JUNIT_SUMMARY.match(line)
        if m:
            failures.append({"test": m.group(1).strip(), "message": m.group(2).strip()[:300]})
            matched_failure = True
        else:
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

    return (compile_hit, unique(missing), unique(missing_packages), failures[:MAX_LIST],
            parse_counts(output), unique_demands(demands), unique_problems(problems),
            unique(beans))


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


RE_MVN_CLASS = re.compile(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+).*? in (\S+)")
RE_PYTEST_RES = re.compile(r"^(PASSED|FAILED|ERROR)\s+(\S+?)(?:::|\s|$)", re.M)
RE_JEST_RES = re.compile(r"^(PASS|FAIL)\s+(\S+\.[cm]?[jt]sx?)\s*$", re.M)
RE_GO_RES = re.compile(r"^(ok|FAIL)\s*\t(\S+)", re.M)


def parse_classes(output):
    """Per-test-file verdicts of a whole-suite run: {identifier: "passed"|"failed"}.

    The orchestrator's wave gate maps a unit's scoped selector onto these keys by
    simple-name/stem equality and refuses to guess on collisions. Toolchain syntax is
    parsed HERE (this tool owns it); the engine consumes a neutral map.
    """
    classes = {}
    for m in RE_MVN_CLASS.finditer(output):
        run, fails, errors, _skipped, fqcn = m.groups()
        if int(run) <= 0:
            continue
        classes[fqcn] = "passed" if int(fails) == 0 and int(errors) == 0 else "failed"
    for m in RE_PYTEST_RES.finditer(output):
        ident = m.group(2).split("::")[0]
        if m.group(1) in ("FAILED", "ERROR"):
            classes[ident] = "failed"
        else:
            classes.setdefault(ident, "passed")
    for m in RE_JEST_RES.finditer(output):
        if m.group(1) == "PASS":
            classes.setdefault(m.group(2), "passed")
        else:
            classes[m.group(2)] = "failed"
    for m in RE_GO_RES.finditer(output):
        if m.group(1) == "ok":
            classes.setdefault(m.group(2), "passed")
        else:
            classes[m.group(2)] = "failed"
    return classes


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

    compile_hit, missing, missing_packages, failures, counts, demands, problems, beans = parse(output, args.cwd)
    status = classify(exit_code, compile_hit, missing, failures, counts, output)
    result = {
        "status": status,
        "exit_code": exit_code,
        "missing_symbols": missing,
        "missing_packages": missing_packages,
        "failures": failures,
        "counts": counts,
        "classes": parse_classes(output),
    }
    if demands:
        result["member_demands"] = demands
    if problems:
        result["problem_kinds"] = problems
    if beans:
        result["bean_demands"] = beans
    if status != "passed":
        result["excerpt"] = excerpt(output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
