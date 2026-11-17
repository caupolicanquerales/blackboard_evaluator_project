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
    "package com.a;\n@SpringBootTest\nclass AppTests {\n  void entryRoundTrip() { WebTestClient client = null; client = null; }\n}\n")
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
    "package com.a;\n@SpringBootTest\nclass AppTests {\n  void entryRoundTrip() { WebTestClient client = null; client = null; }\n}\n")
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
        "metrics": [{"name": "orders.accepted", "type": "counter", "tags": ["outcome"]},
                    {"name": "stock.reserved", "type": "counter", "tags": []}],
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
# V6 (live 2026-11-16 09:50): phase 1 emits the stage-0 scaffold task BEFORE any
# decomposition exists. With claims demanded there, T0 is unemittable by construction -
# the architect burned 19 calls (budget 12) and the run died [fatal] no scaffold task.
# The floor check must STILL fire on a stage-0-only emit; only the claim layer waits.
FULL_FLOOR = {"correlation_key": "cid", "step_logs": ["packet received (IngressPacket)"],
              "audit_trail": {"port": "Audit.record(A)"},
              "metrics": [{"name": "packets.received", "type": "counter", "tags": []},
                          # placeholder counter so floors that swap in the generic
                          # "x done" step stay paired under rule (u) layer 1
                          {"name": "jobs.done", "type": "counter", "tags": []}],
              "export": {"logs": "ecs file sink"}}
(ROOT / "blackboard" / "complete" / "execution-strategy-phase.json").write_text(
    json.dumps({"slug": "phase", "observability": FULL_FLOOR}))
t0_phase = gtask("T0-801", "Scaffold", 0, project="phase")
t0_phase["layer"] = "root"
rc_v = emit([t0_phase])
check("V6 a stage-0-only emit with ZERO stage-2 tasks on the board is ACCEPTED "
      "(phase-order hole: claims demanded before decomposition can exist killed the run)",
      rc_v is None and (settings.QUEUE_DIR / "T0-801-phase.json").is_file(), str(rc_v))
rc_v = emit([gtask("T2-802", "Unclean", 2, project="phase", hints=sl_hints)])
check("V6b the first stage-2 emit arms the claim gate: an unclaimed step log is REJECTED",
      bool(rc_v) and "claimed by NO stage-2 unit" in str(rc_v), str(rc_v))
(ROOT / "blackboard" / "complete" / "execution-strategy-nofloor.json").write_text(
    json.dumps({"slug": "nofloor", "bounded_contexts": ["x"]}))
t0_nofloor = gtask("T0-803", "ScaffoldB", 0, project="nofloor")
t0_nofloor["layer"] = "root"
rc_v = emit([t0_nofloor])
check("V6c the FLOOR layer is not weakened: a stage-0 emit whose strategy on disk has "
      "no observability object is still REJECTED (the agent CAN fix that in-session)",
      bool(rc_v) and "NO `observability` object" in str(rc_v), str(rc_v))
import pipeline as _pipe_v6
(ROOT / "blackboard" / "complete" / "execution-strategy-resume.json").write_text(
    json.dumps({"slug": "resume", "observability": FULL_FLOOR}))
_gap_a = _pipe_v6._strategy_phase_gaps(["resume"])
t0_ok = gtask("T0-805", "Scaffold", 0, project="resume")
t0_ok["layer"] = "root"
emit([t0_ok])
_gap_b = _pipe_v6._strategy_phase_gaps(["resume"])
check("V9 a strategy on disk with NO scaffold task reads as an OPEN phase-1 gap (the "
      "resume state after V6's incident no longer silently skips then dies [fatal])",
      _gap_a == ["resume"] and _gap_b == [], f"{_gap_a} {_gap_b}")
# V10+ (live 2026-11-16 10:15): the plan pinned the driver package `...intake.interface`
# - a Java reserved word. The weaver can never render it, the frozen test can never
# compile: 3 units + 3 evaluators quarantined, ~6 coder sessions spent on an
# unfixable contract. Reserved segments must die at EMIT, in the planned language.
(ROOT / "blackboard" / "complete" / "execution-strategy-kw.json").write_text(json.dumps(
    {"slug": "kw", "tech_stack": {"language": "Java 21"},
     "observability": FULL_FLOOR}))
kw_hints = {"package": "com.demo.kw.interface", "implements": [], "dependencies": [],
            "methods": [{"signature": "go()", "returns": "void"}]}
kw_bad = gtask("T2-810", "com.demo.kw.interface.Resp", 2, project="kw", hints=kw_hints)
kw_bad["path"] = "src/main/java/com/demo/kw/interface/Resp.java"
kw_bad["observability"] = {"step_logs": ["packet received (IngressPacket)"]}
rc_v = emit([kw_bad])
check("V10 a stage-2 task whose package segment is reserved in the PLANNED language "
      "(Java `interface`) is REFUSED at emit naming the field and the word",
      bool(rc_v) and "reserved words" in str(rc_v) and "interface" in str(rc_v), str(rc_v))
kw_ok = json.loads(json.dumps(kw_bad))
kw_ok["id"] = "T2-811"
kw_ok["ast_hints"]["package"] = "com.demo.kw.api"
kw_ok["export"] = "com.demo.kw.api.Resp"
kw_ok["path"] = "src/main/java/com/demo/kw/api/Resp.java"
rc_v = emit([kw_ok])
check("V10b the renamed segment (api) is ACCEPTED - the gate refuses only the collision",
      rc_v is None, str(rc_v))
(ROOT / "blackboard" / "complete" / "execution-strategy-py.json").write_text(json.dumps(
    {"slug": "py", "tech_stack": {"language": "Python 3.12"},
     "observability": {**FULL_FLOOR, "step_logs": ["x done"]}}))
py_bad = gtask("T2-812", "app.src.lambda.handler", 2, project="py", hints={
    "package": "app.src.lambda", "implements": [], "dependencies": [],
    "methods": [{"signature": "go()", "returns": "None"}]})
py_bad["path"] = "src/app/src/lambda/handler.py"
py_bad["observability"] = {"step_logs": ["x done"]}
rc_v = emit([py_bad])
check("V11 the gate follows the strategy's language: `lambda` is reserved in Python "
      "and refused there, and PATH segments are checked too",
      bool(rc_v) and "lambda" in str(rc_v), str(rc_v))
py_ok = gtask("T2-813", "app.src.core.handler", 2, project="py", hints={
    "package": "app.src.core", "implements": [], "dependencies": [],
    "methods": [{"signature": "go()", "returns": "None"}]})
py_ok["path"] = "src/app/src/core/handler.py"
py_ok["observability"] = {"step_logs": ["x done"]}
rc_v = emit([py_ok])
check("V11b a legal Python path/package pair is ACCEPTED", rc_v is None, str(rc_v))
(ROOT / "blackboard" / "complete" / "execution-strategy-ctx.json").write_text(json.dumps(
    {"slug": "ctx", "tech_stack": {"language": "Java 21"},
     "observability": {**FULL_FLOOR, "step_logs": ["x done"]}}))
ctx_task = gtask("T2-814", "com.demo.ctx.record.Handler", 2, project="ctx", hints={
    "package": "com.demo.ctx.record", "implements": [], "dependencies": [],
    "methods": [{"signature": "go()", "returns": "void"}]})
