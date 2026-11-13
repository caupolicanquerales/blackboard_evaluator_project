"""Gauntlet: orchestrator decision rules on synthetic boards.

Every fixture here is distilled from a real incident, but the inputs are structured
fields only - the engine must never be tested (or allowed) to read compiler output.
Coverage:
  A. attribution: own-type demands, nested-vs-top-level, hole subtraction
  B. charge precedence: the frozen test's OWN implementer answers first
  C. wave gate sharing: tree-wide decisive verdicts cost ONE build per state
  D. attempt ledger + grants: informed-attempt semantics, zero-session closeouts
  E. auto-grant: self-healing selection, storm guards intact
  G. plan validity at emit: the API table gate + seed-002 D1..D3 refusal classes
     (unowned file duties, config-less runtime plans, request-encoding
     contradictions, null-rejection without semantics)
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
          "blackboard/coder-changes", "blackboard/weave-results",
          "blackboard/queue", "blackboard/error",
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

# A12-A14: context-boot bean demands (the live T2-012 deadlock): while a PENDING peer
# owns the demanded bean the booting unit defers (zero cost, payload stays woven - a
# quarantine revert would hole the whole test tree); it is charged only when the bean
# is its OWN export, or when no pending peer owns it (honest, capped surfacing).
BEANY = {"status": "assertion_failure", "exit_code": 1, "missing_symbols": [],
         "member_demands": [], "failures": [{"test": "x.RepoTest.append", "message": "boom"}],
         "counts": {"run": 3, "failures": 0, "errors": 3},
         "bean_demands": ["com.x.SampleValidator"]}
validator_task = task(tid="T2-061", export="com.x.SampleValidator")
repo_task = task(tid="T2-062", export="com.x.EventLogRepository")
(ROOT / "blackboard" / "queue" / "T2-061-p.json").write_text(json.dumps(validator_task))
(ROOT / "blackboard" / "queue" / "T2-062-p.json").write_text(json.dumps(repo_task))
check("A12 boot demand for a pending peer's bean DEFERS the booting unit (message would lie)",
      tdd_engine._blocked_by_peers({**BEANY, "status": "assertion_failure"}, repo_task) is True)
check("A13 boot demand for the unit's OWN exported type CHARGES (make my type a bean)",
      tdd_engine._blocked_by_peers(BEANY, validator_task) is False)
(ROOT / "blackboard" / "queue" / "T2-061-p.json").unlink()
(ROOT / "blackboard" / "complete" / "T2-061-p.json").write_text(json.dumps(validator_task))
check("A14 boot demand no pending peer owns CHARGES (surfacing, not deadlock)",
      tdd_engine._blocked_by_peers(BEANY, repo_task) is False)
(ROOT / "blackboard" / "complete" / "T2-061-p.json").unlink()

# A15-A17: the quarantine revert policy (live T2-003 domain freeze): reverting a
# payload the completed suite PROVED harmless deletes a type peers' files import and
# holes the whole tree; reverting stays exactly for compile poison and unknown verdicts.
keep_task = task(tid="T2-070", export="com.x.SampleValidator")
(ROOT / "blackboard" / "coder-changes" / "T2-070.json").write_text(
    json.dumps({"targetFile": "src/main/java/x/SampleValidator.java"}))
(ROOT / "blackboard" / "weave-results" / "T2-070.json").write_text(json.dumps({"status": "ok"}))
test_gate._write_memo(keep_task, "red", {"status": "assertion_failure", "exit_code": 1,
                                         "failures": [], "counts": {}})
check("A15 assertion_failure + payload woven in a COMPLETED suite = proven harmless -> KEEP",
      tdd_engine._payload_proven_harmless(keep_task) is True)
test_gate._write_memo(keep_task, "red", {"status": "compile_error", "exit_code": 1,
                                         "missing_symbols": ["X"], "failures": [], "counts": {}})
check("A16 compile_error verdict -> classic revert (poison or unknown)",
      tdd_engine._payload_proven_harmless(keep_task) is False)
(ROOT / "blackboard" / "weave-results" / "T2-070.json").unlink()
test_gate._write_memo(keep_task, "red", {"status": "assertion_failure", "exit_code": 1,
                                         "failures": [], "counts": {}})
check("A17 nothing spliced into the tree -> nothing to keep",
      tdd_engine._payload_proven_harmless(keep_task) is False)

# A18: the T2-003 domain freeze. The demanded class IS on the tree (woven by its
# producer, gate or no gate): what is missing is a REGISTRATION someone can write in
# their own file - deferring every demanding unit (including the plan's wiring unit)
# deadlocks the domain, so CHARGE; ledger caps bound the bystander churn.
(ROOT / "blackboard" / "queue" / "T2-061-p.json").write_text(json.dumps(validator_task))
(ROOT / "proj" / "src" / "main" / "java" / "x" / "SampleValidator.java").write_text(
    "package x;\npublic class SampleValidator { }\n")
check("A18 materialized bean class + pending peer owner -> CHARGE (no domain deadlock)",
      tdd_engine._blocked_by_peers(BEANY, repo_task) is False)
(ROOT / "proj" / "src" / "main" / "java" / "x" / "SampleValidator.java").unlink()
check("A18b same demand, class NOT materialized -> defer stays (waiting can resolve it)",
      tdd_engine._blocked_by_peers(BEANY, repo_task) is True)

# A19: attribution must read the FULL blame evidence. The wave digest's selector-filtered
# excerpt hid the peer-owned wiring file, and the demand-owner unit was billed 3 attempts
# for a call site it does not own (seed-002 rerun 14:03, T2-017).
wiring = task(tid="T2-077", export="TelemetryWiringConfiguration")
(ROOT / "blackboard" / "queue" / "T2-077-p.json").write_text(json.dumps(wiring))
PEER_OWNED = {"status": "compile_error", "exit_code": 1,
              "missing_symbols": ["ReorderWindow(com.pulse.properties)"],
              "member_demands": [{"member": "ReorderWindow(properties)", "owner": "ReorderWindow",
                                  "kind": "constructor"}],
              "failures": [], "counts": {}, "excerpt": [],
              "excerpt_all": [f"{ROOT}/proj/src/main/java/w/TelemetryWiringConfiguration.java:"
                              "32,32 ] constructor ReorderWindow cannot be applied to given types"]}
demanded = task(tid="T2-076", export="com.x.ReorderWindow", deps=("T1-076",))
check("A19 every blamed MAIN file belongs to a queued peer -> demand owner DEFERS",
      tdd_engine._blocked_by_peers(PEER_OWNED, demanded) is True)
(ROOT / "blackboard" / "queue" / "T2-077-p.json").unlink()

# A20: the partial-tree storm (2026-11-12 14:2x). A quarantined sibling whose payload
# was DISCARDED leaves its class absent from the tree - every bystander gate would pay
# 3 blind charges against that hole. It now holds the wave gate like an unwoven peer.
(ROOT / "blackboard" / "error" / "T2-620-p.json").write_text(
    json.dumps(task(tid="T2-620", export="Ghost")))
check("A20 dead sibling with discarded payload holds the wave gate",
      "T2-620" in tdd_engine._sibling_payloads_pending(kind_task))
(ROOT / "blackboard" / "error" / "T2-621-p.json").write_text(json.dumps(task(tid="T2-621", export="Kept")))
(ROOT / "blackboard" / "coder-changes" / "T2-621.json").write_text('{"id": "T2-621"}')
check("A21 dead sibling whose payload SURVIVES does not hold the wave (class is woven)",
      "T2-621" not in tdd_engine._sibling_payloads_pending(kind_task))
(ROOT / "blackboard" / "coder-changes" / "T2-621.json").unlink()
check("A22 the same sibling holds the wave once its payload is gone",
      "T2-621" in tdd_engine._sibling_payloads_pending(kind_task))
(ROOT / "blackboard" / "error" / "T2-620-p.json").unlink()
(ROOT / "blackboard" / "error" / "T2-621-p.json").unlink()

# A23: the deferral CYCLE (14:58 live). The wiring unit's OWN file structurally broken
# ("constructor ... cannot be applied") while a peer class it must call is still pending:
# deferring on the pending symbol while the class owner defers on the wiring file parks
# BOTH forever. Own structural blame always charges - nothing defers it.
(ROOT / "blackboard" / "queue" / "T2-623-p.json").write_text(json.dumps(task(
    tid="T2-623", export="TelemetryWiringConfiguration",
    path="src/main/java/com/pulsestream/telemetry/shared/config/TelemetryWiringConfiguration.java")))
(ROOT / "blackboard" / "queue" / "T2-624-p.json").write_text(json.dumps(
    task(tid="T2-624", export="ReorderWindow")))
CYCLE = {"status": "compile_error", "exit_code": 1, "missing_symbols": ["ReorderWindow"],
         "member_demands": [], "failures": [], "counts": {},
         "excerpt": [f"{ROOT}/proj/src/main/java/com/pulsestream/telemetry/shared/config/"
                     "TelemetryWiringConfiguration.java:32,32 ] constructor ReorderWindow "
                     "cannot be applied to given types"]}
wiring_task = task(tid="T2-623", export="TelemetryWiringConfiguration",
                   path="src/main/java/com/pulsestream/telemetry/shared/config/TelemetryWiringConfiguration.java")
check("A23 own-file STRUCTURAL blame charges even while a peer symbol is pending (cycle breaker)",
      tdd_engine._blocked_by_peers(CYCLE, wiring_task) is False)
for f in ("T2-623-p.json", "T2-624-p.json"):
    (ROOT / "blackboard" / "queue" / f).unlink()

# A24: a WEAVER TOOL rejection (malformed export, unparseable YAML payload) must surface
# as weave-reject - bounced back to the coder WITHOUT charging an attempt. Live defect:
# "Cannot derive a Java type name from export: final CorrelationContext" was charged as
# 3 unit failures although the unit's code never compiled at all.
import dispatchers
(ROOT / "blackboard" / "coder-changes" / "T2-630.json").write_text(
    json.dumps({"id": "T2-630", "targetFile": "src/main/java/x/CorrelationContext.java"}))
_dispatch_real = dispatchers._dispatch
dispatchers._dispatch = lambda *a, **k: (
    1, "ERROR: Cannot derive a Java type name from export: final CorrelationContext",
    "code-weaver failed: ERROR: Cannot derive a Java type name from export: final CorrelationContext")
reason_24 = dispatchers.run_code_weaver_dispatcher(
    task(tid="T2-630", export="CorrelationContext"))
dispatchers._dispatch = _dispatch_real
(ROOT / "blackboard" / "coder-changes" / "T2-630.json").unlink()
check("A24 weaver shape-rejection returns 'weave-reject:' (bounce class, attempt-free)",
      bool(reason_24) and reason_24.startswith("weave-reject:"), str(reason_24))

# A25/A26: contract-regression reopen (live 17:04). A completed unit's OWN main file
# stopped compiling when a later weave moved a binding it consumes: the file is the
# root defect, but completed tasks are invisible to every deferral rule - live peers
# wait forever and the drain can only stall. The owner goes back to the queue.
(ROOT / "blackboard" / "complete" / "T2-660-p.json").write_text(json.dumps(
    task(tid="T2-660", export="OldThing", path="src/main/java/x/OldThing.java")))
REGRESSION = {"status": "compile_error", "exit_code": 1, "missing_symbols": [],
              "member_demands": [], "failures": [], "counts": {},
              "excerpt": [f"{ROOT}/proj/src/main/java/x/OldThing.java:[9,20] non-static "
                          "method contextKey() cannot be referenced from a static context"]}
live_661 = task(tid="T2-661", export="Consumer61")
check("A25 completed-owner compile blame reopens it to queue (stall breaker)",
      tdd_engine._reopen_contract_regression(REGRESSION, live_661) is True
      and (ROOT / "blackboard" / "queue" / "T2-660-p.json").is_file()
      and not (ROOT / "blackboard" / "complete" / "T2-660-p.json").is_file())
check("A26 same state reopens nothing once the owner is live (no churn)",
      tdd_engine._reopen_contract_regression(REGRESSION, live_661) is False)
(ROOT / "blackboard" / "queue" / "T2-660-p.json").unlink()

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
check("D6 grants count PAID sessions only: D2 billed one, D4's zero-close spent none",
      int(led3.get("grants") or 0) == 1, str(led3.get("grants")))
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

# --- G.11..G17 plan validity emit-refusals (FINAL-EVALUATION-seed002 §6 items 1+3) ---
def gtask(tid, export, stage, deps=(), intent="pin the surface", project="p", path=None,
          hints=None):
    t = {"id": tid, "targetAgent": settings.STAGE_AGENTS[stage], "stage": stage,
         "dependsOn": list(deps), "path": path or f"src/main/java/x/{export}.java",
         "kind": settings.STAGE_KINDS[stage][0], "layer": "domain", "feature": None,
         "export": export, "intent": intent, "project": project}
    if hints is not None:
        t["ast_hints"] = hints
    return t


def encoding_pair(pid, param_type, test_intent):
    hints = {"package": "com.demo.ing", "implements": [], "dependencies": [],
             "methods": [{"signature": f"receive({param_type} body)", "returns": "void"}]}
    t1 = gtask(f"T1-{pid}", "ReceiverTest", 1,
               path=f"src/test/java/ing/ReceiverTest.java", intent=test_intent,
               project=pid, hints=hints)
    t2 = gtask(f"T2-{pid}", "Receiver", 2, deps=(f"T1-{pid}",), project=pid, hints=hints)
    return [t1, t2]


def emit(batch):
    draft.write_text(json.dumps(batch))
    return task_queue.emit_tasks([str(draft)])


rc = emit(encoding_pair("740", "Flux<EventDto>", "POSTs a JSON array of DTOs, expects 202"))
check("G11 Flux request parameter vs 'JSON array' test intent REJECTED at emit (D2)",
      bool(rc) and "streamed" in str(rc), str(rc))
rc = emit(encoding_pair("741", "Flux<EventDto>", "sends streamed JSON documents, one per line"))
check("G12 aligned pair accepted: Flux + streamed-document wording",
      rc is None and (settings.QUEUE_DIR / f"T2-741-741.json").is_file(), str(rc))
rc = emit(encoding_pair("742", "List<EventDto>", "POSTs a single JSON array of DTOs"))
check("G13 aligned pair accepted: List + array wording",
      rc is None, str(rc))
rc = emit(encoding_pair("743", "List<EventDto>", "POSTs streamed JSON documents"))
check("G14 List request parameter vs streamed-documents intent REJECTED",
      bool(rc) and "streamed documents" in str(rc), str(rc))

HINT_NO_METHODS = {"package": "com.demo.cfg", "implements": [], "dependencies": [],
                   "methods": [{"signature": "reorderWindow()", "returns": "Duration"}]}
cfg_only = gtask("T2-744", "IngestService", 2, project="cfgp", hints=HINT_NO_METHODS,
                 intent="bind operational values through @ConfigurationProperties")
rc = emit([cfg_only])
check("G15 config-duty without a config unit REJECTED (D3/L1-L3)",
      bool(rc) and "runtime configuration artifact" in str(rc), str(rc))
cfg_ok = [dict(cfg_only),
          gtask("T2-745", "application", 2, project="cfgp", hints=HINT_NO_METHODS,
                path="src/main/resources/application.yml",
                intent="runtime configuration: reorder-window=60s and metric bounds exactly as "
                       "the seed states them (literal values live here, nowhere else)")]
draft2 = ROOT / "blackboard" / "draft-g15.json"
draft2.write_text(json.dumps(cfg_ok))
rc = task_queue.emit_tasks([str(draft2)])
check("G16 same plan accepted once the config unit is scheduled with the literals",
      rc is None and (settings.QUEUE_DIR / "T2-745-cfgp.json").is_file(), str(rc))

orphan_file = gtask("T2-746", "Writer", 2, project="ownp", hints=HINT_NO_METHODS,
                    intent="store events; Also provide application.yml entries for retention")
rc = emit([orphan_file])
check("G17 intent naming an UNOWNED file artifact REJECTED ('also provide' root pattern)",
      bool(rc) and "no task path owns" in str(rc), str(rc))

sample_hints = {"package": "com.demo.dom", "implements": [], "dependencies": [],
                "methods": [{"signature": "TelemetrySample(String deviceId, String status)",
                             "returns": ""}]}
null_plain = gtask("T2-747", "TelemetrySample", 2, project="nullp", hints=sample_hints,
                   intent="value object; compact constructor rejects blank deviceId and null status")
rc = tasks_mod.validate(null_plain, {}, planning=True)
check("G18 null-rejecting intent without semantics notes REJECTED (D1)",
      bool(rc) and "semantics" in str(rc), str(rc))
null_marked = dict(null_plain)
null_marked["ast_hints"] = {**sample_hints, "methods": [
    {**sample_hints["methods"][0],
     "semantics": "status is never null: pre-validation state is TelemetryStatus.UNVALIDATED, "
                  "the constant this unit ships"}]}
check("G19 same contract accepted once semantics name the initial state",
      tasks_mod.validate(null_marked, {}, planning=True) is None,
      str(tasks_mod.validate(null_marked, {}, planning=True)))
check("G20 methods entries stay shape-checked: unknown keys refused",
      "signature" in str(tasks_mod.validate_ast_hints(
          {**sample_hints, "methods": [{"signature": "go()", "returns": "void", "note": "x"}]})))

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

# --- R. import repair reads CODE, never prose ---------------------------------
# The run6 self-inflicted tree break: a word inside a COMMENT ('// A lone late
# sample...') resolved to a unique classpath class and the engine inserted a real
# import into a MAIN file between gates, freezing every unit on compile_error.
rroot = ROOT / "repairtree"
(rroot / "src" / "main" / "java" / "x").mkdir(parents=True)
(rroot / "src" / "test" / "java" / "x").mkdir(parents=True)
holder = rroot / "src" / "main" / "java" / "x" / "Holder.java"
holder.write_text("package x;\n\n// A lone late sample mentions LocalDate in prose.\n"
                  "public class Holder { String s = \"InOrder\"; }\n")
user = rroot / "src" / "test" / "java" / "x" / "HolderTest.java"
user.write_text("package x;\n\npublic class HolderTest { Zeta w; }\n")
_real_ext = test_gate.external_type_index
test_gate.external_type_index = lambda root: {"A": ("org.checker.qual.A",),
                                              "LocalDate": ("java.time.LocalDate",),
                                              "Zeta": ("com.ext.Zeta",)}
try:
    test_gate.repair_test_imports(rroot)
finally:
    test_gate.external_type_index = _real_ext
check("R1 comment/string words never trigger import insertion (run6 tree-break pin)",
      "org.checker.qual" not in holder.read_text()
      and "java.time" not in holder.read_text()
      and "com.ext" not in holder.read_text(), holder.read_text()[:220])
check("R2 repair still fires for a real bare use in code (no over-correction)",
      "import com.ext.Zeta;" in user.read_text(), user.read_text()[:220])

# --- P. prose-vs-table SHAPE refusal (inspection 2026-11-13 F2: the T2-014 pair) ----
UTILITY_TABLE = {"package": "com.demo.obs", "implements": [], "dependencies": [],
                 "methods": [{"signature": "String contextKey()", "returns": "String"},
                             {"signature": "String headerName()", "returns": "String"}]}
utility = dict(task(tid="T2-760", export="CorrelationContext", deps=(),
                    intent="Final utility class holding the correlation key contract. "
                           "Private constructor."),
               ast_hints=UTILITY_TABLE)
rc_p = tasks_mod.validate(utility, {}, planning=True)
check("G21 prose pins a private constructor while the table binds instance members "
      "REJECTED at planning (seed-002 F2 impossible pair)", bool(rc_p) and "UNCONSTRUCTIBLE" in rc_p,
      str(rc_p))
utility_static = dict(utility)
utility_static["ast_hints"] = {**UTILITY_TABLE, "methods": [
    {"signature": "static String contextKey()", "returns": "String"},
    {"signature": "static String headerName()", "returns": "String"}]}
check("G22 the same utility prose accepted once the table binds statics (coherent shape)",
      tasks_mod.validate(utility_static, {}, planning=True) is None,
      str(tasks_mod.validate(utility_static, {}, planning=True)))
# cross-unit half: consumer prose in static form vs producer's instance table
draft_p = ROOT / "blackboard" / "draft-p.json"
cons_bad = gtask("T2-763", "Reader", 2, project="p", deps=("T2-704",),
                 intent="reads the value via Cfg.window() at boot",
                 hints={"package": "com.demo.read", "implements": [],
                        "dependencies": [{"type": "Cfg", "task_id": "T2-704"}],
                        "methods": [{"signature": "read()", "returns": "int"}]})
draft_p.write_text(json.dumps([cons_bad]))
rc_p2 = task_queue.emit_tasks([str(draft_p)])
check("G23 consumer prose calling a pinned producer's INSTANCE member in static form "
      "REJECTED at emit (the F2 call-shape drift)",
      bool(rc_p2) and "STATIC form" in str(rc_p2), str(rc_p2))
cons_ok = gtask("T2-764", "Reader2", 2, project="p", deps=("T2-704",),
                intent="reads the value from the injected cfg's window() at boot",
                hints={"package": "com.demo.read", "implements": [],
                       "dependencies": [{"type": "Cfg", "task_id": "T2-704"}],
                       "methods": [{"signature": "read()", "returns": "int"}]})
draft_p.write_text(json.dumps([cons_ok]))
check("G24 same pair accepted when the prose names the injected instance call",
      task_queue.emit_tasks([str(draft_p)]) is None, str(rc_p2))

# --- Q. quarantine rollback must not hole MAIN sources (inspection 2026-11-13 F1) ---
(ROOT / "proj" / "src" / "main" / "java" / "x").mkdir(parents=True, exist_ok=True)
holder_m = ROOT / "proj" / "src" / "main" / "java" / "x" / "WiredHolder.java"
holder_m.write_text("package x;\nimport x.VanishedArtifact;\n"
                    "public class WiredHolder { VanishedArtifact a; }\n")
completed_rec = task(tid="T2-770", export="WiredHolder", deps=())
completed_rec["path"] = "src/main/java/x/WiredHolder.java"
(ROOT / "blackboard" / "complete" / "T2-770-p.json").write_text(json.dumps(completed_rec))
rolled = task(tid="T2-771", export="VanishedArtifact", deps=())
rolled["path"] = "src/main/java/x/VanishedArtifact.java"
check("A27 rolled-back artifact NAMES the main file still importing it",
      tdd_engine._dangling_main_consumers(rolled)
      == ["src/main/java/x/WiredHolder.java"],
      str(tdd_engine._dangling_main_consumers(rolled)))
notice_q = tdd_engine._surface_rollback_hole(rolled)
check("A28 the rollback REOPENS the completed consumer's owner (hole becomes adjudicated)",
      "T2-770" in notice_q and (ROOT / "blackboard" / "queue" / "T2-770-p.json").is_file(),
      notice_q)
holder_m.unlink()
(ROOT / "blackboard" / "queue" / "T2-770-p.json").unlink(missing_ok=True)

# --- S. the hollow-boot guard: composition root must SEE the code (F3) -------------
import assembly as assembly_mod
svc = ROOT / "svc" / "hollow-demo"
(svc / "src" / "main" / "java" / "com" / "a").mkdir(parents=True)
(svc / "src" / "main" / "java" / "com" / "z").mkdir(parents=True)
(svc / "src" / "test" / "java" / "com" / "a").mkdir(parents=True)
(svc / "pom.xml").write_text("<project><artifactId>hollow-demo</artifactId></project>")
(svc / "src" / "test" / "java" / "com" / "a" / "AppTests.java").write_text(
    "package com.a;\n@SpringBootTest\nclass AppTests {}\n")
app = svc / "src" / "main" / "java" / "com" / "a" / "App.java"
app.write_text("package com.a;\n@SpringBootApplication\npublic class App {\n"
               "  public static void main(String[] a) {}\n}\n")
(svc / "src" / "main" / "java" / "com" / "z" / "Svc.java").write_text(
    "package com.z;\npublic class Svc {}\n")


def hollow_problems():
    contract = assembly_mod.detect(svc)
    return [p for p in (contract or {}).get("problems", []) if "cannot see" in p]


def hollow_problems_all():
    contract = assembly_mod.detect(svc)
    return list((contract or {}).get("problems", []))


check("S1 assembly gate refuses a composition root that cannot see the code packages "
      "(green boot over an empty context is not boot, seed-002 F3)",
      bool(hollow_problems()), str(assembly_mod.detect(svc)["problems"]))
app.write_text('package com.a;\n@SpringBootApplication(scanBasePackages = "com")\n'
               "public class App {\n  public static void main(String[] a) {}\n}\n")
check("S2 the same tree accepted once the entry DECLARES scan coverage",
      not hollow_problems(), str(hollow_problems()))
app.write_text("package com.a;\n@SpringBootApplication\npublic class App {\n"
               "  public static void main(String[] a) {}\n}\n")
(svc / "src" / "main" / "java" / "com" / "z" / "Svc.java").write_text(
    "package com.a.deep;\npublic class Svc {}\n")
check("S3 same tree accepted when every package sits under the entry root",
      not hollow_problems(), str(hollow_problems()))
# S4/S5 pin the 13:45 live class: scanBasePackages fixed the MAIN visibility but two
# slice units stayed red forever - package-upwards discovery ignores the marker.
(svc / "src" / "test" / "java" / "com" / "other").mkdir(parents=True)
(svc / "src" / "test" / "java" / "com" / "other" / "SliceCheckTest.java").write_text(
    "package com.other;\n@SpringBootTest\nclass SliceCheckTest {}\n")
app.write_text('package com.a;\n@SpringBootApplication(scanBasePackages = "com")\n'
               "public class App {\n  public static void main(String[] a) {}\n}\n")
check("S4 a declared scan marker does NOT waive @SpringBootTest package-upwards discovery "
      "(the exact 13:45 hollow-fix the gate accepted)",
      any("UPWARDS" in p for p in hollow_problems_all()), str(hollow_problems_all()))
app.write_text("package com;\n@SpringBootApplication\npublic class App {\n"
               "  public static void main(String[] a) {}\n}\n")
check("S5 moving the composition root to the shared package ancestor waives both halves",
      not hollow_problems_all(), str(hollow_problems_all()))

# --- T. assembly must be scheduled even though the scaffold lands DURING the
#    drain, and a domain that never booted must be reported, not skipped.
#    (2026-11-13 rerun 13:33 live shape: queue 0, 35 complete, zero T4 records -
#    the run ended having never run a boot gate.)
import pipeline as pipeline_mod
sched = ROOT / "sched"
tree = sched / "services" / "demo2"
(tree / "src" / "main" / "java" / "com" / "a").mkdir(parents=True)
(tree / "src" / "test" / "java" / "com" / "a").mkdir(parents=True)
(tree / "pom.xml").write_text("<project/>")
(tree / "src" / "test" / "java" / "com" / "a" / "AppTests.java").write_text(
    "package com.a;\n@SpringBootTest\nclass AppTests {}\n")
(tree / "src" / "main" / "java" / "com" / "a" / "App.java").write_text(
    "package com.a;\n@SpringBootApplication\npublic class App {\n"
    "  public static void main(String[] a) {}\n}\n")
_orig_root = workspace.get_project_root
workspace.get_project_root = lambda: sched
try:
    lines_asm = []
    assembly_mod.ensure_tasks(report=lines_asm.append)
    queued4 = sorted(f.name for f in settings.QUEUE_DIR.glob("T4-*.json"))
    check("T1 assembly is queued once the scaffold EXISTS (late-schedule, not launch-time)",
          len(queued4) == 1 and "demo2" in queued4[0], str(queued4) + " " + str(lines_asm))
    assembly_mod.ensure_tasks(report=lines_asm.append)
    check("T2 re-scheduling stays idempotent (no duplicate boot tasks)",
          len(list(settings.QUEUE_DIR.glob("T4-*.json"))) == 1)
    (settings.QUEUE_DIR / queued4[0]).unlink()  # leave no assembly task on this board
finally:
    workspace.get_project_root = _orig_root
# terminal tree report, board-driven:
st2 = dict(task(tid="T2-780", export="SvcX", deps=()))
(ROOT / "blackboard" / "complete" / "T2-780-p.json").write_text(json.dumps(st2))
report = pipeline_mod._terminal_tree_report(gate=lambda rec: (True, ""))
check("T3 a domain with no completed boot is reported NEVER BOOTED (silent-exit shape died)",
      any(line.startswith("[tree   ] p:") and "NEVER BOOTED" in line for line in report),
      str(report))
(ROOT / "blackboard" / "complete" / "T4-781-p.json").write_text(
    json.dumps(dict(task(tid="T4-781", export="App", deps=(), stage=4,
                        targetAgent="agent-assembly", path="src/main/java/x/App.java"))))
report = pipeline_mod._terminal_tree_report(gate=lambda rec: (False, "dangling import"))
check("T4 completed-but-red boot surfaces as RED DELIVERED TREE via the real gate",
      any("DELIVERED TREE IS BROKEN" in line for line in report), str(report))
report = pipeline_mod._terminal_tree_report(gate=lambda rec: (True, ""))
check("T5 green boot gate yields the GREEN tree line",
      any(line.startswith("[tree   ] p:") and "GREEN - the delivered tree" in line
          for line in report), str(report))

# --- U. the 13:51 double-defect: path-guard over assembly moves + zombie records ---
moved = dict(task(tid="T4-785", export="App", deps=(), stage=4, targetAgent="agent-assembly",
                  kind="assembly", layer="root",
                  path="src/main/java/com/x/gone/TelemetryApp.java"))
check("U1 assembly is judged ONLY by its boot gate: a legitimate composition-root move "
      "no longer quarantines as 'was not created' (13:51 false-positive)",
      tdd_engine._missing_artifact_problem(moved, True) is None,
      str(tdd_engine._missing_artifact_problem(moved, True)))
late_tester = dict(task(tid="T1-786", export="GhostTest", deps=(), stage=1,
                       targetAgent="agent-tester", path="src/test/java/x/AbsentTest.java"))
check("U2 the same guard still refuses a tester that never wrote its file",
      "not created" in str(tdd_engine._missing_artifact_problem(late_tester, True)),
      str(tdd_engine._missing_artifact_problem(late_tester, True)))
zombie = ROOT / "blackboard" / "error" / "T4-787-p.json"
zombie.write_text(json.dumps(dict(moved, id="T4-787")))
draft_u = ROOT / "blackboard" / "draft-u.json"
draft_u.write_text(json.dumps([dict(moved, id="T4-787")]))
check("U3 re-emitting an id SUPERSEDES its zombie quarantine record (one id, one record)",
      task_queue.emit_tasks([str(draft_u)]) is None and not zombie.exists()
      and (settings.QUEUE_DIR / "T4-787-p.json").is_file(),
      f"zombie={zombie.exists()}")

# --- V. strategy step-log CLAIM coverage (2026-11-13: 5 planned, 0 owned, 0 logged,
#    every gate green - vocabulary overlap proves nothing, a claim field can) ---------
(ROOT / "blackboard" / "complete" / "execution-strategy-sl.json").write_text(json.dumps(
    {"slug": "sl", "observability": {
        "correlation_key": "requestId",
        "step_logs": ["order accepted (outcome)", "stock reserved"],
        "audit_trail": {"record_fields": ["actor", "action", "outcome", "timestamp",
                                          "correlationId"],
                        "port": "AuditTrail.record(AuditEntry)"},
        "metrics": [{"name": "orders.accepted", "type": "counter", "tags": ["outcome"]}],
        "export": {"logs": "structured ecs file sink", "metrics": "scrape endpoint",
                   "dependency_rule": "boot passes with the collector absent"}}}))
sl_hints = {"package": "com.demo.sl", "implements": [], "dependencies": [],
            "methods": [{"signature": "go()", "returns": "void"}]}
sl_task = gtask("T2-790", "Orders", 2, project="sl", hints=sl_hints)
rc_v = emit([sl_task])
check("V1 a strategy promising step logs with ZERO claiming units is REJECTED at emit",
      bool(rc_v) and "claimed by NO stage-2 unit" in str(rc_v), str(rc_v))
own_a = dict(gtask("T2-791", "Orders2", 2, project="sl", hints=sl_hints))
own_a["observability"] = {"step_logs": ["Order Accepted (outcome)"]}   # normalized match
own_b = dict(gtask("T2-792", "Stock2", 2, project="sl", hints=sl_hints))
own_b["observability"] = {"step_logs": ["stock reserved"]}
rc_v = emit([own_a, own_b])
check("V2 full verbatim coverage (case/space-normalized) ACCEPTS the batch",
      rc_v is None and (settings.QUEUE_DIR / "T2-791-sl.json").is_file(), str(rc_v))
own_c = dict(gtask("T2-793", "Ghost2", 2, project="sl", hints=sl_hints,
                   deps=("T2-791",)))
own_c["observability"] = {"step_logs": ["ghost logged"]}
rc_v = emit([own_c])
check("V3 claiming a step log the strategy never planned is REJECTED",
      bool(rc_v) and "never planned" in str(rc_v), str(rc_v))
dup_a = dict(gtask("T2-794", "DupA", 2, project="sl", hints=sl_hints))
dup_a["observability"] = {"step_logs": ["order accepted (outcome)"]}
dup_b = dict(gtask("T2-795", "DupB", 2, project="sl", hints=sl_hints))
dup_b["observability"] = {"step_logs": ["order accepted (outcome)"]}
rc_v = emit([dup_a, dup_b])
check("V4 a double-claimed step log names both rivals and is REJECTED",
      bool(rc_v) and "exactly" in str(rc_v) and "one owner" in str(rc_v), str(rc_v))
no_obs = gtask("T2-796", "Plain", 2, project="legacy", hints=sl_hints)
check("V5 projects WITHOUT a promised step-log surface skip the rule (legacy-safe)",
      emit([no_obs]) is None)
(ROOT / "blackboard" / "complete" / "execution-strategy-bare.json").write_text(
    json.dumps({"slug": "bare", "bounded_contexts": ["x"]}))
rc_v = emit([gtask("T2-798", "Bare1", 2, project="bare", hints=sl_hints)])
check("V7 THE FLOOR IS UNCONDITIONAL: a strategy with no observability object at all is "
      "REJECTED at task emit - the old skip was the loophole one layer deeper",
      bool(rc_v) and "NO `observability` object" in str(rc_v), str(rc_v))
(ROOT / "blackboard" / "complete" / "execution-strategy-half.json").write_text(json.dumps(
    {"slug": "half", "observability": {"correlation_key": "cid",
                                       "step_logs": ["x done"],
                                       "audit_trail": {"port": "Audit.record(A)"}}}))
rc_v = emit([gtask("T2-799", "Half1", 2, project="half", hints=sl_hints)])
check("V8 a half floor is rejected naming the missing surfaces - all five are mandatory",
      bool(rc_v) and "floor surfaces" in str(rc_v) and "metrics" in str(rc_v), str(rc_v))
base_h = task(tid="T2-797", export="Hashing", deps=())
h0 = attempt_ledger.contract_hash(base_h)
h1 = attempt_ledger.contract_hash({**base_h, "observability": None})
h2 = attempt_ledger.contract_hash({**base_h, "observability": {"step_logs": ["x"]}})
check("U4 attempt-ledger continuity: an absent claim hashes IDENTICALLY to the pre-field "
      "contract (no budget reset on resumed boards); a real claim moves the contract",
      h0 == h1 and h2 != h0, f"{h0[:8]} {h1[:8]} {h2[:8]}")

bad_names = [n for n, c in CHECKS if not c]
print(f"\nENGINE-DECISIONS SUITE: {len(CHECKS) - len(bad_names)}/{len(CHECKS)}")
print("FAILED:", bad_names if bad_names else "none")
sys.exit(1 if bad_names else 0)
