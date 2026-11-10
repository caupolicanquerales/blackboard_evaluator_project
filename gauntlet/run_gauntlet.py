"""Gauntlet runner: the pre-flight every change must pass before a live drain.

Usage:
    python3 gauntlet/run_gauntlet.py            # suites over temp boards, ~5 s
    python3 gauntlet/run_gauntlet.py --weaver   # also the weaver's JUnit suite (~1 min)

Rule of the repo: any fix to orchestrators/ or .opencode/skills/ ships WITH a case
here. A bug that reaches a live run is a gauntlet gap, not an unlucky language shape.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITES = [HERE / "test_skill_scripts.py", HERE / "test_engine_decisions.py"]

failures = []
for suite in SUITES:
    print(f"== {suite.name}")
    result = subprocess.run([sys.executable, str(suite)], capture_output=True, text=True)
    tail = [line for line in result.stdout.splitlines() if "SUITE" in line or "FAILED" in line]
    for line in tail:
        print("   " + line)
    if result.returncode != 0:
        failures.append(suite.name)
        print(result.stdout[-1500:])
        print(result.stderr[-600:])

if "--weaver" in sys.argv:
    tool = HERE.parent / "ast_weaver_tools" / "ast_weaver_java"
    print("== ast_weaver_java (JUnit)")
    result = subprocess.run(["./mvnw", "-q", "test"], cwd=tool, capture_output=True, text=True)
    if result.returncode != 0:
        failures.append("ast_weaver_java")
        print(result.stdout[-2000:])

print()
print("GAUNTLET:", "ALL GREEN" if not failures else f"FAILED -> {', '.join(failures)}")
sys.exit(1 if failures else 0)