ctx_task["path"] = "src/main/java/com/demo/ctx/record/Handler.java"
ctx_task["observability"] = {"step_logs": ["x done"]}
rc_v = emit([ctx_task])
check("V12 CONTEXTUAL Java identifiers stay legal (record/var/yield are NOT reserved "
      "words - over-refusing a valid plan is the same defect wearing the other uniform)",
      rc_v is None, str(rc_v))
(ROOT / "blackboard" / "complete" / "execution-strategy-nolang.json").write_text(
    json.dumps({"slug": "nolang", "observability": {**FULL_FLOOR,
                                                    "step_logs": ["x done"]}}))
nl_task = gtask("T2-815", "com.demo.nl.interface.X", 2, project="nolang", hints={
    "package": "com.demo.nl.interface", "implements": [], "dependencies": [],
    "methods": [{"signature": "go()", "returns": "void"}]})
nl_task["path"] = "src/main/java/com/demo/nl/interface/X.java"
nl_task["observability"] = {"step_logs": ["x done"]}
rc_v = emit([nl_task])
check("V12b a strategy with no language (legacy, unknown stack) SKIPS the gate",
      rc_v is None, str(rc_v))
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

# --- V13. TERMINAL SUITE gate (live 2026-11-16 10:52): the T3-007 evaluator refactored
#    EventRevision and the T4 assembler rewrote flyway.url AFTER the last wave gate -
#    two peers' frozen tests broke with no gate left to notice, the board idled at
#    queue 0 on a red tree. The quiet-board suite must reopen the COMPLETED owners
#    (T3 mirror rides along), leave quarantined owners alone, and NAME ownerless reds.
for _n, _stage, _dep in (("T1-820", 1, None), ("T1-821", 1, None)):
    (ROOT / "blackboard" / "complete" / f"{_n}-ts.json").write_text(json.dumps(
        gtask(_n, f"ts.{_n[-3:]}", _stage, project="ts",
              path=f"src/test/java/ts/{'Widget' if _n.endswith('20') else 'Sock'}Test.java")))
(ROOT / "blackboard" / "complete" / "T2-820-ts.json").write_text(json.dumps(
    gtask("T2-820", "ts.Widget", 2, deps=("T1-820",), project="ts")))
(ROOT / "blackboard" / "complete" / "T3-820-ts.json").write_text(json.dumps(
    gtask("T3-820", "ts.Widget", 3, deps=("T2-820",), project="ts")))
(ROOT / "blackboard" / "error" / "T2-821-ts.json").write_text(json.dumps(
    gtask("T2-821", "ts.Sock", 2, deps=("T1-821",), project="ts")))
(ROOT / "blackboard" / "complete" / "T4-822-ts.json").write_text(json.dumps(
    gtask("T4-822", "ts.App", 4, deps=(), project="ts")))
(ROOT / "blackboard" / "complete" / "T1-823-ts.json").write_text(json.dumps(
    gtask("T1-823", "ts.GearTest", 1, project="ts",
          path="src/test/java/ts/GearTest.java")))
(ROOT / "blackboard" / "complete" / "T2-823-ts.json").write_text(json.dumps(
    gtask("T2-823", "ts.Gear", 2, deps=("T1-823",), project="ts",
          path="src/main/java/ts/Gear.java")))
(ROOT / "blackboard" / "red-phase" / "T1-820.json").write_text(json.dumps(
    {"executed": True, "status": "compile_error", "command": "./mvnw -Dtest=WidgetTest test"}))
(ROOT / "blackboard" / "red-phase" / "T1-821.json").write_text(json.dumps(
    {"executed": True, "status": "compile_error", "command": "./mvnw -Dtest=SockTest test"}))
test_gate._tool_result = lambda root, command, timeout: (
    {"status": "passed", "exit_code": 0, "classes": {}, "counts": {}}
    if "compile" in command else
    {"status": "assertion_failure", "exit_code": 1, "counts": {"run": 4, "failures": 3},
     "classes": {"ts.WidgetTest": "failed", "ts.SockTest": "failed",
                 "x.GhostTest": "failed", "ts.GearTest": "passed"},
     "excerpt": ["java.lang.IllegalArgumentException: deviceId must not be blank",
                 "at com.ts.Gear.<init>(Gear.java:9)"],
     "failures": [{"test": "ts.WidgetTest.g", "message": "expected 0 but was 1"}]})
import contextlib as _cl
import io as _io
_buf = _io.StringIO()
with _cl.redirect_stdout(_buf):
    _ts_reopen = tdd_engine.terminal_suite_gate()
_ts_out = _buf.getvalue()
with _cl.redirect_stdout(_io.StringIO()):
    _ts_again = tdd_engine.terminal_suite_gate()
check("V13 a red delivered-suite class whose owner is COMPLETED reopens the owner "
      "(and its T3 mirror) instead of an idle board lying green",
      "T2-820" in _ts_reopen and "T4-822" in _ts_reopen and "T2-823" in _ts_reopen
      and (settings.QUEUE_DIR / "T2-820-ts.json").is_file()
      and not (settings.COMPLETE_DIR / "T2-820-ts.json").is_file()
      and (settings.QUEUE_DIR / "T3-820-ts.json").is_file()
      and (settings.QUEUE_DIR / "T4-822-ts.json").is_file(),
      f"{_ts_reopen} {_ts_out[:180]}")
check("V13c an ownerless red class is NAMED and handed to stage 4 (the only unit whose "
      "contract is the whole tree), once per tree state - not board silence",
      "GhostTest has NO producing unit" in _ts_out, _ts_out[:400])
check("V13b a red owned by a QUARANTINED unit is left to the retry path (no double claim)",
      (settings.ERROR_DIR / "T2-821-ts.json").is_file()
      and not (settings.QUEUE_DIR / "T2-821-ts.json").is_file())
check("V13d the second quiet pass re-reads the memoized verdict and reopens nothing "
      "(converged or not, the same tree never rebuilds twice)",
      _ts_again == [], str(_ts_again))

# --- W. the MECHANIZED plan rules (k)/(m)/(n): the machine half of the 2026-11-16
#    artifact findings (orphaned rule service F1, discarded boolean signal F2,
#    double registration duty F8). Fixtures use the exact incident shapes.
wl_hints = {"package": "com.w", "implements": [], "dependencies": [],
            "methods": [{"signature": "Flux<Event> out()", "returns": "Flux<Event>"}]}
island = gtask("T2-900", "Feeder", 2, project="wl", path="src/main/java/w/Feeder.java",
              hints=wl_hints)
rc_w = emit([island])
check("W1 a unit whose table PUBLISHES a stream and nobody pins it is REFUSED at emit "
      "(the F1 orphan: registered, green-tested, never executed)",
      bool(rc_w) and "PUBLISHES a stream" in str(rc_w), str(rc_w)[:200])
consumer_hints = {"package": "com.w", "implements": [],
                  "dependencies": [{"type": "Feeder", "task_id": "T2-900"}],
                  "methods": [{"signature": "go()", "returns": "void"}]}
consumer = gtask("T2-901", "Drain", 2, deps=("T2-900",), project="wl",
                 path="src/main/java/w/Drain.java", hints=consumer_hints)
rc_w = emit([island, consumer])
check("W2 the same source ACCEPTS once a real consumer pins it (dependency edge, "
      "not a mention)", rc_w is None, str(rc_w)[:200])
