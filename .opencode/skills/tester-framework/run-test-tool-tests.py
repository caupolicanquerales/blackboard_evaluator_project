#!/usr/bin/env python3
"""Test suite for run-test-tool.py (stdlib unittest, no external deps).

Run:  python3 .opencode/skills/tester-framework/run-test-tool-tests.py
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent / "run-test-tool.py"
_spec = importlib.util.spec_from_file_location("run_test_tool", TOOL)
rtt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rtt)

MAVEN_RED = """
[ERROR] Tests run: 2, Failures: 1, Errors: 0, Skipped: 0
GreeterTest.greetOk(GreeterTest)  Time elapsed: 0.01 s <<< FAILURE!
java.lang.AssertionError: expected: <hi> but was: <null>
[INFO] BUILD FAILURE
"""

MAVEN_COMPILE = """
[ERROR] src/main/java/Greeter.java:[8,5] cannot find symbol
  symbol:   method greet(java.lang.String)
[INFO] BUILD FAILURE
"""

JEST_RED = """
FAIL src/user.service.test.ts
  User service
    \u00d7 creates user
      expect(received).toBe(expected)
Tests: 1 failed, 3 passed, 4 total
"""

PYTEST_RED = """
FAILED tests/test_user.py::test_create - AssertionError: assert 1 == 2
=== 1 failed, 2 passed in 0.12s ===
"""

GO_RED = """
--- FAIL: TestGreet (0.00s)
    greeter_test.go:12: got "", want "hi"
FAIL
"""

TS_COMPILE = """
src/user.ts(3,5): error TS2554: Expected 2 arguments, but got 1.
"""


def status(output, exit_code=1):
    compile_hit, missing, failures, counts = rtt.parse(output)
    return rtt.classify(exit_code, compile_hit, missing, failures, counts, output), counts, failures


class ParseAndClassifyTest(unittest.TestCase):
    def test_classify_exit0_without_evidence_not_run(self):
        self.assertEqual(rtt.classify(0, False, [], {}, {}, ""), "not_run")

    def test_classify_build_success_passed(self):
        self.assertEqual(rtt.classify(0, False, [], {}, {}, "BUILD SUCCESS"), "passed")

    def test_classify_counts_run_passed(self):
        self.assertEqual(rtt.classify(0, False, [], {}, {"run": 3, "failures": 0, "errors": 0}, ""), "passed")

    def test_classify_compile_error_beats_exit_zero(self):
        self.assertEqual(rtt.classify(0, True, [], {}, {}, ""), "compile_error")

    def test_classify_nonzero_without_markers_error(self):
        self.assertEqual(rtt.classify(1, False, [], {}, {}, "boom"), "error")

    def test_parse_maven_red_counts_and_failure(self):
        status_name, counts, failures = status(MAVEN_RED)
        self.assertEqual(status_name, "assertion_failure")
        self.assertEqual(counts, {"run": 2, "failures": 1, "errors": 0})
        self.assertEqual(failures[0]["test"], "GreeterTest.greetOk(GreeterTest)")

    def test_parse_maven_compile_error_symbols(self):
        status_name, _, failures = status(MAVEN_COMPILE)
        self.assertEqual(status_name, "compile_error")

    def test_parse_jest_red(self):
        status_name, counts, failures = status(JEST_RED)
        self.assertEqual(status_name, "assertion_failure")
        self.assertEqual(counts, {"run": 4, "failures": 1, "errors": 0})
        self.assertTrue(any("user.service.test.ts" in f["test"] for f in failures))
        self.assertTrue(any("creates user" in f["test"] for f in failures))

    def test_parse_pytest_red(self):
        status_name, counts, failures = status(PYTEST_RED)
        self.assertEqual(status_name, "assertion_failure")
        self.assertEqual(counts, {"run": 3, "failures": 1, "errors": 0})

    def test_parse_go_red(self):
        status_name, _, failures = status(GO_RED)
        self.assertEqual(status_name, "assertion_failure")
        self.assertEqual(failures[0]["test"], "TestGreet")

    def test_parse_ts_compile_error(self):
        status_name, _, _ = status(TS_COMPILE)
        self.assertEqual(status_name, "compile_error")

    def test_shell_guard_rejects_operators(self):
        for cmd in ("cd x && npm test", "mvn test; rm -rf /", "npm test | tee log",
                    "mvn -Dx=$VAR test", 'python3 -c "print(1); print(2)" && echo done',
                    "mvn test > log.txt"):
            self.assertIsNotNone(rtt.shell_guard(cmd), cmd)

    def test_shell_guard_accepts_argv_commands(self):
        for cmd in ("./mvnw -q -Dtest=GreeterTest test", 'python3 -c "print(1)"', "go test ./...",
                    "npx jest --ci user.service",
                    "python3 -c \"print('x'); print('y')\"",
                    "gradle test --tests *GreeterTest*"):
            self.assertIsNone(rtt.shell_guard(cmd), cmd)

    def test_shell_guard_rejects_unbalanced_quotes(self):
        self.assertIsNotNone(rtt.shell_guard('python3 -c "print'))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _run(self, cmd):
        proc = subprocess.run(
            [sys.executable, str(TOOL), "--cwd", self.tmp, "--cmd", cmd],
            capture_output=True, text=True,
        )
        return proc.returncode, json.loads(proc.stdout)

    def test_cli_passing_evidence(self):
        code, result = self._run(f'{sys.executable} -c "print(\'3 passed in 0.1s\')"')
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "passed")

    def test_cli_silent_success_is_not_run(self):
        _, result = self._run(f"{sys.executable} -c pass")
        self.assertEqual(result["status"], "not_run")

    def test_cli_shell_operator_refused(self):
        code, result = self._run("echo hi && echo bye")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "not_run")
        self.assertIn("argv", result["reason"])

    def test_cli_missing_binary_not_run(self):
        code, result = self._run("definitely-not-a-real-binary --version")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "not_run")


if __name__ == "__main__":
    unittest.main(verbosity=2)
