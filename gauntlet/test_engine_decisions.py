"""Gauntlet: orchestrator decision rules on synthetic boards.

Every fixture here is distilled from a real incident, but the inputs are structured
fields only - the engine must never be tested (or allowed) to read compiler output.
Coverage:
  A. attribution: own-type demands, nested-vs-top-level, hole subtraction
  B. charge precedence: the frozen test's OWN implementer answers first
  C. wave gate sharing: tree-wide decisive verdicts cost ONE build per state
  D. attempt ledger + grants: informed-attempt semantics, zero-session closeouts
  E. auto-grant: self-healing selection, storm guards intact
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "orchestrators"))
import settings

ROOT = Path("/tmp/opencode/gauntlet-engine")
shutil.rmtree(ROOT, ignore_errors=True)
for d in ("blackboard/attempts", "blackboard/red-phase", "blackboard/ast-context",
          "blackboard/coder-changes", "blackboard/queue", "blackboard/error",
          "blackboard/gate-cache", "proj/src"):
    (ROOT / d).mkdir(parents=True)
settings.ROOT = ROOT
settings.BLACKBOARD = ROOT / "blackboard"
settings.QUEUE_DIR = ROOT / "blackboard" / "queue"
settings.COMPLETE_DIR = ROOT / "blackboard" / "complete"
settings.ERROR_DIR = ROOT / "blackboard" / "error"
settings.RED_PHASE_DIR = ROOT / "blackboard" / "red-phase"
settings.AST_CONTEXT_DIR = ROOT / "blackboard" / "ast-context"
settings.ATTEMPTS_DIR = ROOT / "blackboard" / "attempts"
settings.GATE_CACHE_DIR = ROOT / "blackboard" / "gate-cache"
settings.DOMAIN_DIR = ROOT / "blackboard" / "domain"
settings.CONTEXT_MAP_DIR = ROOT / "blackboard" / "context-map"
(ROOT / "blackboard" / "complete").mkdir(parents=True)

import attempt_ledger
import task_queue
import tdd_engine
import test_gate
import workspace


workspace.project_root_for = lambda project: ROOT / "proj"
CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f" {'PASS' if cond else 'FAIL'} {name}" + ("" if cond else f"  [{detail}]"))


def task(tid="T2-001", export="com.x.Box", deps=("T1-001",), stage=2, **extra):
    base = {"id": tid, "stage": stage, "targetAgent": "agent-coder",
            "dependsOn": list(deps), "path": f"src/main/java/x/{export.split('.')[-1]}.java",
            "kind": "code", "layer": "domain", "feature": None, "export": export,
            "intent": "pin the surface", "project": "p"}
    base.update(extra)
    return base


def demand_verdict(demands, missing=(), status="compile_error"):
    return {"status": status, "exit_code": 1,
            "missing_symbols": list(missing),
            "member_demands": list(demands),
            "failures": [], "counts": {}, "excerpt": []}

# --- A. attribution on structured fields -------------------------------------

t_box = task(export="com.x.Channel")
v = demand_verdict([{"member": "compute(java.lang.Object)", "owner": "Channel", "kind": "method"}])
check("A1 method demand on MY exported type charges me",
      tdd_engine._own_type_member_demand(v, t_box) is True)
check("A2 demand owned by a peer does not charge me",
      tdd_engine._own_type_member_demand(
          demand_verdict([{"member": "save(Order)", "owner": "Repository", "kind": "method"}]), t_box) is False)

# nested-vs-top-level: class demand whose member is NOT resolvable elsewhere -> mine
(ROOT / "blackboard" / "queue" / "T2-001-p.json").write_text(json.dumps(t_box))
nested = demand_verdict([{"member": "Row", "owner": "Channel", "kind": "class"}])
check("A3 unresolvable class located in my type is a nested gap I own",
      tdd_engine._own_type_member_demand(nested, t_box) is True)
# the same phrasing where the member IS someone else's export -> not mine
peer = task(tid="T2-002", export="Row")
(ROOT / "blackboard" / "queue" / "T2-002-p.json").write_text(json.dumps(peer))
check("A4 class located in my type that another unit exports is NOT my gap",
      tdd_engine._own_type_member_demand(nested, t_box) is False)

# hole detector subtraction
holes_plain = tdd_engine._unresolvable_missing({"status": "compile_error", "missing_symbols": ["Ghost"],
                                                "member_demands": []}, t_box)
check("A5 unattributable missing type is a scheduling hole", holes_plain == ["Ghost"], str(holes_plain))
holes_cond = tdd_engine._unresolvable_missing(
    {"status": "compile_error", "missing_symbols": ["Row2"],
     "member_demands": [{"member": "Row2", "owner": "Channel", "kind": "class"}]}, t_box)
check("A6 demand-attached symbol is conditional, not a hole (false-abort guard)",
      holes_cond == [], str(holes_cond))

# problem_kinds drives cascade-vs-structural and the moving-port deferral WITHOUT
# the engine reading a single message phrase (fields present, text would lie).
KINDS = {"status": "compile_error", "exit_code": 1, "missing_symbols": [],
         "member_demands": [], "failures": [], "counts": {},
         "excerpt": [f"{ROOT}/proj/src/main/java/x/Channel.java:[4,1] totally unrelated prose"],
         "problem_kinds": [{"file": "Channel.java", "line": 4, "kind": "supertype",
                            "supertypes": ["Gateway"]}]}
kind_task = task(tid="T2-601", export="Chan", path="src/main/java/x/Channel.java",
                 deps=("T1-601",))
(ROOT / "blackboard" / "queue" / "T1-601-p.json").write_text(json.dumps(
    task(tid="T1-601", export="ChanTest", deps=[], stage=1,
         path="src/test/java/x/ChanTest.java")))
(ROOT / "blackboard" / "queue" / "T2-601-p.json").write_text(json.dumps(kind_task))
(ROOT / "blackboard" / "queue" / "T2-602-p.json").write_text(json.dumps(
    task(tid="T2-602", export="Gateway")))
check("A7 supertype problem defers while the peer owns the port (field-driven)",
      tdd_engine._peer_supertype_conflict(kind_task, KINDS) is True)
check("A7b full precedence: own-file structural + peer supertype -> DEFER, not charge",
      tdd_engine._blocked_by_peers(KINDS, kind_task) is True)
check("A8 cascade kind keeps own-file blame from charging the victim",
      tdd_engine._own_structural(
          {**KINDS, "problem_kinds": [{"file": "Channel.java", "line": 4,
                                       "kind": "missing-symbol"}]},
          "Channel.java", []) is False)
check("A9 structural kind charges my own file",
      tdd_engine._own_structural(KINDS, "Channel.java", []) is True)

# A10/A11: the materialized-port relaxation - deferring an adapter whose port is
# ALREADY on disk deadlocks both gates on the same compile error (live board).
from pathlib import Path as _Path
(_Path(ROOT) / "proj" / "src" / "main" / "java" / "x").mkdir(parents=True, exist_ok=True)
port_file = _Path(ROOT) / "proj" / "src" / "main" / "java" / "x" / "Gateway.java"
check("A10 deferral intact while the port is NOT on the tree",
      tdd_engine._blocked_by_peers(KINDS, kind_task) is True)
port_file.write_text("package x;\npublic interface Gateway { void send(); }\n")
check("A11 materialized port + own structural defect -> CHARGE, not defer",
      tdd_engine._blocked_by_peers(KINDS, kind_task) is False)
port_file.unlink()

# --- B. charge precedence: own frozen test first ------------------------------
(ROOT / "blackboard" / "queue" / "T1-050-p.json").write_text(
    json.dumps(task(tid="T1-050", export="BoxTest", deps=[], stage=1,
                   path="src/test/java/x/WidgetTest.java")))
blamed = {"status": "compile_error", "exit_code": 1, "missing_symbols": [],
          "member_demands": [], "failures": [], "counts": {},
          "excerpt": [f"{ROOT}/proj/src/test/java/x/WidgetTest.java:[10,3] error: incompatible types: A cannot be converted to B"],
          }
mine = task(tid="T2-010", export="Widget", deps=("T1-050",))
other = task(tid="T2-011", export="Widget", deps=("T1-999",))
check("B1 the frozen test's own implementer is charged for its compile errors",
      tdd_engine._blocked_by_peers(blamed, mine) is False)
check("B2 peers defer on a conversion defect they do not own",
      tdd_engine._blocked_by_peers(blamed, other) is True)

# --- C. wave gate sharing ------------------------------------------------------
calls = []


def scripted_tool(*results):
    seq = list(results)

    def fake(root, command, timeout):
        calls.append(command)
        return seq.pop(0) if seq else {"status": "not_run", "reason": "script exhausted"}
    return fake


DECISIVE = {"status": "compile_error", "exit_code": 1, "classes": {},
            "missing_symbols": ["Ghost"], "failures": [], "counts": {},
            "excerpt": ["cannot find symbol: class Ghost"]}
test_gate._tool_result = scripted_tool(DECISIVE)
reason_a, res_a = test_gate.wave_gate_verdict(task(tid="T2-501", project="pc1"), "./mvnw -Dtest=X test")
n = len(calls)
reason_b, res_b = test_gate.wave_gate_verdict(task(tid="T2-502", project="pc1"), "./mvnw -Dtest=Y test")
check("C1 decisive module failure is shared: sibling costs ZERO builds",
      len(calls) == n and reason_b and "compile_error" in reason_b, str(calls))
test_gate._tool_result = scripted_tool(
    {"status": "error", "exit_code": 1, "classes": {}, "excerpt": ["boot crash"]})
reason_e, _ = test_gate.wave_gate_verdict(task(tid="T2-503", project="pc2"), "./mvnw -Dtest=Z test")
check("C2 boot crash without class evidence is decisive too", reason_e and "status=error" in reason_e)
test_gate._tool_result = scripted_tool({"status": "passed", "exit_code": 0, "classes": {}},
                                       {"status": "passed", "exit_code": 0,
                                        "classes": {"com.x.WTest": "passed"}, "counts": {"run": 2}})
reason_g, res_g = test_gate.wave_gate_verdict(task(tid="T2-504", project="pc3"), "./mvnw -Dtest=WTest test")
check("C3 per-class evidence keeps routing (green selector)",
      reason_g is None and res_g.get("status") == "passed")

# --- D. attempt ledger + granted informed attempts -----------------------------
settings.MAX_TDD_RETRIES = 3
SAME = ("test gate: status=compile_error; exit_code=1; blame: a.java:[2,5] cannot find symbol "
        "symbol: method compute(String) location: class com.x.Chan")
LEDGER_TASK = task(tid="T2-900", export="Chan")
payload = ROOT / "blackboard" / "coder-changes" / "T2-900.json"


def drive(verdicts, payload_present=False, reset=True):
    state = {"sessions": [], "queue": list(verdicts)}

    def invoke(feedback):
        if payload_present and feedback is None:
            return True, ""
        state["sessions"].append(feedback)
        payload.write_text('{"id": "T2-900"}')
        return True, ""

    def verify():
        return state["queue"].pop(0) if state["queue"] else (False, "script exhausted")
    if reset:
        attempt_ledger.clear("T2-900")
        payload.unlink(missing_ok=True)
    ok, reason = tdd_engine.execute_with_tdd(LEDGER_TASK, invoke, verify)
    if not ok and not payload_present:
        payload.unlink(missing_ok=True)
    return len(state["sessions"]), ok, reason, state["sessions"], attempt_ledger.read("T2-900")


n1, ok1, r1, f1, led1 = drive([(False, SAME), (False, SAME), (False, SAME)])
check("D1 in-run identical repeats stop at 2 sessions", n1 == 2 and "signature identical" in r1)
# exhausted ledger WITH payload on disk (the run18 trap): the granted attempt must
# replay for free and then bill exactly ONE informed session - never burn on blind skip.
sig_same = tdd_engine._failure_signature(SAME)
LEDGER_CONTRACT = attempt_ledger.contract_hash(LEDGER_TASK)
attempt_ledger.write("T2-900", contract=LEDGER_CONTRACT, consumed=3,
                     signature=sig_same, fed="some-older-shown-failure")
payload.write_text('{"id": "T2-900"}')
n2, ok2, r2, f2, led2 = drive([(False, SAME), (False, SAME)], payload_present=True, reset=False)
check("D2 granted attempt: free replay then ONE informed session", n2 == 1 and f2 and f2[0] is not None, str(f2))
check("D3 the shown failure is marked fed", led2.get("fed") == sig_same)
payload.write_text('{"id": "T2-900"}')
n3, ok3, r3, f3, led3 = drive([(False, SAME)], payload_present=True, reset=False)
check("D4 repeat of a SHOWN failure on an unchanged world closes with ZERO sessions",
      n3 == 0 and "already informed" in r3)
attempt_ledger.clear("T2-900")
n5, ok5, r5, f5, led5 = drive([(True, "")])
check("D5 green clears the ledger", led5 == {} and n5 == 1)

# --- E. auto-grant selection ---------------------------------------------------
attempt_ledger.clear("T2-900")
err = ROOT / "blackboard" / "error"
for f in list(err.glob("*.json")) + list((ROOT / "blackboard" / "queue").glob("T2-9*.json")):
    f.unlink(missing_ok=True)
base_ledger = attempt_ledger.contract_hash(LEDGER_TASK)
# budgeted quarantine
attempt_ledger.write("T2-910", contract=base_ledger, consumed=1, signature="sigA", fed="sigZ")
(err / "T2-910-p.json").write_text(json.dumps(task(tid="T2-910", export="A910")))
# exhausted, failure shown, world unmoved (fresh memo)
attempt_ledger.write("T2-911", contract=base_ledger, consumed=3, signature="sigB", fed="sigB")
(err / "T2-911-p.json").write_text(json.dumps(task(tid="T2-911", export="A911")))
fp = json.dumps({"memo_version": 5, "payload": 0,
                 "tree": test_gate._tree_fingerprint(ROOT / "proj")}, sort_keys=True)
(settings.GATE_CACHE_DIR / "T2-911.json").write_text(json.dumps({"fingerprint": fp, "reason": "x", "result": None}))
# exhausted, shown, world MOVED (no memo)
attempt_ledger.write("T2-912", contract=base_ledger, consumed=3, signature="sigC", fed="sigC")
(err / "T2-912-p.json").write_text(json.dumps(task(tid="T2-912", export="A912")))
# grants at cap, unshown
attempt_ledger.write("T2-913", contract=base_ledger, consumed=3, signature="sigD", fed="sigE",
                     grants=settings.MAX_INFORMED_GRANTS)
(err / "T2-913-p.json").write_text(json.dumps(task(tid="T2-913", export="A913")))
# cascade whose blocker is being granted in this batch
(err / "T2-914-p.json").write_text(json.dumps(
    task(tid="T2-914", export="A914", deps=["T2-910"], error="dependsOn T2-910 not resolvable")))
# cascade whose blocker is still quarantined
(err / "T2-915-p.json").write_text(json.dumps(
    task(tid="T2-915", export="A915", deps=["T2-913"], error="dependsOn T2-913 not resolvable")))
# cascade-shaped quarantine WITH an unspent-budget ledger: must be governed by the
# dependency, never by the budget rule (the live T2-041 ping-pong bug)
attempt_ledger.write("T2-915", contract=base_ledger, consumed=0, signature="sigF")
tdd_engine.task_queue.load_valid_tasks = lambda: ([], set())
restored = tdd_engine.autogrant_progressing()
check("E1 budgeted unit restored", "T2-910" in restored)
check("E2 shown+exhausted on UNMOVED world stays quarantined", "T2-911" not in restored)
check("E3 shown+exhausted on MOVED world restored (replay will tell)", "T2-912" in restored)
check("E4 grants cap holds even for unshown failures", "T2-913" not in restored)
check("E5 cascade unwinds in the same batch", "T2-914" in restored)
check("E6 cascade behind a staying quarantine stays", "T2-915" not in restored)
check("E7 cascade shape outranks the budget rule (no ping-pong)", "T2-915" not in restored)

# --- G. plan-time API contract table: the seed-002 root cause, pinned as a gate -------
import tasks as tasks_mod
import task_queue

PROVIDER_HINTS = {"package": "com.demo.cfg", "implements": [], "dependencies": [],
                  "methods": [{"signature": "window()", "returns": "Duration"}]}
provider = dict(task(tid="T2-704", export="Cfg", deps=()), ast_hints=PROVIDER_HINTS)
(providers := ROOT / "blackboard" / "draft-g0.json").write_text(json.dumps([provider]))
check("G0 provider lands", task_queue.emit_tasks([str(providers)]) is None)
HINTS = {"package": "com.demo.ledger", "implements": ["UseCase"],
         "dependencies": [{"type": "Cfg", "task_id": "T2-704"}],
         "methods": [{"signature": "record(SampleEvent e)", "returns": "Mono<Receipt>"}]}
full2 = dict(task(tid="T2-700", export="Service", deps=()), ast_hints=HINTS)
check("G1 complete contract table accepted at planning",
      tasks_mod.validate(full2, {}, planning=True) is None,
      str(tasks_mod.validate(full2, {}, planning=True)))
check("G2 stage-2 task without the table refused at planning",
      "ast_hints" in str(tasks_mod.validate(task(tid="T2-701", export="Svc2", deps=()),
                                            {}, planning=True)))
check("G3 resume mode still loads the legacy 11-key task",
      tasks_mod.validate(task(tid="T2-702", export="Svc3", deps=()), {}, planning=False) is None)
no_surf = dict(full2); no_surf["ast_hints"] = {**HINTS, "methods": []}
check("G4 implements-without-methods refused (single API truth)",
      "methods" in str(tasks_mod.validate(no_surf, {}, planning=True)))
unpinned = dict(full2); unpinned["ast_hints"] = {**HINTS, "dependencies": ["Cfg"]}
check("G5 unpinned collaborator refused",
      "dependencies" in str(tasks_mod.validate(unpinned, {}, planning=True)))
draft = ROOT / "blackboard" / "draft-g.json"
draft.write_text(json.dumps([full2]))
rc_g = task_queue.emit_tasks([str(draft)])
check("G6 end-to-end emit accepts the compliant task",
      rc_g is None and (settings.QUEUE_DIR / "T2-700-p.json").is_file(), str(rc_g))
bare = dict(task(tid="T2-703", export="Svc4", deps=()))
draft.write_text(json.dumps([bare]))
rc_g2 = task_queue.emit_tasks([str(draft)])
check("G7 emit refuses the prose-only plan (the seed-002 shape)",
      bool(rc_g2) and "ast_hints" in str(rc_g2)
      and not (settings.QUEUE_DIR / "T2-703-p.json").is_file(), str(rc_g2))
# cross-task: a pinned producer MUST spell its surface (the TelemetryProperties case)
empty_provider = dict(task(tid="T2-705", export="Props", deps=()),
                      ast_hints={"package": "com.demo.cfg", "implements": [],
                                 "dependencies": [], "methods": []})
consumer = dict(task(tid="T2-706", export="User", deps=("T2-705",)),
                ast_hints={"package": "com.demo.app", "implements": [],
                           "dependencies": [{"type": "Props", "task_id": "T2-705"}],
                           "methods": [{"signature": "run()", "returns": "void"}]})
draft.write_text(json.dumps([empty_provider, consumer]))
rc_x = task_queue.emit_tasks([str(draft)])
check("G8 pinned producer with empty methods refuses the whole batch",
      bool(rc_x) and "T2-705" in str(rc_x) and "methods is empty" in str(rc_x), str(rc_x))
fixed_provider = dict(empty_provider)
fixed_provider["ast_hints"] = {**fixed_provider["ast_hints"],
                               "methods": [{"signature": "windowSeconds()", "returns": "long"}]}
draft.write_text(json.dumps([fixed_provider, consumer]))
rc_ok = task_queue.emit_tasks([str(draft)])
check("G9 batch lands once the producer spells its surface",
      rc_ok is None and (settings.QUEUE_DIR / "T2-705-p.json").is_file(), str(rc_ok))
dangling = dict(task(tid="T2-707", export="Later", deps=()),
                ast_hints={"package": "com.demo.app", "implements": [],
                           "dependencies": [{"type": "Ghost", "task_id": "T2-899"}],
                           "methods": [{"signature": "go()", "returns": "void"}]})
draft.write_text(json.dumps([dangling]))
rc_d = task_queue.emit_tasks([str(draft)])
check("G10 dangling collaborator pin refused at emit",
      bool(rc_d) and "T2-899" in str(rc_d), str(rc_d))

import builtins
import contextlib
import io
import re

import pipeline   # patches the tagged-line clock at import (entry-module side effect)

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    builtins.print("[run ] tagged line")
    builtins.print("plain passthrough")
lines = buf.getvalue().splitlines()
check("F1 tagged lines carry an HH:MM:SS clock",
      bool(re.match(r"^\d{2}:\d{2}:\d{2} \[run \] tagged line$", lines[0])), lines[0])
check("F2 untagged output passes through untouched", lines[1] == "plain passthrough", lines[1])

import status
buf2 = io.StringIO()
with contextlib.redirect_stdout(buf2):
    rc = status.main()
out2 = buf2.getvalue()
check("F3 status renders the board without error", rc == 0 and "quarantined" in out2, out2[:160])

# --- H. tester batch + collaborator truth injected in the message ------------
import prompts

def t1task(tid, export, path, hints=None):
    base = {"id": tid, "targetAgent": settings.STAGE_AGENTS[1], "stage": settings.TESTER_STAGE,
            "dependsOn": ["T0-001"], "path": path, "kind": "test", "layer": "domain",
            "feature": None, "export": export, "intent": "test it", "project": "p"}
    if hints is not None:
        base["ast_hints"] = hints
    return base

peers = [t1task(f"T1-80{i}", ch, f"src/test/java/{ch.lower()}/{ch}Test.java")
         for i, ch in enumerate("ABCD")]
for p_ in peers:
    (settings.QUEUE_DIR / f"{p_['id']}-p.json").write_text(json.dumps(p_))
sib = tdd_engine._testless_peers(peers[0])
check("H1 testless peers gathered, self first",
      sib[0]["id"] == "T1-800" and {"T1-801", "T1-802", "T1-803"} <= {s["id"] for s in sib},
      str([s["id"] for s in sib]))
done_test = ROOT / "proj" / "src" / "test" / "java" / "b"
done_test.mkdir(parents=True, exist_ok=True)
(done_test / "BTest.java").write_text("// exists now\n")
sib2 = tdd_engine._testless_peers(peers[0])
check("H2 units with a test on disk leave the batch",
      "T1-801" not in {s["id"] for s in sib2} and {"T1-802", "T1-803"} <= {s["id"] for s in sib2},
      str([s["id"] for s in sib2]))
(done_test / "BTest.java").unlink()

pinning = {"package": "com.demo.shared", "implements": [],
           "dependencies": [{"type": "Widget", "task_id": "T2-800"}], "methods": []}
widget = {"id": "T2-800", "targetAgent": settings.STAGE_AGENTS[2], "stage": 2,
          "dependsOn": [], "path": "src/main/java/x/Widget.java", "kind": "code",
          "layer": "domain", "feature": None, "export": "Widget", "intent": "build",
          "project": "p",
          "ast_hints": {"package": "com.demo.shared", "implements": [], "dependencies": [],
                        "methods": [{"signature": "Widget(int w)", "returns": ""}]}}
(settings.QUEUE_DIR / "T2-800-p.json").write_text(json.dumps(widget))
msg_h = prompts.build_task_message(t1task("T1-805", "Echo", "src/test/java/e/EchoTest.java",
                                          hints=pinning))
check("H3 tester message inlines the collaborator API truth (T1-018 fix)",
      "Collaborators" in msg_h and "Widget(int w)" in msg_h)
orphan = t1task("T1-806", "Foxtrot", "src/test/java/f/FTest.java",
                hints={"package": "x", "implements": [],
                       "dependencies": [{"type": "Ghost", "task_id": "T2-899"}], "methods": []})
msg_o = prompts.build_task_message(orphan)
check("H4 unsatisfiable pin surfaces as a plan hole, never a guess",
      "NOT FOUND" in msg_o and "PLAN HOLE" in msg_o)
bm = prompts.build_batch_message(peers[:4])
check("H5 batch duty is stage-correct for testers",
      "BATCH MODE" in bm and "write the test" in bm
      and "produce and persist a payload" not in bm)
check("H6 tester batch budget scales per unit",
      settings.call_budget(settings.STAGE_AGENTS[1], 4)
      == settings.TESTER_BATCH_FIRST_CALLS + 4 * settings.TESTER_BATCH_CALLS_PER_UNIT)
check("H7 single tester budget unchanged by the batch model",
      settings.call_budget(settings.STAGE_AGENTS[1], 1)
      == settings.AGENT_CALL_BUDGETS[settings.STAGE_AGENTS[1]])

import dispatchers

(proj := ROOT / "proj").mkdir(exist_ok=True)
(proj / "pom.xml").write_text("<project/>\n")
rdir = proj / "src" / "test" / "java" / "r"
rdir.mkdir(parents=True, exist_ok=True)
(rdir / "RecoveredTest.java").write_text("// test on disk, red record never written\n")
rt = t1task("T1-810", "Recovered", "src/test/java/r/RecoveredTest.java")
seen = {}
orig_run = dispatchers.subprocess.run
def fake_run(cmd, **kw):
    joined = " ".join(str(c) for c in cmd)
    key = "tool" if "run-test-tool" in joined else "writer" if "write-red-phase" in joined else "other"
    seen[key] = joined
    class R:
        returncode = 0
        stdout = json.dumps({"status": "compile_error", "exit_code": 1, "missing_symbols": [],
                             "failures": [], "counts": {}, "classes": {}})
    return R()
dispatchers.subprocess.run = fake_run
derived = dispatchers.derive_red_phase(rt)
dispatchers.subprocess.run = orig_run
check("H8 missing red is DERIVED from the test file (zero sessions)",
      derived and "tool" in seen and "-Dtest=RecoveredTest" in seen["tool"]
      and "writer" in seen, str(seen))
ghost = t1task("T1-811", "Nothing", "src/test/java/r/NothingTest.java")
check("H9 no test on disk: recovery refuses, session path preserved",
      dispatchers.derive_red_phase(ghost) is False)
# command synthesis: the tester's own four shapes, from path alone
check("H10 scoped command shapes derived from path+markers",
      test_gate.command_from_test_path("src/test/java/x/ATest.java", proj) == "./mvnw -Dtest=ATest test"
      and test_gate.command_from_test_path("src/a_test.py", proj).startswith("python3 -m pytest")
      and test_gate.command_from_test_path("src/a.rb", proj) is None)

bad_names = [n for n, c in CHECKS if not c]
print(f"\nENGINE-DECISIONS SUITE: {len(CHECKS) - len(bad_names)}/{len(CHECKS)}")
print("FAILED:", bad_names if bad_names else "none")
sys.exit(1 if bad_names else 0)