wiring_hints = {"package": "com.w", "implements": [],
                "dependencies": [{"type": "Feeder2", "task_id": "T2-902"}],
                "methods": [{"signature": "Feeder2 feeder2()", "returns": "Feeder2"}]}
island2 = gtask("T2-902", "Feeder2", 2, project="wm",
                  path="src/main/java/w/Feeder2.java", hints={
    "package": "com.w", "implements": [], "dependencies": [],
    "methods": [{"signature": "Flux<Event> out()", "returns": "Flux<Event>"}]})
wiring = gtask("T2-903", "Wiring", 2, deps=("T2-902",), project="wm",
               path="src/main/java/w/Wiring.java", hints=wiring_hints)
rc_w = emit([island2, wiring])
check("W2b a WIRING unit's pin does NOT count as consumption - the config unit that "
      "FACTORIES the orphan is exactly today's F1 shape (factory edge != consumer)",
      bool(rc_w) and "PUBLISHES a stream" in str(rc_w), str(rc_w)[:200])
boundary = gtask("T2-904", "Feeder4", 2, project="wn",
                 path="src/main/java/w/Feeder4.java",
                 intent="Publishes the window Flux for out-of-process analytics "
                        "subscribers; no in-tree consumer.", hints={
                     "package": "com.w", "implements": [], "dependencies": [],
                     "methods": [{"signature": "Flux<Event> out()", "returns": "Flux<Event>"}]})
rc_w = emit([boundary])
check("W3 the boundary exemption is honored ONLY when the UNIT's own intent declares "
      "the out-of-process surface (rule (i)'s vocabulary, per source)",
      rc_w is None, str(rc_w)[:200])
sig_hints = {"package": "com.w", "implements": [], "dependencies": [],
             "methods": [{"signature": "boolean publish(Event e)", "returns": "boolean"}]}
sig = gtask("T2-905", "Pub", 2, project="wp", path="src/main/java/w/Pub.java",
           hints=sig_hints)
rc_w = emit([sig])
check("W4 a tabled SIGNAL return (boolean / Mono<Boolean>) with no `semantics` naming "
      "both outcomes is REFUSED (F2: an unowned false branch is a silent drop)",
      bool(rc_w) and "SIGNAL" in str(rc_w), str(rc_w)[:200])
fixed_hints = json.loads(json.dumps(sig_hints))
fixed_hints["methods"][0]["semantics"] = ("true = buffered for the appender; false = the "
                                          "bounded sink dropped it, the caller must reject 503")
rc_w = emit([gtask("T2-906", "Pub6", 2, project="wp", path="src/main/java/w/Pub6.java",
               hints=fixed_hints)])
check("W4b the same signal ACCEPTS once `semantics` spells both outcomes", rc_w is None,
      str(rc_w)[:200])
mono_sig = {"package": "com.w", "implements": [], "dependencies": [],
            "methods": [{"signature": "Mono<Boolean> append(Event e)", "returns": "Mono<Boolean>"}]}
rc_w = emit([gtask("T2-907", "App7", 2, project="wq", path="src/main/java/w/App7.java",
               hints=mono_sig)])
check("W4c the wrapped reactive form Mono<Boolean> is a signal too (the F3 dropped-"
      "duplicate path rode exactly this spelling)", bool(rc_w) and "SIGNAL" in str(rc_w),
      str(rc_w)[:200])
owner8 = gtask("T2-908", "Widget8", 2, project="wr",
               path="src/main/java/w/Widget8.java",
               intent="Implementation unit; registers itself as a managed component.",
               hints={"package": "com.w", "implements": [], "dependencies": [],
                      "methods": [{"signature": "go()", "returns": "void"}]})
maker8 = gtask("T2-909", "Wiring8", 2, deps=("T2-908",), project="wr",
               path="src/main/java/w/Wiring8.java", hints={
    "package": "com.w", "implements": [],
    "dependencies": [{"type": "Widget8", "task_id": "T2-908"}],
    "methods": [{"signature": "Widget8 widget8()", "returns": "Widget8"}]})
rc_w = emit([owner8, maker8])
check("W5 a product claimed by TWO registration duties (own intent registers itself + "
      "a wiring factory returns it) is REFUSED - factory XOR self-register (F8)",
      bool(rc_w) and "TWO registration" in str(rc_w), str(rc_w)[:200])
owner8b = dict(owner8, id="T2-920", export="Widget9",
               path="src/main/java/w/Widget9.java", intent="Plain unit; the wiring "
               "unit is the only registration duty.")
owner8b["ast_hints"] = json.loads(json.dumps(owner8["ast_hints"]))
maker8b = dict(maker8, id="T2-921", export="Wiring9",
               path="src/main/java/w/Wiring9.java")
maker8b["dependsOn"] = ["T2-920"]
maker8b["ast_hints"] = json.loads(json.dumps(maker8["ast_hints"]))
maker8b["ast_hints"]["dependencies"][0] = {"type": "Widget9", "task_id": "T2-920"}
maker8b["ast_hints"]["methods"][0] = {"signature": "Widget9 widget9()", "returns": "Widget9"}
rc_w = emit([owner8b, maker8b])
check("W5b ONE registration mechanism (factory only) is the accepted shape",
      rc_w is None, str(rc_w)[:200])
# W6: range-claim -> constructor semantics (2026-11-16: `revision (>=1)` lived only in
# the producer's intent prose; the collaborator TABLE is what consumer testers receive,
# and four frozen fixtures fabricated revision=0 and died on a test nobody could edit).
ctor_hints = {"package": "com.w", "implements": [], "dependencies": [],
              "methods": [{"signature": "Sample6(int revision)", "returns": ""}]}
claim = gtask("T2-922", "Sample6", 2, project="ws",
              intent="record; revision (>=1, else IllegalArgumentException)",
              path="src/main/java/w/Sample6.java", hints=ctor_hints)
rc_w = emit([claim])
check("W6 an intent stating a constructor ARGUMENT INVARIANT is refused when the "
      "constructor's table entry carries no `semantics` (the bound must reach the "
      "consumer units' injected collaborator table, not live only in prose)",
      bool(rc_w) and "semantics" in str(rc_w) and "Sample6" in str(rc_w), str(rc_w)[:200])
claim_ok = gtask("T2-923", "Sample7", 2, project="ws",
                 intent="record; revision (>=1, else IllegalArgumentException)",
                 path="src/main/java/w/Sample7.java",
                 hints={"package": "com.w", "implements": [], "dependencies": [],
                        "methods": [{"signature": "Sample7(int revision)", "returns": "",
                                     "semantics": "revision >= 1; first revision is 1; "
                                                  "consumers build via received()"}]})
rc_w = emit([claim_ok])
check("W6b the same claim ACCEPTS once the constructor entry spells the bound in "
      "`semantics` (the tester-facing construction contract is complete)",
      rc_w is None, str(rc_w)[:200])
# W7: the MOCKABILITY gap (2026-11-16 15:17: an evaluator sealed an event interface and
# the CONSUMER's seven stub-based tests died - the consumer burned its whole life budget
# on a file it must not touch). Runner normalizes `mock_impossible`/failure.mock_type;
# the engine charges the producer that CLOSED the type, never the mocking victim, and an
# own-product closure stays the unit's own fault.
(ROOT / "blackboard" / "complete" / "T2-930-wt.json").write_text(json.dumps(
    gtask("T2-930", "EvtClosed", 2, project="wt", path="src/main/java/w/EvtClosed.java",
          hints={"package": "com.w", "implements": [], "dependencies": [],
                 "methods": [{"signature": "payload()", "returns": "String"}]})))
(ROOT / "blackboard" / "complete" / "T1-931-wt.json").write_text(json.dumps(
    gtask("T1-931", "StubberTest", 1, project="wt",
          path="src/test/java/w/StubberTest.java")))
(ROOT / "blackboard" / "complete" / "T2-931-wt.json").write_text(json.dumps(
    gtask("T2-931", "Stubber", 2, deps=("T1-931",), project="wt",
          path="src/main/java/w/Stubber.java", hints={
              "package": "com.w", "implements": [],
              "dependencies": [{"type": "EvtClosed", "task_id": "T2-930"}],
              "methods": [{"signature": "go()", "returns": "void"}]})))
mock_result = {"status": "assertion_failure", "exit_code": 1, "counts": {"run": 7, "errors": 7},
               "mock_impossible": ["EvtClosed"],
               "failures": [{"test": "w.StubberTest.stubs", "mock_type": "EvtClosed",
                             "message": "Mockito cannot mock this class"}]}
_stubber = json.load(open(ROOT / "blackboard" / "complete" / "T2-931-wt.json"))
check("W7 a mockability gap on a FOREIGN closed type defers the mocking unit and names "
      "its producer (_mock_impossible_owner -> T2-930, not the victim T2-931)",
      tdd_engine._mock_impossible_owner(mock_result, _stubber) == "T2-930"
      and tdd_engine._blocked_by_peers(mock_result, _stubber) is True)
_self = json.load(open(ROOT / "blackboard" / "complete" / "T2-930-wt.json"))
check("W7b closing the type the unit ITSELF ships is its own contract's problem "
      "(no foreign owner -> charged normally)",
      tdd_engine._mock_impossible_owner(mock_result, _self) is None)
(ROOT / "blackboard" / "red-phase" / "T1-931.json").write_text(json.dumps(
    {"executed": True, "status": "compile_error",
     "command": "./mvnw -q -Dtest=StubberTest test"}))
test_gate._tool_result = lambda root, command, timeout: (
    {"status": "passed", "exit_code": 0, "classes": {}, "counts": {}}
    if "compile" in command else
    {"status": "assertion_failure", "exit_code": 1, "counts": {"run": 7, "errors": 7},
     "classes": {"w.StubberTest": "failed"},
     "mock_impossible": ["EvtClosed"],
     "failures": [{"test": "w.StubberTest.stubs", "mock_type": "EvtClosed",
                   "message": "Mockito cannot mock this class"}],
     "excerpt": []})
with _cl.redirect_stdout(_io.StringIO()):
    _wt_reopen = tdd_engine.terminal_suite_gate()
check("W7c the terminal suite gate charges the CLOSED-type producer (T2-930 reopened) "
      "and leaves the victim's completed record (T2-931) alone",
      "T2-930" in _wt_reopen and "T2-931" not in _wt_reopen, str(_wt_reopen))

# --- X. the REAL-SUBSTRATE / REQUEST-PATH / IDEMPOTENCY plan gates (2026-11-16
#    second drain: mocked DatabaseClient hid an unpopulated NOT NULL PK while 186
#    tests and a contextLoads boot stayed green).
xu_hints = {"package": "com.x", "implements": [], "dependencies": [],
            "methods": [{"signature": "record(E e)", "returns": "void"}]}
x_mockonly_t1 = gtask("T1-941", "com.x.AuditMock", 1, project="xu",
                      path="src/test/java/x/AuditMockTest.java",
                      intent="Test the audit adapter with a mocked database client.",
                      hints=xu_hints)
x_mockonly_t2 = gtask("T2-941", "com.x.AuditMock", 2, deps=("T1-941",), project="xu",
                      path="src/main/java/x/AuditMock.java",
                      intent="INSERT INTO audit_trail (actor, action) VALUES ...",
                      hints=xu_hints)
rc_x = emit([x_mockonly_t1, x_mockonly_t2])
check("X1 an SQL-executing unit whose paired test intent lacks a real-substrate demand "
      "is REFUSED (the N1 class: mocked client proves shape, never schema fit)",
      bool(rc_x) and "REAL-SUBSTRATE" in str(rc_x), str(rc_x)[:200])
x_real_t1 = gtask("T1-942", "com.x.AuditReal", 1, project="xu",
                  path="src/test/java/x/AuditRealTest.java",
                  intent="Execute the actual migration DDL against the embedded "
                         "substitute database and assert the durable row.", hints=xu_hints)
x_real_t2 = gtask("T2-942", "com.x.AuditReal", 2, deps=("T1-942",), project="xu",
                  path="src/main/java/x/AuditReal.java",
                  intent="INSERT INTO audit_trail (actor, action) VALUES ...",
                  hints=xu_hints)
rc_x = emit([x_real_t1, x_real_t2])
check("X1b the same unit ACCEPTS once the paired test intent demands the real-substrate "
      "run against actual migration DDL", rc_x is None, str(rc_x)[:200])
xv_t1 = gtask("T1-943", "com.x.Ping", 1, project="xv", path="src/test/java/x/PingTest.java",
              intent="assert the controller delegates", hints=xu_hints)
xv_t2 = gtask("T2-943", "com.x.Ping", 2, deps=("T1-943",), project="xv",
              path="src/main/java/x/Ping.java",
              intent="@PostMapping /api/ping request body handling", hints=xu_hints)
rc_x = emit([xv_t1, xv_t2])
check("X2 a plan with an inbound HTTP adapter but no end-to-end request-path slice is "
      "REFUSED (contextLoads + new-built unit tests never make the pieces AGREE)",
      bool(rc_x) and "request-path slice" in str(rc_x), str(rc_x)[:200])
xv_t1b = gtask("T1-944", "com.x.Pong", 1, project="xw", path="src/test/java/x/PongTest.java",
               intent="assert the controller delegates", hints=xu_hints)
xv_t2b = gtask("T2-944", "com.x.Pong", 2, deps=("T1-944",), project="xw",
               path="src/main/java/x/Pong.java",
               intent="@PostMapping /api/pong request body handling", hints=xu_hints)
xv_e2e = gtask("T1-945", "com.x.EntrySliceTest", 1, project="xw",
               path="src/test/java/x/EntrySliceTest.java",
               intent="end-to-end request-path slice: drive the entry, assert durable rows",
               hints=xu_hints)
xv_e2e2 = gtask("T2-945", "com.x.EntrySliceSupport", 2, deps=("T1-945",), project="xw",
                path="src/main/java/x/EntrySliceSupport.java",
                intent="test support for the integration slice", hints=xu_hints)
rc_x = emit([xv_t1b, xv_t2b, xv_e2e, xv_e2e2])
check("X2b the same plan ACCEPTS once one integration-slice task is scheduled",
      rc_x is None, str(rc_x)[:200])
xw2_chain_t1 = gtask("T1-946", "com.x.Ingest", 1, project="xx",
                     path="src/test/java/x/IngestTest.java",
                     intent="assert the store appends", hints=xu_hints)
xw2_chain_t2 = gtask("T2-946", "com.x.Ingest", 2, deps=("T1-946",), project="xx",
                     path="src/main/java/x/Ingest.java",
                     intent="append-only revision store: nextRevision per delivery",
                     hints=xu_hints)
xw2_in_t1 = gtask("T1-947", "com.x.Front", 1, project="xx",
                  path="src/test/java/x/FrontTest.java",
                  intent="assert the POST handler", hints=xu_hints)
xw2_in_t2 = gtask("T2-947", "com.x.Front", 2, deps=("T1-947", "T2-946"), project="xx",
                  path="src/main/java/x/Front.java",
                  intent="@PostMapping /api/ingest request body, server-minted id",
                  hints=xu_hints)
xw2_e2e = gtask("T1-948", "com.x.ChainSliceTest", 1, project="xx",
                path="src/test/java/x/ChainSliceTest.java",
                intent="end-to-end request-path slice for the ingress chain",
                hints=xu_hints)
xw2_e2e2 = gtask("T2-948", "com.x.ChainSliceSupport", 2, deps=("T1-948",), project="xx",
                 path="src/main/java/x/ChainSliceSupport.java",
                 intent="test support", hints=xu_hints)
rc_x = emit([xw2_chain_t1, xw2_chain_t2, xw2_in_t1, xw2_in_t2, xw2_e2e, xw2_e2e2])
check("X3 an at-least-once inbound over an append-only chain with NO idempotency duty "
      "on the chain is REFUSED (N4: a network retry must not mint a revision)",
      bool(rc_x) and "idempotency" in str(rc_x), str(rc_x)[:200])
xw2_chain_t2b = dict(xw2_chain_t2)
xw2_chain_t2b["intent"] = ("append-only revision store: dedup by the client-supplied "
                           "idempotency key (natural identity), nextRevision per new key")
rc_x = emit([xw2_chain_t1, xw2_chain_t2b, xw2_in_t1, xw2_in_t2, xw2_e2e, xw2_e2e2])
check("X3b the same chain ACCEPTS once the receiving store contract names the dedup key",
      rc_x is None, str(rc_x)[:200])

# X4/X5: the assembly-time probes (request-path evidence, base-document discipline).
import assembly as _asm
xs = ROOT / "xs-service"
(xs / "src" / "main" / "java" / "com" / "a").mkdir(parents=True)
(xs / "src" / "test" / "java" / "com" / "a").mkdir(parents=True)
(xs / "src" / "main" / "resources").mkdir(parents=True)
(xs / "pom.xml").write_text("<project><dependency>flyway-core</dependency></project>")
(xs / "src" / "main" / "java" / "com" / "a" / "App.java").write_text(
    "package com.a;\n@SpringBootApplication\npublic class App {\n"
    "  public static void main(String[] a) {}\n}\n")
(xs / "src" / "test" / "java" / "com" / "a" / "AppTests.java").write_text(
    "package com.a;\n@SpringBootTest\nclass AppTests {}\n")
(xs / "src" / "main" / "resources" / "application.yml").write_text(
    "spring:\n  r2dbc:\n    url: r2dbc:h2:mem:///db\n")
check("X4 the assembly gate REFUSES a delivered tree where no test ever sends a request "
      "(contextLoads-only boot, the N1 blind spot at delivered time)",
      bool(_asm._request_path_problems(xs, "java-springboot")))
(xs / "src" / "test" / "java" / "com" / "a" / "EntrySliceTest.java").write_text(
    "package com.a;\n@SpringBootTest\nclass EntrySliceTest {\n"
    "  WebTestClient client;\n}\n")
check("X4b one request-path slice satisfies the probe",
      not _asm._request_path_problems(xs, "java-springboot"))
check("X5 the base document pinning the embedded substitute LITERALLY is REFUSED "
      "(N3 production fiction)", bool(_asm._base_config_problems(xs, "java-springboot")))
(xs / "src" / "main" / "resources" / "application.yml").write_text(
    "spring:\n  r2dbc:\n    url: ${DB_URL}\n  flyway:\n"
    "    locations: classpath:db/migration\n---\nspring:\n  config:\n"
    "    activate:\n      on-profile: test\n  r2dbc:\n    url: r2dbc:h2:mem:///db\n")
check("X5b placeholder base + substitute isolated in the profile document ACCEPTS",
      not _asm._base_config_problems(xs, "java-springboot"))
(xs / "src" / "main" / "resources" / "application.yml").write_text(
    "spring:\n  r2dbc:\n    url: r2dbc:h2:mem:///xsdb\n")
(xs / "src" / "test" / "java" / "com" / "a" / "ConfigPinTest.java").write_text(
    "package com.a;\nclass ConfigPinTest {\n  void baseUrl() {\n"
    "    assertThat(url).isEqualTo(\"r2dbc:h2:mem:///xsdb\");\n  }\n}\n")
check("X5d the substitute probe goes SILENT when a delivered test pins the exact base "
      "value: the plan decided the embedded-default posture and the contract witnesses "
      "it (2026-11-17: the assembler obeyed the probe, broke the config unit's frozen "
      "test, and the terminal suite gate reopened the owner to undo it - the VALUE "
      "twin of the N8 location collision)",
      not _asm._base_config_problems(xs, "java-springboot"))
(xs / "src" / "test" / "java" / "com" / "a" / "ConfigPinTest.java").unlink()
check("X5e without the witness test the literal base substitute is REFUSED again "
      "(the exemption cannot be conjured by unrelated files)",
      bool(_asm._base_config_problems(xs, "java-springboot")))
(xs / "src" / "main" / "resources" / "application.yml").write_text(
    "spring:\n  flyway:\n    locations: filesystem:db/migrations\n  r2dbc:\n"
    "    url: ${DB_URL}\n")
(xs / "db" / "migrations").mkdir(parents=True)
(xs / "db" / "migrations" / "V1__x.sql").write_text("CREATE TABLE t (id INT);")
check("X5c a delivered config whose locations token is filesystem: NO LONGER fails the "
      "assembly gate - that check collided with the config unit's own frozen test and "
      "livelocked T4 (2026-11-16); portability of the SAME shape is refused at EMIT "
      "instead, where the architect can still fix it",
      not _asm._base_config_problems(xs, "java-springboot"),
      str(_asm._base_config_problems(xs, "java-springboot"))[:200])

# X6: plan rule (r) - migration locations must be the PACKAGED classpath form, at EMIT.
import workspace as _ws
(_ROOT_proj := ROOT / "proj" / "db" / "migrations").mkdir(parents=True, exist_ok=True)
(_ROOT_proj / "V1__x.sql").write_text("CREATE TABLE t (id INT);")
_orig_root_for = workspace.project_root_for
workspace.project_root_for = lambda slug: ROOT / "proj"
cfg_bad = gtask("T2-952", "AppCfg", 2, project="wh",
                path="src/main/resources/application.yml",
                intent="runtime application.yml: spring.flyway.locations filesystem:db/migrations, "
                       "clean ${DB_URL} placeholders for the datasource")
rc_x = emit([cfg_bad])
check("X6 an emit config unit that pins migration locations CWD-relative into the "
      "project is REFUSED at plan time (jar-portability, enforced where it is "
      "fixable - not at the assembly gate against a frozen test)",
      bool(rc_x) and "CWD-relative" in str(rc_x), str(rc_x)[:200])
cfg_good = gtask("T2-953", "AppCfgOk", 2, project="wh",
                 path="src/main/resources/application.yml",
                 intent="runtime application.yml: spring.flyway.locations classpath:db/migration, "
                        "the scripts packaged under src/main/resources/db/migration",
                 hints={"package": "com.w", "implements": [], "dependencies": [],
                        "methods": []})
rc_x = emit([cfg_good])
check("X6b the packaged classpath form ACCEPTS", rc_x is None, str(rc_x)[:200])

# X7: the terminal suite gate must read a red class whose owner is QUARANTINED as the
# quarantine owning it - not as an ownerless mystery.
(ROOT / "blackboard" / "error" / "T2-954-wg.json").write_text(json.dumps(
    gtask("T2-954", "Holder954", 2, deps=("T1-954",), project="wg",
          path="src/main/java/g/Holder954.java")))
(ROOT / "blackboard" / "complete" / "T1-954-wg.json").write_text(json.dumps(
    gtask("T1-954", "Holder954Test", 1, project="wg",
          path="src/test/java/g/Holder954Test.java")))
(ROOT / "blackboard" / "red-phase" / "T1-954.json").write_text(json.dumps(
    {"executed": True, "status": "compile_error",
     "command": "./mvnw -q -Dtest=Holder954Test test"}))
test_gate._tool_result = lambda root, command, timeout: (
    {"status": "passed", "exit_code": 0, "classes": {}, "counts": {}}
    if "compile" in command else
    {"status": "assertion_failure", "exit_code": 1, "counts": {"run": 3, "failures": 3},
     "classes": {"g.Holder954Test": "failed"},
     "failures": [{"test": "g.Holder954Test.works", "message": "expected 1 but was 2"}]})
_buf7 = _io.StringIO()
with _cl.redirect_stdout(_buf7):
    _wg_reopen = tdd_engine.terminal_suite_gate()
check("X7 a red class whose owner is QUARANTINED reads as 'the quarantine already owns "
      "it' - not 'NO producing unit' (the owner map must see error/ records)",
      _wg_reopen == [] and "owner T2-954 is quarantined" in _buf7.getvalue(),
      f"{_wg_reopen} {_buf7.getvalue()[-220:]}")
workspace.project_root_for = _orig_root_for

# X8: plan rule (v) delivered machine half - structured config documents carry their
# kind's NATIVE shape; flat dotted property keys inside a .yml are the properties
# vocabulary smuggled into YAML (2026-11-16 tree finding: boot-green, test-green,
# and reported as a bug by a human reader). FORMAT CARRIES NO VALUES, so the probe
# demands re-serialization at the gate where the assembler can act - the argued
# exception to (r)'s frozen-value doctrine.
check("X8 the config-format probe keeps the nested-shape delivered document clean",
      not _asm._config_format_problems(xs, "java-springboot"))
(xs / "src" / "main" / "resources" / "application.yml").write_text(
    "spring.flyway.locations: filesystem:db/migrations\nspring.r2dbc.url: ${DB_URL}\n"
    "telemetry.boundaries[0].metric: HEART_RATE\n")
rc_x8 = _asm._config_format_problems(xs, "java-springboot")
check("X8b a flat dotted-key YAML document is FLAGGED for re-serialization "
      "(root-level dotted keys = flattened property paths, e.g. 'telemetry."
      "boundaries[0].metric')",
      bool(rc_x8) and "Re-SERIALIZE" in str(rc_x8), str(rc_x8)[:200])
(xs / "src" / "main" / "resources" / "application.yml").write_text(
    "spring:\n  flyway:\n    locations: filesystem:db/migrations\n  r2dbc:\n"
    "    url: ${DB_URL}\ntelemetry:\n  boundaries:\n    - metric: HEART_RATE\n")
check("X8c the re-serialized document (identical keys, identical values, nested "
      "shape + real SEQUENCE) passes - this is the exact fix the probe demands",
      not _asm._config_format_problems(xs, "java-springboot"))
(xs / "src" / "main" / "resources" / "application.properties").write_text(
    "spring.application.name=demo\nspring.flyway.locations=filesystem:db/migrations\n")
check("X8d flat dotted keys in a PROPERTIES artifact are their kind's native form - "
      "the probe never touches them",
      not _asm._config_format_problems(xs, "java-springboot"))

# --- Y. the three refusal classes born from the 2026-11-16 EVENING inspection
#    (PART III G2/G3/G4). Each Y-refusal reproduces, from plan records alone, one of
#    the three residuals the third drain shipped GREEN - the same probe over the real
#    v9 board names all four findings; these pins lock the machine cores.
# Y1/Y1b: (s) a deduped chain over a CORRECTING history must state the value axis.
y1_units = [
    gtask("T1-960", "com.x.CorStore", 1, project="ax",
          path="src/test/java/x/CorStoreTest.java",
          intent="assert the store dedups redelivered samples", hints=xu_hints),
    gtask("T2-960", "com.x.CorStore", 2, deps=("T1-960",), project="ax",
          path="src/main/java/x/CorStore.java",
          intent="append-only revision store; corrections append a new revision; dedup by "
                 "the natural identity (device, metric, t_device); nextRevision per delivery",
          hints=xu_hints),
    gtask("T1-961", "com.x.CorFront", 1, project="ax",
          path="src/test/java/x/CorFrontTest.java",
          intent="assert the POST handler", hints=xu_hints),
    gtask("T2-961", "com.x.CorFront", 2, deps=("T1-961", "T2-960"), project="ax",
          path="src/main/java/x/CorFront.java",
          intent="@PostMapping /api/ingest request body handling", hints=xu_hints),
    gtask("T1-962", "com.x.CorSlice", 1, project="ax",
          path="src/test/java/x/CorSliceTest.java",
          intent="end-to-end request-path slice for the ingress chain", hints=xu_hints),
    gtask("T2-962", "com.x.CorSliceSupport", 2, deps=("T1-962",), project="ax",
          path="src/main/java/x/CorSliceSupport.java",
          intent="test support for the integration slice", hints=xu_hints),
]
rc_y = emit(y1_units)
check("Y1 (s) a deduped chain whose history SPEAKS of corrections is REFUSED while no "
      "contract states the value axis (PART III G2: UNIQUE(device,metric,t_device) "
      "reclassified every value-correction as a duplicate no-op, suite green)",
      bool(rc_y) and "VALUE-AXIS" in str(rc_y), str(rc_y)[:250])
y1_fixed = [dict(u) for u in y1_units]
y1_fixed[1]["intent"] = (
    "append-only revision store; corrections append a new revision; dedup by the natural "
    "identity (device, metric, t_device) - the identity EXCLUDES the value, so a "
    "retry-vs-correction discriminator is required: the payload comparison duty rewrites "
    "a same-identity new-value resend as a revision append and never as a no-op; nextRevision "
    "per delivery")
rc_y = emit(y1_fixed)
check("Y1b the chain ACCEPTS once the receiving store contract states the VALUE-AXIS "
      "decision beside the identity (excluded + payload-comparison discriminator)",
      rc_y is None, str(rc_y)[:250])

# Y2/Y2b/Y2c: (t) a strategy-promised mechanism needs a scheduled, UNNEGATED install duty.
(ROOT / "blackboard" / "complete" / "execution-strategy-mech.json").write_text(json.dumps(
    {"slug": "mech", "observability": {
        "correlation_key": "requestId carried in the async context and propagated to log "
                           "lines via context-propagation",
        "step_logs": ["packet received"],
        "audit_trail": {"record_fields": ["actor", "action", "outcome", "timestamp"]},
        "metrics": [{"name": "packets.received", "type": "counter", "tags": []}],
        "export": {"logs": "structured file sink"}}}))
mech_hints = {"package": "com.mech", "implements": [], "dependencies": [],
              "methods": [{"signature": "ingest(P p)", "returns": "void"}]}
mech_claimer = dict(gtask("T2-963", "com.mech.Ingress", 2, project="mech", hints=mech_hints))
mech_claimer["observability"] = {"step_logs": ["packet received"]}
rc_y = emit([mech_claimer])
check("Y2 (t) a strategy promising correlation 'via <mechanism>' with NO unit scheduling "
      "the install duty is REFUSED (PART III G3: promise and plan disagreed, every gate "
      "green because nothing compares a promise to a duty)",
      bool(rc_y) and "INSTALLS the mechanism" in str(rc_y), str(rc_y)[:250])
mech_wiring = gtask("T2-964", "com.mech.Wiring", 2, project="mech",
                    intent="wiring unit: add the context-propagation dependency and enable "
                           "automatic context-propagation at boot", hints=mech_hints)
rc_y = emit([mech_claimer, mech_wiring])
check("Y2b the batch ACCEPTS once a unit declares the install duty with the strategy's own "
      "mechanism token", rc_y is None, str(rc_y)[:250])
mech_negated = gtask("T2-965", "com.mech.Manual", 2, project="mech",
                     intent="correlation via manual argument passing: no context-propagation "
                            "library is used, log lines carry the key only when hand-passed",
                     hints=mech_hints)
for _f in settings.QUEUE_DIR.glob("*-mech.json"):
    _f.unlink()  # the claim/duty layers read the whole board: clear Y2b's accepted tasks
mech_claimer2 = dict(mech_claimer, id="T2-970")
rc_y = emit([mech_claimer2, mech_negated])
check("Y2c a NEGATED mention of the mechanism is the divergence, not the duty (the exact "
      "'no context-propagation library is used' sentence the v9 plan tabled)",
      bool(rc_y) and "INSTALLS the mechanism" in str(rc_y), str(rc_y)[:250])

# Y3/Y3b/Y3c: (u) layer 1 - every promised boundary crossing is counted or exempted.
(ROOT / "blackboard" / "complete" / "execution-strategy-flr.json").write_text(json.dumps(
    {"slug": "flr", "observability": {
        "correlation_key": "cid",
        "step_logs": ["order accepted", "stock reserved", "shipment broadcast downstream"],
        "audit_trail": {"record_fields": ["actor", "action", "outcome", "timestamp"]},
        "metrics": [{"name": "orders.accepted", "type": "counter", "tags": ["outcome"]},
                    {"name": "stock.reserved", "type": "counter", "tags": []}],
        "export": {"logs": "structured file sink"}}}))
flr_task = dict(gtask("T2-966", "com.f.Service", 2, project="flr", hints=mech_hints))
flr_task["observability"] = {"step_logs": ["order accepted", "stock reserved",
                                           "shipment broadcast downstream"]}
rc_y = emit([flr_task])
check("Y3 (u) a strategy step log with no metric pairing ('shipment broadcast downstream') "
      "is REFUSED (PART III G4: the broadcast/windowed boundaries were logged, never counted "
      "- the floor looked complete because it only checked claims of what it promised)",
      bool(rc_y) and "broadcast" in str(rc_y) and "nobody" in str(rc_y), str(rc_y)[:250])
flr_fixed = json.loads((ROOT / "blackboard" / "complete"
                        / "execution-strategy-flr.json").read_text())
flr_fixed["observability"]["metrics"].append(
    {"name": "shipments.broadcast", "type": "counter", "tags": []})
(ROOT / "blackboard" / "complete" / "execution-strategy-flr.json").write_text(
    json.dumps(flr_fixed))
rc_y = emit([flr_task])
check("Y3b the floor ACCEPTS once a counter pairs with every promised step "
      "(name-token overlap: shipments.broadcast <-> 'shipment broadcast downstream')",
      rc_y is None, str(rc_y)[:250])
flr_exempt = json.loads((ROOT / "blackboard" / "complete"
                         / "execution-strategy-flr.json").read_text())
del flr_exempt["observability"]["metrics"][-1]
flr_exempt["observability"]["uncounted_steps"] = [
    {"step": "shipment broadcast downstream", "reason": "bounded by the replay sink's own "
     "waterfall metric owned by the platform exporter"}]
(ROOT / "blackboard" / "complete" / "execution-strategy-flr.json").write_text(
    json.dumps(flr_exempt))
for _f in settings.QUEUE_DIR.glob("*-flr.json"):
    _f.unlink()  # clear Y3b's accepted task so its claims do not double with Y3c's
flr_task2 = dict(flr_task, id="T2-971")
rc_y = emit([flr_task2])
check("Y3c an explicit `uncounted_steps` entry with its reason exempts the step "
      "(the honest posture becomes a recorded decision, not a silent hole)",
      rc_y is None, str(rc_y)[:250])

# Y4/Y4b/Y4c: (u) layer 2 - no contracted failure outcome is unmetered.
(ROOT / "blackboard" / "complete" / "execution-strategy-flm.json").write_text(json.dumps(
    {"slug": "flm", "observability": {
        "correlation_key": "cid",
        "step_logs": ["event enqueued"],
        "audit_trail": {"record_fields": ["actor", "action", "outcome", "timestamp"]},
        "metrics": [{"name": "events.enqueued", "type": "counter", "tags": ["outcome"]}],
        "export": {"logs": "structured file sink"}}}))
flm_hints = {"package": "com.flm", "implements": [], "dependencies": [],
             "methods": [{"signature": "publish(E e)", "returns": "boolean",
                          "semantics": "TRUE=event enqueued; FALSE=event dropped after "
                                       "the FAILED audit (the subscriber keeps running)"}]}
flm_task = dict(gtask("T2-967", "com.flm.Publisher", 2, project="flm", hints=flm_hints))
flm_task["observability"] = {"step_logs": ["event enqueued"]}
rc_y = emit([flm_task])
check("Y4 (u) a tabled FALSE='dropped after the FAILED audit' signal with no counting "
      "meter is REFUSED (PART III G4: audited-but-uncounted failures - the losing pipeline "
      "that reports a healthy dashboard)",
      bool(rc_y) and "uncounted" in str(rc_y), str(rc_y)[:250])
flm_metered = json.loads((ROOT / "blackboard" / "complete"
                          / "execution-strategy-flm.json").read_text())
flm_metered["observability"]["metrics"].append(
    {"name": "events.dropped", "type": "counter", "tags": ["stage"]})
(ROOT / "blackboard" / "complete" / "execution-strategy-flm.json").write_text(
    json.dumps(flm_metered))
rc_y = emit([flm_task])
check("Y4b the plan ACCEPTS once the floor carries the paired drop counter "
      "(telemetry.pipeline.dropped{stage}'s abstract shape: events.dropped{stage})",
      rc_y is None, str(rc_y)[:250])
flm_posture = json.loads((ROOT / "blackboard" / "complete"
                          / "execution-strategy-flm.json").read_text())
del flm_posture["observability"]["metrics"][-1]
flm_posture["observability"]["uncounted_failures"] = (
    "per-event drops continue to be audit-only: accepted posture, the audit table is the "
    "operator surface, reason recorded with the owner sign-off")
(ROOT / "blackboard" / "complete" / "execution-strategy-flm.json").write_text(
    json.dumps(flm_posture))
for _f in settings.QUEUE_DIR.glob("*-flm.json"):
    _f.unlink()  # clear Y4b's accepted task before the posture variant re-emits
flm_posture_task = dict(flm_task, id="T2-972")
rc_y = emit([flm_posture_task])
check("Y4c a declared `uncounted_failures` posture ACCEPTS - the silence becomes a "
      "decision on the board", rc_y is None, str(rc_y)[:250])

# Z1/Z1b/Z1c: (w) a stage-1 test task owns a TEST file. 2026-11-17 drain: the architect
# emitted EVERY tester task with the paired production unit's path; the tester - bound to
# "ONE unit test at task `path`" / "Only `path` writable" - wrote @Test classes into
# src/main/java, where JUnit/AssertJ/Mockito/reactor-test are invisible to the main
# classpath; the import-closure guard killed the drain at the first red close-out.
z_hints = {"package": "com.z", "implements": [], "dependencies": [],
           "methods": [{"signature": "ping()", "returns": "void"}]}
z_t1 = gtask("T1-983", "Ping", 1, project="zw", path="src/main/java/z/Ping.java",
             hints=z_hints)
z_t2 = gtask("T2-983", "Ping", 2, deps=("T1-983",), project="zw",
             path="src/main/java/z/Ping.java", hints=z_hints)
rc_z = emit([z_t1, z_t2])
check("Z1 (w) a stage-1 test task whose path IS the paired unit's production file is "
      "REFUSED at emit (one file cannot hold the frozen test and the woven unit)",
      bool(rc_z) and "stage-1 test path" in str(rc_z), str(rc_z)[:250])
z_test = gtask("T1-984", "Ping", 1, project="zw", path="src/test/java/z/PingTest.java",
               hints=z_hints)
z_impl = gtask("T2-984", "Ping", 2, deps=("T1-984",), project="zw",
               path="src/main/java/z/Ping.java", hints=z_hints)
rc_z = emit([z_test, z_impl])
check("Z1b the pair ACCEPTS once the test task owns its own test artifact (the "
      "src/test/java convention every previous drain used)",
      rc_z is None, str(rc_z)[:250])
z_owner = gtask("T2-985", "Ping", 2, project="zx", path="src/main/java/z/Ping.java",
                hints=z_hints)
z_leech = gtask("T1-985", "Pong", 1, project="zx", path="src/main/java/z/Ping.java",
                hints=z_hints)
for _f in settings.QUEUE_DIR.glob("*-zx.json"):
    _f.unlink()  # the pair of ids below reuses them; start the foreign-path case clean
rc_z = emit([z_owner, z_leech])
check("Z1c the rule is board-wide, not pair-local: a test task aimed at ANOTHER unit's "
      "production file is REFUSED too (foreign-file tests are the same poison)",
      bool(rc_z) and "T1-985" in str(rc_z), str(rc_z)[:250])

# Z2/Z2b/Z2c: (x) a mapped inbound handler must name a registration its framework can
# execute (2026-11-17 drain: the controller intent pinned "no scanning-registration
# annotation: registered only by the wiring factory" - WebFlux's isHandler accepts only
# @Controller classes (bytecode-verified), so the bean existed, boot was green and every
# request answered 404; only the e2e slice caught it).
(ROOT / "blackboard" / "complete" / "execution-strategy-z2.json").write_text(json.dumps(
    {"slug": "z2", "tech_stack": {"language": "Java 21"}, "observability": {
        "correlation_key": "cid",
        "step_logs": ["probe accepted"],
        "audit_trail": {"record_fields": ["actor", "action", "outcome", "timestamp"]},
        "metrics": [{"name": "probes.accepted", "type": "counter", "tags": []}],
        "export": {"logs": "structured file sink"}}}))
z2_hints = {"package": "com.z2", "implements": [], "dependencies": [],
            "methods": [{"signature": "accept(P p)", "returns": "void"}]}
z2_tester = gtask("T1-988", "ProbeController", 1, project="z2",
                  path="src/test/java/z2/ProbeControllerTest.java", hints=z2_hints)
z2_slice = gtask("T1-989", "EntrySlice", 1, project="z2",
                 path="src/test/java/z2/EntrySliceTest.java", hints=z2_hints,
                 intent="end-to-end request-path slice driving POST /api/v1/probe and "
                        "asserting the durable row")
z2_pojo = dict(gtask("T2-988", "ProbeController", 2, deps=("T1-988",), project="z2",
                     hints=z2_hints,
                     intent="POST /api/v1/probe endpoint handler. Declared via class-level "
                            "@RequestMapping with @ResponseBody methods and no scanning-"
                            "registration annotation: it is registered only by the wiring factory."),
               layer="interface")
z2_pojo["observability"] = {"step_logs": ["probe accepted"]}
rc_z = emit([z2_tester, z2_slice, z2_pojo])
check("Z2 (x) an inbound HANDLER unit forbidding the stack's marker while crediting the "
      "factory alone is REFUSED (the green boot answering 404 on its own endpoint)",
      bool(rc_z) and "404" in str(rc_z), str(rc_z)[:250])
z2_marked = dict(z2_pojo, id="T2-989", dependsOn=["T1-990"],
                 intent="POST /api/v1/probe endpoint handler. Class-level @Controller + "
                        "@RequestMapping with @ResponseBody methods: it self-registers "
                        "through the marker (WebFlux maps only annotated classes); the "
                        "wiring unit supplies its collaborators and never re-produces it.")
z2_tester2 = dict(z2_tester, id="T1-990")
z2_slice2 = dict(z2_slice, id="T1-991")
rc_z = emit([z2_tester2, z2_slice2, z2_marked])
check("Z2b the batch ACCEPTS once the handler names its marker registration",
      rc_z is None, str(rc_z)[:250])
z2f_tester = gtask("T1-992", "RequestAdmissionFilter", 1, project="z2",
                   path="src/test/java/z2/RequestAdmissionFilterTest.java", hints=z2_hints)
z2_filter = gtask("T2-990", "RequestAdmissionFilter", 2, deps=("T1-992",), project="z2",
                  hints=z2_hints,
                  intent="WebFilter adopting the inbound request header into the Reactor "
                         "Context. No stereotype: it is registered only by the wiring "
                         "factory as a filter bean.")
rc_z = emit([z2f_tester, z2_filter])
check("Z2c the rule exempts NON-handler components: a factory-built WebFilter never needs "
      "the handler marker - refusing it would be the (r)-style gate-vs-gate trap",
      rc_z is None, str(rc_z)[:250])

bad_names = [n for n, c in CHECKS if not c]
print(f"\nENGINE-DECISIONS SUITE: {len(CHECKS) - len(bad_names)}/{len(CHECKS)}")
print("FAILED:", bad_names if bad_names else "none")
sys.exit(1 if bad_names else 0)
