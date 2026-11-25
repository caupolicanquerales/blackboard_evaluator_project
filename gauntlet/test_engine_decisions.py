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
  S. security architect: the spec gate (deny-by-default, IDOR, disclosure, duty
     closure), the stage 0 scaffold identity, and the emit gate's duty-claim
     coverage with its three phase-order skips
"""
import inspect
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
import ddd
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
    # verdict contract v2 (2026-11-25): fixtures write what the TOOL writes
    return {"verdict_version": 2, "status": status, "exit_code": 1,
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
KINDS = {"verdict_version": 2, "status": "compile_error", "exit_code": 1,
         "missing_symbols": [],
         "member_demands": [], "failures": [], "counts": {},
         "excerpt": [f"{ROOT}/proj/src/main/java/x/Channel.java:[4,1] totally unrelated prose"],
         "blamed_files": ["Channel.java"],
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
test_gate._write_memo(keep_task, "red", {"verdict_version": 2, "status": "assertion_failure",
                                         "exit_code": 1, "failures": [], "counts": {}})
check("A15 assertion_failure + payload woven in a COMPLETED suite = proven harmless -> KEEP",
      tdd_engine._payload_proven_harmless(keep_task) is True)
test_gate._write_memo(keep_task, "red", {"verdict_version": 2, "status": "compile_error",
                                         "exit_code": 1, "missing_symbols": ["X"],
                                         "failures": [], "counts": {}})
check("A16 compile_error verdict -> classic revert (poison or unknown)",
      tdd_engine._payload_proven_harmless(keep_task) is False)
(ROOT / "blackboard" / "weave-results" / "T2-070.json").unlink()
test_gate._write_memo(keep_task, "red", {"verdict_version": 2, "status": "assertion_failure",
                                         "exit_code": 1, "failures": [], "counts": {}})
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
PEER_OWNED = {"verdict_version": 2, "status": "compile_error", "exit_code": 1,
              "missing_symbols": ["ReorderWindow(com.pulse.properties)"],
              "member_demands": [{"member": "ReorderWindow(properties)", "owner": "ReorderWindow",
                                  "kind": "constructor"}],
              "failures": [], "counts": {}, "excerpt": [],
              # O1 (2026-11-25): the tool positions every compile error and TYPES the
              # blame set; the excerpt prose that used to drive this decision is
              # DISPLAY ONLY. Behavior pin unchanged: the peer-owned wiring file's
              # owner defers while its call site is unadjudicated.
              "blamed_files": ["TelemetryWiringConfiguration.java"],
              "problem_kinds": [{"file": "TelemetryWiringConfiguration.java", "line": 32,
                                 "kind": "other"}]}
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
CYCLE = {"verdict_version": 2, "status": "compile_error", "exit_code": 1,
         "missing_symbols": ["ReorderWindow"],
         "member_demands": [], "failures": [], "counts": {},
         "blamed_files": ["TelemetryWiringConfiguration.java"],
         "problem_kinds": [{"file": "TelemetryWiringConfiguration.java", "line": 32,
                            "kind": "other"}]}
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
REGRESSION = {"verdict_version": 2, "status": "compile_error", "exit_code": 1,
              "missing_symbols": [], "member_demands": [], "failures": [], "counts": {},
              "blamed_files": ["OldThing.java"],
              "problem_kinds": [{"file": "OldThing.java", "line": 9, "kind": "other"}]}
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
blamed = {"verdict_version": 2, "status": "compile_error", "exit_code": 1,
          "missing_symbols": [],
          "member_demands": [], "failures": [], "counts": {},
          "blamed_files": ["WidgetTest.java"],
          "problem_kinds": [{"file": "WidgetTest.java", "line": 10, "kind": "other"}],
          "excerpt": [f"{ROOT}/proj/src/test/java/x/WidgetTest.java:[10,3] error: incompatible types: A cannot be converted to B"]}
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


DECISIVE = {"verdict_version": 2, "status": "compile_error", "exit_code": 1,
            "classes": {}, "missing_symbols": ["Ghost"], "failures": [], "counts": {},
            "excerpt": ["cannot find symbol: class Ghost"]}
test_gate._tool_result = scripted_tool(DECISIVE)
reason_a, res_a = test_gate.wave_gate_verdict(task(tid="T2-501", project="pc1"), "./mvnw -Dtest=X test")
n = len(calls)
reason_b, res_b = test_gate.wave_gate_verdict(task(tid="T2-502", project="pc1"), "./mvnw -Dtest=Y test")
check("C1 decisive module failure is shared: sibling costs ZERO builds",
      len(calls) == n and reason_b and "compile_error" in reason_b, str(calls))
test_gate._tool_result = scripted_tool(
    {"verdict_version": 2, "status": "error", "exit_code": 1, "classes": {},
     "excerpt": ["boot crash"]})
reason_e, _ = test_gate.wave_gate_verdict(task(tid="T2-503", project="pc2"), "./mvnw -Dtest=Z test")
check("C2 boot crash without class evidence is decisive too", reason_e and "status=error" in reason_e)
test_gate._tool_result = scripted_tool(
    {"verdict_version": 2, "status": "passed", "exit_code": 0, "classes": {}},
    {"verdict_version": 2, "status": "passed", "exit_code": 0,
     "classes": {"com.x.WTest": "passed"}, "counts": {"run": 2},
     # O2: the selector->class join is the TOOL's typed answer (unit_match), not an
     # engine stem guess; the pin's behavior (per-class routing keeps a green selector
     # from re-billing) is unchanged.
     "unit_match": {"selector": "WTest", "class_key": "com.x.WTest", "candidates": 1}})
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
# V9 (2026-11-20 live board): agent-strategy-architect writes step_logs as the
# per-context MAPPING {context: [logs]}; the claim gate read lists only and answered
# CLEAN while FOUR distribution logs (event.consumed, window.buffered, window.broadcast,
# window.overflow) had zero owners - the 2026-11-13 5-planned-0-owned class re-born in a
# new spelling. The gate must flatten BOTH shapes before demanding coverage.
(ROOT / "blackboard" / "complete" / "execution-strategy-sl.json").write_text(json.dumps(
    {"slug": "sl", "observability": {
        "correlation_key": "requestId",
        "step_logs": {"Legacy": ["order accepted (outcome)", "stock reserved"],
                      "Ingest": ["packet.received"],
                      "Stream": ["window.broadcast"]},
        "audit_trail": {"record_fields": ["actor", "action", "outcome", "timestamp"],
                        "port": "AuditTrail.record(AuditEntry)"},
        "metrics": [{"name": "orders.accepted", "type": "counter", "tags": ["outcome"]},
                    {"name": "stock.reserved", "type": "counter", "tags": []},
                    {"name": "packet.received", "type": "counter", "tags": []},
                    {"name": "window.broadcast", "type": "counter", "tags": []}],
        "export": {"logs": "structured ecs file sink", "metrics": "scrape endpoint",
                   "dependency_rule": "boot passes with the collector absent"}}}))
v9_a = dict(gtask("T2-798", "Half", 2, project="sl", hints=sl_hints))
v9_a["observability"] = {"step_logs": ["packet.received"]}
rc_v = emit([v9_a])
check("V9 a dict-shaped step-log floor is FLATTENED by the claim gate: half coverage of a "
      "per-context mapping is refused naming the exact unowned entry (the list-only reader "
      "skipped the whole law on the live board - 4 logs unowned, gate CLEAN, V1's promise "
      "broken by shape, not by will)",
      bool(rc_v) and "window.broadcast" in str(rc_v) and "claimed by NO stage-2 unit" in str(rc_v),
      str(rc_v)[:260])
v9_b = dict(gtask("T2-799", "Rest", 2, project="sl", hints=sl_hints))
v9_b["observability"] = {"step_logs": ["packet.received", "window.broadcast"]}
rc_v = emit([v9_b])
check("V9b the SAME dict floor ACCEPTS once every entry has exactly one owner across both "
      "spellings (the legacy list entries' old claims on the board still count - coverage "
      "is over the whole board, not the batch)",
      rc_v is None, str(rc_v)[:220])

# V10 (2026-11-20 root fix): the floor SHAPE law belongs at the strategy WRITE BOUNDARY -
# a step_logs spelling no consumer can flatten must die in phase 1's post-check, not in a
# downstream reader's silence (V9's silent skip was an ambiguous contract at the source).
_v10_strat = settings.COMPLETE_DIR / "execution-strategy-shp.json"
_v10_base = {"slug": "shp", "bounded_contexts": ["A"],
             "surfaces": [{"name": "in a", "kind": "http", "context": "A",
                           "operations": ["post"], "traced_from": "v10", "method": "POST", "path": "/x"}],
             "contexts_without_inbound": [], "modules": [], "layers": [], "build_order": [],
             "risks": [], "module_layout": {"base_package": "com.x", "packages": [],
                                            "integration": []},
             "persistence": {"drivers": [], "data_model": [], "queries": [],
                             "migration_plan": [], "backup_recovery": "",
                             "open_questions": []}}
_v10_floor = {"correlation_key": "cid", "audit_trail": {"record_fields": ["actor"]},
              "metrics": [], "export": {}}
_v10_strat.write_text(json.dumps(dict(
    _v10_base, observability=dict(_v10_floor, step_logs="packet received"))),
    encoding="utf-8")
_v10_bad = ddd.validate_strategy("shp") or ""
_v10_strat.write_text(json.dumps(dict(
    _v10_base, observability=dict(_v10_floor, step_logs={"A": ["packet received"]}))),
    encoding="utf-8")
_v10_map = ddd.validate_strategy("shp")
_v10_strat.write_text(json.dumps(dict(
    _v10_base, observability=dict(_v10_floor, step_logs=["packet received"]))),
    encoding="utf-8")
_v10_list = ddd.validate_strategy("shp")
_v10_strat.write_text(json.dumps(dict(
    _v10_base, observability=dict(_v10_floor, step_logs={"A": "packet received"}))),
    encoding="utf-8")
_v10_nested = ddd.validate_strategy("shp") or ""
_v10_strat.unlink()
check("V10 the floor-shape law fires at the STRATEGY GATE: a step_logs spelled as a bare "
      "string, or a context mapped to a string, is refused at phase 1's post-check - while "
      "the two lawful shapes (flat list, {context: [logs]} of lists) pass: ambiguity dies "
      "where the file is still the only thing being written (root cause of V9's silent skip)",
      "step_logs" in _v10_bad and "shape" in _v10_bad
      and _v10_map is None and _v10_list is None
      and "step_logs[" in _v10_nested,
      f"bad={_v10_bad[:90]} nested={_v10_nested[:110]}")
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
    {"verdict_version": 2, "status": "assertion_failure", "exit_code": 1,
     "counts": {"run": 4, "failures": 3},
     "classes": {"ts.WidgetTest": "failed", "ts.SockTest": "failed",
                 "x.GhostTest": "failed", "ts.GearTest": "passed"},
     "excerpt": ["java.lang.IllegalArgumentException: deviceId must not be blank",
                 "at com.ts.Gear.<init>(Gear.java:9)"],
     # O1: the tool types the RUNTIME frame's file; the engine joins Gear.java to its
     # registry owner instead of scanning the frame line
     "stack_files": ["Gear.java"],
     "failures": [{"test": "ts.WidgetTest.g", "message": "expected 0 but was 1",
                   "class": "ts.WidgetTest"}]})
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
envelope = gtask("T2-917", "StreamEnvelope", 2, project="wv",
                 path="src/main/java/w/StreamEnvelope.java", hints={
    "package": "com.w", "implements": [], "dependencies": [],
    "methods": [{"signature": "Mono<ResponseEntity<Flux<Event>>> stream()",
                 "returns": "Mono<ResponseEntity<Flux<Event>>>"}]})
rc_w = emit([envelope])
check("W1e the ENVELOPED publisher is caught too (2026-11-24 seed-002: an SSE endpoint "
      "wrapped as Mono<ResponseEntity<Flux<...>>> hid from the start-of-type match and "
      "passed the unconsumed-source gate - the repair pass called it a workaround): the "
      "stream type counts ANYWHERE in the return, so an envelope is no escape",
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
xw_front_hints = dict(xu_hints, routes=[{"method": "POST", "path": "/api/pong", "duty": "serves"}])
xv_t1b = gtask("T1-944", "com.x.Pong", 1, project="xw", path="src/test/java/x/PongTest.java",
               intent="assert the controller delegates", hints=xw_front_hints)
xv_t2b = gtask("T2-944", "com.x.Pong", 2, deps=("T1-944",), project="xw",
               path="src/main/java/x/Pong.java",
               intent="@PostMapping /api/pong request body handling", hints=xw_front_hints)
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
xx_front_hints = dict(xu_hints, routes=[{"method": "POST", "path": "/api/ingest", "duty": "serves"}])
xw2_in_t1 = gtask("T1-947", "com.x.Front", 1, project="xx",
                  path="src/test/java/x/FrontTest.java",
                  intent="assert the POST handler", hints=xx_front_hints)
xw2_in_t2 = gtask("T2-947", "com.x.Front", 2, deps=("T1-947", "T2-946"), project="xx",
                  path="src/main/java/x/Front.java",
                  intent="@PostMapping /api/ingest request body, server-minted id",
                  hints=xx_front_hints)
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

# X6c/X6d (2026-11-24 seed-002 v3): the (h) reader-connection leg went machine at emit -
# the live draft tabled spring.flyway.locations but no datasource URL path (the URLs lived
# only in an UNOWNED file the database agent wrote), the F5 fiction class reborn.
_cfg_loc = gtask("T2-961", "AppLoc", 2, project="wj",
                 path="src/main/resources/application.yml",
                 intent="runtime config document seeding the reader locations and ceilings",
                 hints={"package": "com.w", "implements": [], "dependencies": [],
                        "methods": [], "meters": [], "routes": [],
                        "config": [{"path": "spring.flyway.locations", "kind": "value"},
                                   {"path": "spring.codec.max-in-memory-size", "kind": "value"}]})
rc_x = emit([_cfg_loc])
check("X6c a stage-2 config unit tableding a LOCATIONS-class path with NO URL-class path "
      "is REFUSED at emit (rule (h)'s connection leg, stack-neutral segment matching - no "
      "vendor name in the gate; an enabled reader with no tabled datasource migrates the "
      "auto-detected store while the app writes elsewhere)",
      bool(rc_x) and "LOCATIONS key" in str(rc_x), str(rc_x)[:200])
_cfg_url = json.loads(json.dumps(_cfg_loc))
_cfg_url["id"] = "T2-962"
_cfg_url["export"] = "AppUrl"
_cfg_url["ast_hints"]["config"] += [{"path": "spring.r2dbc.url", "kind": "value"},
                                    {"path": "spring.flyway.url", "kind": "value"}]
rc_x = emit([_cfg_url])
check("X6d the SAME unit ACCEPTS once the connection-URL paths are tabled (the gate "
      "refuses the gap, not the style)", rc_x is None, str(rc_x)[:200])
for _q in (ROOT / "blackboard" / "queue").glob("*-wj.json"):
    _q.unlink()
check("X6e the planner brief's next-free numbers include T0 (2026-11-24: the manifest "
      "bootstrap id was hand-guessed because only stages 1-3 were printed)",
      set(pipeline._next_free_for("anything")) == {"T0", "T1", "T2", "T3"})

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
ax_front_hints = dict(xu_hints, routes=[{"method": "POST", "path": "/api/ingest",
                                         "duty": "serves"}])
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
          intent="assert the POST handler", hints=ax_front_hints),
    gtask("T2-961", "com.x.CorFront", 2, deps=("T1-961", "T2-960"), project="ax",
          path="src/main/java/x/CorFront.java",
          intent="@PostMapping /api/ingest request body handling", hints=ax_front_hints),
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
z2_serve_hints = dict(z2_hints, routes=[{"method": "POST", "path": "/api/v1/probe",
                                         "duty": "serves"}])
z2_uses_hints = dict(z2_hints, routes=[{"method": "POST", "path": "/api/v1/probe",
                                        "duty": "uses"}])
z2_tester = gtask("T1-988", "ProbeController", 1, project="z2",
                  path="src/test/java/z2/ProbeControllerTest.java", hints=z2_serve_hints)
z2_slice = gtask("T1-989", "EntrySlice", 1, project="z2",
                 path="src/test/java/z2/EntrySliceTest.java",
                 hints=z2_uses_hints,
                 intent="end-to-end request-path slice driving POST /api/v1/probe and "
                        "asserting the durable row")
z2_pojo = dict(gtask("T2-988", "ProbeController", 2, deps=("T1-988",), project="z2",
                     hints=z2_serve_hints,
                     intent="POST /api/v1/probe endpoint handler. Declared via class-level "
                            "@RequestMapping with @ResponseBody methods and no scanning-"
                            "registration annotation: it is registered only by the wiring factory."),
               layer="interface")
z2_pojo["observability"] = {"step_logs": ["probe accepted"]}
rc_z = emit([z2_tester, z2_slice, z2_pojo])
check("Z2 (x) an inbound HANDLER unit forbidding the stack's marker while crediting the "
      "factory alone is REFUSED (the green boot answering 404 on its own endpoint)",
      bool(rc_z) and "404" in str(rc_z), str(rc_z)[:250])
z2_marked = dict(z2_pojo,
                 intent="POST /api/v1/probe endpoint handler. Class-level @Controller + "
                        "@RequestMapping with @ResponseBody methods: it self-registers "
                        "through the marker (WebFlux maps only annotated classes); the "
                        "wiring unit supplies its collaborators and never re-produces it.")
rc_z = emit([z2_tester, z2_slice, z2_marked])
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

# --- S. the security architect: one artifact, four laws, zero engine vocabulary.
#     (2026-11-17, revised after the separation-of-concerns review) The step decides WHAT
#     must hold and names the capability that holds it; the architect maps tokens to real
#     mechanisms and schedules them. Every case below guards one of those two boundaries:
#     a leak of realization vocabulary into the spec, or a duty that reaches no unit.

SEC_SLUG = "sec"
SEC_FILE = settings.COMPLETE_DIR / f"security-spec-{SEC_SLUG}.json"


def sec_spec(mutate=None):
    """One lawful spec in the shape references/security-spec.schema.json tables (trimmed to
    the fields these gates read; Q1 pins the full key contract against the engine)."""
    spec = {
        "schema_version": "1.0", "report_type": "security-spec", "slug": SEC_SLUG,
        "metadata": {"generated_at": "2026-11-17T00:00:00-03:00",
                     "agent": "agent-security-architect", "inputs": ["execution-strategy"],
                     "confidence": "high"},
        "assumptions": [{"id": "AS-01", "text": "callers arrive authenticated",
                         "source": "context-map", "excludes": "anonymous intake"}],
        "trust_boundaries": [{"id": "TB-01", "name": "caller to intake", "from": "device",
                              "to": "Intake", "untrusted_inputs": ["payload"],
                              "controls": ["AZ-01"]}],
        "principals": [{"id": "P-01", "name": "device", "kind": "device", "source": "actors",
                        "authentication": "required", "credential_capability": "proof-of-possession",
                        "identity_claims": ["tenant_id"]}],
        "data_classification": [{"id": "DC-01", "concept": "location", "class": "confidential",
                                 "pii": True, "secret": False, "fields": ["latitude"],
                                 "at_rest": "envelope-encryption", "in_transit": "tls",
                                 "masking": "partial", "retention": "90d", "deletion": "hard",
                                 "log_visibility": "masked", "error_visibility": "forbidden",
                                 "export_visibility": "masked", "reason": "tracks a person"}],
        "authorization_matrix": [
            {"id": "AZ-01", "surface": "intake write", "operation": "POST",
             "principal_ids": ["P-01"], "roles": ["device"], "scopes": ["ingest"],
             "ownership_rule": "owner-and-tenant", "client_supplied_ids": ["device_key"],
             "decision_point": {"layer": "application", "component": "Intake"}, "default": "deny",
             "effect_on_deny": "unauthenticated", "fields_read": [], "fields_written": ["DC-01"],
             "audit_event": "intake-denied", "test_duty": "permitted, denied, cross-owner"},
            {"id": "AZ-02", "surface": "sample read", "operation": "GET", "principal_ids": ["P-01"],
             "roles": ["device"], "scopes": ["read"], "ownership_rule": "tenant",
             "client_supplied_ids": ["sample_id"],
             "decision_point": {"layer": "application", "component": "Query"}, "default": "deny",
             "effect_on_deny": "forbidden-not-found", "fields_read": ["DC-01"],
             "fields_written": [], "audit_event": "read-denied", "test_duty": "foreign tenant refused"}],
        "invariants": [{"id": "SI-01", "rule": "no lookup by a client key skips the tenant clause",
                        "capability": "tenant-scoped-query", "enforcement_layer": "application",
                        "owner_context": "Intake", "failure_mode": "closed",
                        "verification": "cross-owner refused"}],
        "secrets": {"inventory": [{"id": "SD-01", "name": "device credential", "owner": "Intake",
                                   "custody": "external-key-store", "rotation": "90d",
                                   "must_not_appear_in": ["source", "logs"]}],
                    "handling_rules": ["never logged"]},
        "error_policy": {"allowed_fields": ["code", "message", "correlation_key"],
                         "never_expose": ["stack traces"], "security_audit_events": []},
        "duties": [
            {"spec_ref": "AZ-01", "obligation": "admit only rows the caller owns within its tenant",
             "capability": "tenant-scoped-query", "unit_kind": "ownership-predicate"},
            {"spec_ref": "AZ-02", "obligation": "scope every read by the caller's tenant",
             "capability": "tenant-scoped-query", "unit_kind": "policy-adapter"},
            {"spec_ref": "SI-01", "obligation": "decide admission at the boundary, failing closed",
             "capability": "deny-by-default", "unit_kind": "policy-port"},
            {"spec_ref": "DC-01", "obligation": "mask classified fields on every egress surface",
             "capability": "log-redaction", "unit_kind": "redaction"},
            # 2026-11-24 principal law: an in-matrix principal's credential_capability must be
            # discharged by SOME duty (seed-002: bearer-jwt-proof had no duty, so no consumer
            # chain was ever scheduled and the scope-check guarded an unauthenticated road).
            {"spec_ref": "AZ-01", "obligation": "establish the device proof before any row decides",
             "capability": "proof-of-possession", "unit_kind": "credential-handling"}],
        "risks": [{"id": "R-01", "risk": "credential reuse", "likelihood": "medium",
                   "impact": "high", "mitigation": "SD-01 rotation", "residual": "rotation window"}],
        "open_questions": [],
    }
    if mutate:
        mutate(spec)
    SEC_FILE.write_text(json.dumps(spec))
    return spec


def sec_task(tid, stage, path, intent, export, deps=(), hints=None, layer=None):
    record = {"id": tid, "targetAgent": settings.STAGE_AGENTS[stage], "stage": stage,
              "dependsOn": list(deps), "path": path, "kind": settings.STAGE_KINDS[stage][0],
              "layer": layer or ("root" if stage == 0 else "application"), "feature": None,
              "export": export, "intent": intent, "project": SEC_SLUG}
    if hints is not None:
        record["ast_hints"] = hints
    return record


def sec_reset():
    """Clear this section's board only: ids are refused twice, and deleting another
    project's records would break pin closures the earlier sections still assert."""
    for folder in (settings.QUEUE_DIR, settings.ERROR_DIR):
        for stale in folder.glob(f"*-{SEC_SLUG}.json"):
            stale.unlink()


SEC_HINTS = {"package": "com.sec", "implements": [], "dependencies": [],
             "methods": [{"signature": "permits(String tenantKey)", "returns": "boolean",
                          "semantics": "true admits the caller, false rejects at the boundary"}]}
SEC_BOARD = [
    sec_task("T0-501", 0, "pom.xml", "Generate the sec project root and build scaffold",
             task_queue.SCAFFOLD_EXPORT),
    sec_task("T1-501", 1, "src/test/java/sec/AdmissionTest.java",
             "Test AZ-01: permitted caller, denied caller, and the cross-owner case where a "
             "valid key owned by another tenant is refused", "AdmissionTest", ("T0-501",),
             SEC_HINTS),
    sec_task("T2-501", 2, "src/main/java/sec/Admission.java",
             "Enforce AZ-01, SI-01 and the proof-of-possession credential-handling: the device "
             "secret is verified before the tenant-scoped-query predicate plus deny-by-default, "
             "applied inside the lookup, so a foreign key admits nothing and answers like a "
             "missing row", "Admission", ("T1-501",), SEC_HINTS),
    sec_task("T2-502", 2, "src/main/java/sec/Reader.java",
             "Enforce AZ-02 and DC-01: tenant-scoped-query on every read, log-redaction on "
             "egress fields", "Reader", ("T1-501",), SEC_HINTS),
]

sec_spec()
check("S1 the spec gate passes a lawful, capability-only spec",
      ddd.validate_security_spec(SEC_SLUG) is None, ddd.validate_security_spec(SEC_SLUG))
# 2026-11-24 seed-002: the stream surface's principal carried credential_capability
# bearer-jwt-proof and NO duty discharged it - duty coverage stayed complete while no
# unit could ever authenticate the caller (the consumer chain was never scheduled).
sec_spec(lambda s: s["duties"].pop(4))
check("S1p an in-matrix principal whose credential_capability is discharged by no duty is "
      "REFUSED (a row addressed to a credential nothing establishes is a guard on an "
      "unbuilt road - the bearer-jwt-proof hole, machine-killed at the spec)",
      "credential_capability" in str(ddd.validate_security_spec(SEC_SLUG))
      and "proof-of-possession" in str(ddd.validate_security_spec(SEC_SLUG)))
sec_spec()
# S1q (2026-11-24 seed-002 v2, the mirror hole): P-04 mutual-tls-proof addressed NO row -
# the plan shipped a network identity with no route that ever admits it (SI-10 claimed on
# the device chain, x509/ssl configured nowhere). Entry law, machine-killed at the spec.
sec_spec(lambda s: [r.update(principal_ids=[]) for r in s["authorization_matrix"]])
check("S1q a principal with authentication 'required' addressing NO authorization_matrix "
      "row is REFUSED (the consumer-entry law: an identity no declared face admits has "
      "nothing to enforce - the dangling mutual-tls/SI-10 class)",
      "addresses NO authorization_matrix row" in str(ddd.validate_security_spec(SEC_SLUG)))
sec_spec()
# DIG1 (2026-11-24 seed-002 v2): the digest matched an UNTABLED duty to a sibling row by
# unit_kind (SI-03 append-only-write, kind policy-adapter, got scope-check's hasAuthority
# mechanism) and the planner faithfully copied the manufactured poison. Row matching is
# TOKEN-only now; a shape says WHERE a duty lives, never WHICH mechanism holds it.
sec_spec(lambda s: s["duties"][1].update(capability="invented-write"))
_dig_strategy = settings.COMPLETE_DIR / f"execution-strategy-{SEC_SLUG}.json"
_dig_had_strategy = _dig_strategy.is_file()
if not _dig_had_strategy:
    _dig_strategy.write_text(json.dumps({
        "slug": SEC_SLUG, "report_type": "execution-strategy",
        "bounded_contexts": ["Intake"],
        "surfaces": [{"name": r["surface"], "kind": "http", "context": "Intake",
                      "operations": ["x"], "traced_from": "sec", "method": "POST", "path": "/x"}
                     for r in json.loads(SEC_FILE.read_text())["authorization_matrix"]],
        "persistence": {}, "observability": {}}), encoding="utf-8")
_dig_path, _dig_problems = ddd.write_phase2_digest(SEC_SLUG)
_dig = json.loads(_dig_path.read_text(encoding="utf-8")) if _dig_path else {}
_dig_duty = next((x for x in _dig.get("duties", []) if x.get("spec_ref") == "AZ-02"), {})
_dig_gaps = (_dig.get("mechanisms", {}).get("security") or {}).get("unmapped_duties") or []
if not _dig_had_strategy:
    _dig_strategy.unlink(missing_ok=True)
check("DIG1 an untabled capability token NEVER inherits a sibling row through a unit_kind "
      "collision: the duty arrives with table_row null AND lands in unmapped_duties (the "
      "channel that lawfully sends the planner to the table - where an absent token is a "
      "reported flow defect, never a borrowed mechanism)",
      _dig_problems == [] and _dig_duty.get("table_row") is None
      and any(g.split(":", 1)[0] == "AZ-02" for g in _dig_gaps))
sec_spec()
check("S2 an absent spec is a reason, never a pass (the phase must be seen to have run)",
      "not found" in ddd.validate_security_spec("no-such-domain"))
sec_spec(lambda s: s["authorization_matrix"][1].update(ownership_rule="none"))
check("S3 a row addressed by client-supplied ids with no ownership predicate is REFUSED "
      "(the IDOR law, machine-checkable in the artifact)",
      "IDOR" in str(ddd.validate_security_spec(SEC_SLUG)))
sec_spec(lambda s: s["duties"][0].update(spec_ref="AZ-99"))
check("S4 a duty pointing at a rule the spec never declares is REFUSED (broken handoff)",
      "no entry" in str(ddd.validate_security_spec(SEC_SLUG)))
sec_spec(lambda s: s["duties"].pop(1))
check("S5 a matrix row that discharges no duty is REFUSED (a rule nobody schedules is prose)",
      "no owning duty" in str(ddd.validate_security_spec(SEC_SLUG)))
sec_spec(lambda s: s["data_classification"][0].update(
    **{"class": "restricted", "log_visibility": "allowed"}))
check("S6 restricted data visible anywhere is REFUSED (the disclosure law)",
      "disclosure" in str(ddd.validate_security_spec(SEC_SLUG)))
sec_spec(lambda s: s["authorization_matrix"][0].update(principal_ids=["P-77"]))
check("S7 a row granting an undeclared principal is REFUSED",
      "no principals entry" in str(ddd.validate_security_spec(SEC_SLUG)))
sec_spec(lambda s: s["authorization_matrix"][0].update(default="permit"))
check("S8 deny-by-default is enforced, not advised",
      "must be 'deny'" in str(ddd.validate_security_spec(SEC_SLUG)))
sec_spec(lambda s: s["duties"][0].update(capability="TenantScopedQuery"))
check("S9 a capability token that is not an abstract token is REFUSED",
      "abstract token" in str(ddd.validate_security_spec(SEC_SLUG)))
sec_spec(lambda s: s["duties"][0].update(unit_kind="web-filter"))
check("S10 an invented duty kind is REFUSED (closed enumeration, not a suggestion)",
      "unit_kind" in str(ddd.validate_security_spec(SEC_SLUG)))

# --- the separation-of-concerns law: the spec may not decide the architect's job.
for label, mutate, at_path in (
        ("a framework product name",
         lambda s: s["duties"][0].update(
             obligation="Spring Security denies the row at the filter"), "duties[0].obligation"),
        ("an annotation",
         lambda s: s["authorization_matrix"][0].update(
             test_duty="@PreAuthorize rejects the caller"), "authorization_matrix[0].test_duty"),
        ("a class with a framework suffix",
         lambda s: s["authorization_matrix"][0].update(
             decision_point={"layer": "application", "component": "IntakeController"}),
         "authorization_matrix[0].decision_point.component"),
        ("a file name",
         lambda s: s["error_policy"].update(never_expose=["application.yml"]),
         "error_policy.never_expose[0]"),
        ("an assumption source citing an input FILE (the shape the reference itself used to "
         "teach: 2026-11-18 live - the agent obeyed '<input file or baseline rule>' and the "
         "gate refused it - only metadata.inputs may cite files)",
         lambda s: s["assumptions"][0].update(
             source="domain-boundary-sec.json assumption: security required"),
         "assumptions[0].source"),
        ("a package path",
         lambda s: s["duties"][0].update(obligation="declare com.sec.intake.Admission"),
         "duties[0].obligation"),
        ("a task id",
         lambda s: s["duties"][0].update(obligation="claimed by T2-004"), "duties[0].obligation"),
        ("a stage number",
         lambda s: s["duties"][0].update(obligation="installed at stage 0 by the scaffold"),
         "duties[0].obligation"),
        ("an agent name",
         lambda s: s["duties"][0].update(obligation="agent-container wires the keystore"),
         "duties[0].obligation"),
):
    sec_spec(mutate)
    refused = str(ddd.validate_security_spec(SEC_SLUG))
    check(f"S11 the gate refuses {label} at {at_path} - realization vocabulary is the "
          "architect's, with the tech-stack skill",
          "REALIZATION" in refused and at_path in refused, refused[:200])
sec_spec()
spec = sec_spec()
spec["duties"][0]["obligation"] = ("a traveller's passport number, a lab flask, the buffer queue, "
                                   "and how fast sensors react are all ordinary requirements")
spec["error_policy"]["allowed_fields"] = ["code", "message", "correlation_key"]
SEC_FILE.write_text(json.dumps(spec))
check("S11z ordinary domain English that merely LOOKS technical stays legal (passport is PII, "
      "a flask is glassware, a queue is a buffer, react is a verb, a stage is a phase of work)",
      ddd.validate_security_spec(SEC_SLUG) is None, ddd.validate_security_spec(SEC_SLUG))

print("== stage 0 identity and the emit gate")
sec_reset()
rc = emit(SEC_BOARD)
check("S12 emit ACCEPTS a decomposition that claims every duty by token",
      rc is None or not any("security duty" in line for line in str(rc).splitlines()), str(rc)[:260])
sec_reset()
rc = emit([t for t in SEC_BOARD if t["id"] != "T2-502"])
check("S13 an unclaimed security duty is REFUSED naming the token (the rule would ship in no "
      "unit while every per-unit gate stays green)",
      any("security duty AZ-02" in line for line in str(rc).splitlines()), str(rc)[:260])
bare = [dict(t) for t in SEC_BOARD]
bare[3]["intent"] = ("Enforce the read path per AZ-02 and DC-01 with a scoped query and masked "
                     "output")  # ids named, capability tokens paraphrased away
sec_reset()
rc = emit(bare)
check("S14b a claim that cites the duty id but never names its capability token is REFUSED "
      "(a citation is not a mapping: the duty looks covered and nothing was realized)",
      any("citation, not a mapping" in line for line in str(rc).splitlines()), str(rc)[:280])
shifted = [dict(t) for t in SEC_BOARD]
shifted[3]["intent"] = "Enforce AZ-07 on the read path"
sec_reset()
rc = emit(shifted)
check("S14 a spec_ref the spec never declared is REFUSED too (one plan, one vocabulary)",
      any("security entry AZ-07" in line for line in str(rc).splitlines()), str(rc)[:260])
sec_reset()
rc = emit([t for t in SEC_BOARD if int(t["stage"]) == 0])
check("S15 skip (b): a stage-0-only batch is never refused for duties it cannot claim - the "
      "database step would otherwise livelock on a board whose spec arrived late",
      rc is None, str(rc)[:220])
sec_reset()
settings.QUEUE_DIR.joinpath(f"T0-501-{SEC_SLUG}.json").write_text(json.dumps(SEC_BOARD[0]))
settings.QUEUE_DIR.joinpath(f"T0-509-{SEC_SLUG}.json").write_text(json.dumps(
    sec_task("T0-509", 0, "bootstrap-notes.md", "A dependency-free stage 0 sibling", "notes")))
check("S16 the scaffold resolves by its export marker even beside another dependency-free "
      "stage 0 task (the shape heuristic alone would credit whichever id sorted first)",
      task_queue.scaffold_task_id(SEC_SLUG) == "T0-501", task_queue.scaffold_task_id(SEC_SLUG))
sec_reset()
settings.QUEUE_DIR.joinpath(f"T0-510-{SEC_SLUG}.json").write_text(json.dumps(
    sec_task("T0-510", 0, "pom.xml", "A board written before the marker was taught", "notes")))
settings.QUEUE_DIR.joinpath(f"T0-511-{SEC_SLUG}.json").write_text(json.dumps(
    sec_task("T0-511", 0, "db/migrations/V1__x.sql", "A migration task", "V1__x", deps=("T0-510",))))
check("S17 the legacy fallback still finds the dependency-free non-migrations task, and a "
      "migration task is never mistaken for the scaffold",
      task_queue.scaffold_task_id(SEC_SLUG) == "T0-510", task_queue.scaffold_task_id(SEC_SLUG))

print("== prompts and profiles")
import prompts  # noqa: E402

SEC_REPO = Path(__file__).resolve().parents[1]
sec_msg = prompts.build_security_prompt(SEC_SLUG)
SEC_FLAT = " ".join(sec_msg.split())
sec_planner_msg = prompts.build_planner_prompt(
    ROOT, "runner", SEC_SLUG, "Intake", f"/tmp/tasks/{SEC_SLUG}-intake.json",
    f"/tmp/phase2-slice-{SEC_SLUG}-intake.json", None,
    {"T1": "T1-050", "T2": "T2-050", "T3": "T3-050"}, ["Intake"])
sec_planner_flat = " ".join(sec_planner_msg.split())
check("S17b the split planner's per-context brief demands the PAIR (spec_ref + capability "
      "VERBATIM beside the mechanism copied from the duty's own table_row), names the reach "
      "law and the closure list, routes the session to strategy + slice + symbols, and stops "
      "at ONE lint: the ENGINE runs the batch emit, so the atomic cross-context checks still "
      "see the whole plan while no session carries a second context's draft (2026-11-18 "
      "audit: one 57-task file forced a 40,442-token single output turn; the split's answer: "
      "the same law, the transcript cost of one ~8k context)",
      "READ EXACTLY THESE" in sec_planner_flat
      and "`table_row`" in sec_planner_flat
      and "spelling its `spec_ref` AND `capability` VERBATIM" in sec_planner_flat
      and "CROSS-OWNER case" in sec_planner_flat
      and "spec_ref -> claiming unit ids -> mechanism named -> surface unit" in sec_planner_flat
      and "--lint" in sec_planner_flat and "LINT-CLEAN" in sec_planner_flat
      and "Do NOT run" in sec_planner_flat
      and "the ENGINE emits the batch" in sec_planner_flat
      and "strategy-slice-" in sec_planner_msg
      and "arrives COMPLETE" in sec_planner_flat
      and "joined ONTO the duty" in sec_planner_flat)
check("S17c the refusal is machine-enforced, not just taught: the emit gate itself carries the "
      "mapping layer (source-level read of the gate, so a doc that promises it without the code "
      "fails here)",
      "citation, not a mapping" in inspect.getsource(task_queue._security_claim_errors)
      and "duty_caps" in inspect.getsource(task_queue._security_claim_errors))
check("S18 the security prompt renders its paths and ships no queue command",
      f"security-spec-{SEC_SLUG}.json" in sec_msg
      and not any(token in sec_msg for token in
                  ("{slug}", "{spec_path}", "{strategy_path}", "{slice_path}", "{map_path}"))
      and "python3" not in sec_msg and "/tmp/tasks" not in sec_msg)
check("S19 the security prompt commands the prohibition its gate enforces",
      "Your vocabulary is requirements only" in SEC_FLAT
      and "never an invented answer" in SEC_FLAT
      and "You queue nothing and you author no project file" in SEC_FLAT)
_planner_docs = [(SEC_REPO / ".opencode/agents/agent-planner-architect.md").read_text(),
                 (SEC_REPO / ".github/agents/agent-planner-architect.agent.md").read_text()]
check("S20 the PLANNER owns the mapping: the profile says the token-to-mechanism map is "
      "yours FROM the digest's row (a name the row does not carry is a defect to report, "
      "never a recall), and no planning brief hands out security stage-0 ids (none exist)",
      # 2026-11-25 carrier compression: the mapping-authority sentence moved from the
      # loop-only profiles into the per-context brief, where the session reads it with
      # the claim law it governs
      "YOU ALONE map a capability token" in " ".join(
          prompts.ARCHITECT_PLANNER_PROMPT.split())
      and "map it FROM its row" in " ".join(prompts.ARCHITECT_PLANNER_PROMPT.split())
      and "{security_ids}" not in sec_planner_msg and "security_ids" not in sec_planner_msg
      and "{security_ids}" not in prompts.ARCHITECT_PLANNER_REPAIR_PROMPT)
check("S21 phase 1 is told the security step reads its surfaces and data model",
      "The security step runs after you" in prompts.ARCHITECT_STRATEGY_PROMPT)
bodies = [(SEC_REPO / ".opencode/agents/agent-security-architect.md").read_text(),
          (SEC_REPO / ".github/agents/agent-security-architect.agent.md").read_text()]
frontmatter = bodies[0].split("---\n", 2)[1]
open_body, copilot_body = (b.split("---\n", 2)[2] for b in bodies)
check("S22 no tech-stack skill is granted to the security profile (the leak was the rule, not "
      "the wording: loading a stack skill puts framework idioms in the context that decides "
      "requirements)",
      "java-springboot3" not in frontmatter and "python-fastapi" not in frontmatter
      and "typescript-nestjs" not in frontmatter and "security-strategy: allow" in frontmatter
      and frontmatter.count("allow") <= 8)
check("S23 the profile edits ONLY its spec and runs ONLY the reader: no runner, no /tmp draft, "
      "no project tree write - it queues nothing",
      '"services/*/security/**"' not in frontmatter and '"/tmp/**"' not in frontmatter
      and "orchestrator_" not in frontmatter
      and '"blackboard/complete/security-spec-*.json": allow' in frontmatter)
check("S24 both profiles teach the same body and no queueing step (the .github skills folder "
      "is a symlink: one skill, two profiles, zero drift)",
      open_body == copilot_body and "--emit" not in open_body
      and "/tmp/tasks" not in open_body and "security-spec-<slug>.json" in open_body
      and "Budget <=8" in open_body)
check("S25 the engine's budget for this phase matches the profile it states",
      settings.SECURITY_AGENT == "agent-security-architect"
      and settings.call_budget(settings.SECURITY_AGENT) == 8
      and "Budget <=8" in open_body)

# --- Z. the SURFACE JOIN (Gap A) and the PLACEMENT law (Gap B), 2026-11-18 probe.
#     The probe that wrote this section shipped a plan whose every duty was claimed and whose
#     entry unit had no guard on its path, and a spec that tabled one row for a strategy with
#     four inbound surfaces - every gate green both times. Each case below is one of those two
#     shapes: a surface phase 1 hid, or a claim that sits on an island.
#     Ids live in the 67x band: `load_index` keys by ID alone, so a section that reuses another
#     section's id (T2-902 here once did) silently overwrites its record and the case passes for
#     the wrong reason.
import pipeline as pipeline_mod

Z_SLUG = "surf"
settings.DOMAIN_DIR.mkdir(parents=True, exist_ok=True)

Z_ROW = {"id": "AZ-01", "surface": "intake write", "operation": "POST",
         "principal_ids": ["P-01"], "roles": ["device"], "scopes": ["ingest"],
         "ownership_rule": "owner-and-tenant", "client_supplied_ids": ["device_key"],
         "decision_point": {"layer": "application", "component": "Intake"}, "default": "deny",
         "effect_on_deny": "unauthenticated", "fields_read": [], "fields_written": ["DC-01"],
         "audit_event": "intake-denied", "test_duty": "permitted, denied, cross-owner"}
Z_DUTY = {"spec_ref": "AZ-01", "obligation": "admit only rows the caller owns",
          "capability": "tenant-scoped-query", "unit_kind": "ownership-predicate"}


def z_strategy(surfaces=("intake write",), contexts=("Intake",), exempt=None):
    strat = {"slug": Z_SLUG, "language": "Java 21", "modules": [Z_SLUG],
             "layers": ["domain", "application", "interface"], "build_order": ["domain"],
             "bounded_contexts": list(contexts),
             "surfaces": [{"name": name, "kind": "http", "context": contexts[0],
                           "operations": ["POST"], "method": "POST", "path": "/x"} for name in surfaces],
             "persistence": {"data_model": "telemetry_record (tenant_id, device_key, value)"},
             "observability": FULL_FLOOR, "risks": []}
    if exempt:
        strat["contexts_without_inbound"] = exempt
    (ROOT / "blackboard" / "complete" / f"execution-strategy-{Z_SLUG}.json").write_text(
        json.dumps(strat))
    return strat


def z_spec(rows=(), duties=(), principals=None, invariants=(), questions=()):
    spec = sec_spec()   # the lawful S-block shape, retargeted at this section's slug
    spec.update({"slug": Z_SLUG, "authorization_matrix": list(rows) or [Z_ROW],
                 "duties": list(duties) or [Z_DUTY], "invariants": list(invariants),
                 "principals": principals if principals is not None else spec["principals"],
                 "open_questions": list(questions)})
    spec["trust_boundaries"] = []
    (settings.COMPLETE_DIR / f"security-spec-{Z_SLUG}.json").write_text(json.dumps(spec))
    return spec


(settings.DOMAIN_DIR / f"domain-boundary-{Z_SLUG}.json").write_text(json.dumps(
    {"bounded_contexts": [{"name": "Intake", "actors": ["IoT edge device"],
                           "consumes": ["Device transmissions (external)"]}]}))
z_spec()
z_strategy()
check("Z1 a lawful strategy naming its inbound surfaces passes the phase-1 gate",
      ddd.validate_strategy(Z_SLUG) is None, str(ddd.validate_strategy(Z_SLUG))[:200])
surfaceless = dict(z_strategy(), surfaces=None)
(ROOT / "blackboard" / "complete" / f"execution-strategy-{Z_SLUG}.json").write_text(
    json.dumps(surfaceless))
check("Z2 a strategy that names NO inbound surface is REFUSED at phase 1 (Gap A: the spec can "
      "only table rows for surfaces it was told about, and rule (y) discharges only that spec)",
      "surfaces" in str(ddd.validate_strategy(Z_SLUG)), str(ddd.validate_strategy(Z_SLUG))[:120])
z_strategy(surfaces=("intake write",), contexts=("Intake", "Archive"))
check("Z3 a declared context in neither `surfaces` nor `contexts_without_inbound` is REFUSED "
      "(silence is not a decision)",
      "Archive" in str(ddd.validate_strategy(Z_SLUG)), str(ddd.validate_strategy(Z_SLUG))[:200])
z_strategy(surfaces=("intake write",), contexts=("Intake", "Archive"),
           exempt=[{"context": "Archive", "reason": "store-only, no caller"}])
check("Z4 the exemption with a reason ACCEPTS", ddd.validate_strategy(Z_SLUG) is None,
      str(ddd.validate_strategy(Z_SLUG))[:200])
z_strategy(surfaces=("intake write", "sample read"))
check("Z5 a declared surface with NO authorization row is refused by the SPEC gate - 'the table "
      "is not empty' was never the law 'one row per surface' (Gap A)",
      "sample read" in str(ddd.validate_security_spec(Z_SLUG)),
      str(ddd.validate_security_spec(Z_SLUG))[:220])
z_strategy()
z_spec(invariants=[{"id": "SI-01", "rule": "no lookup skips the tenant clause",
                    "capability": "tenant-scoped-query", "enforcement_layer": "application",
                    "owner_context": "Nowhere", "failure_mode": "closed",
                    "verification": "cross-owner refused"}],
       duties=[Z_DUTY, {"spec_ref": "SI-01", "obligation": "decide at the edge, failing closed",
                        "capability": "deny-by-default", "unit_kind": "policy-port"}])
check("Z6 an invariant owned by a context the strategy never declared is REFUSED",
      "owner_context" in str(ddd.validate_security_spec(Z_SLUG)),
      str(ddd.validate_security_spec(Z_SLUG))[:200])
z_spec(invariants=())
principals = [{"id": "P-01", "name": "operator", "kind": "human", "source": "Nightly operator",
               "authentication": "required", "credential_capability": "bearer-jwt-proof",
               "identity_claims": ["tenant_id"]}]
z_spec(principals=principals)
check("Z7 a principal whose source cites no `actors`/`external_systems` entry is REFUSED "
      "(the traceability law was prose)",
      "Nightly operator" in str(ddd.validate_security_spec(Z_SLUG)),
      str(ddd.validate_security_spec(Z_SLUG))[:200])
z_spec(principals=None)
z_spec(questions=["the read surface carries no row: no input declared it"])
check("Z8 the pipeline reads what the spec leaves undecided (an open question is a STOP signal, "
      "not a filed-away note)", ddd.security_open_questions(Z_SLUG) != []
      and "open question(s)" in inspect.getsource(pipeline_mod.run)
      and "--replan" in inspect.getsource(pipeline_mod.build_parser),
      str(ddd.security_open_questions(Z_SLUG))[:120])
z_spec(questions=[])

Z_GUARD_HINTS = {"package": "com.surf.guard", "implements": [], "dependencies": [],
                 "methods": [{"signature": "permits(String tenantKey)", "returns": "boolean",
                              "semantics": "true admits, false denies at the boundary"}]}
Z_ENTRY_HINTS = {"package": "com.surf.entry", "implements": [], "dependencies": [],
                 "methods": [{"signature": "accept(byte[] payload)", "returns": "void",
                              "semantics": "acknowledges the packet"}],
                 "routes": [{"method": "POST", "path": "/api/samples", "duty": "serves"}]}
Z_ENTRY_PINNED = {"package": "com.surf.entry", "implements": [],
                  "dependencies": [{"type": "Guard", "task_id": "T2-673"}],
                  "methods": Z_ENTRY_HINTS["methods"],
                  "routes": [{"method": "POST", "path": "/api/samples", "duty": "serves"}]}


def z_board(entry_hints=Z_ENTRY_HINTS, entry_deps=("T1-672",), guard_stage=2, tester_intent=None):
    guard_intent = ("Enforce AZ-01 with the tenant-scoped-query ownership predicate at the lookup")
    if guard_stage == 3:
        guard = gtask("T3-673", "Guard", 3, deps=("T0-671",), intent=guard_intent,
                      project=Z_SLUG, path="src/main/java/surf/Guard.java", hints=Z_GUARD_HINTS)
    elif guard_stage == 1:
        guard = gtask("T1-673", "GuardTest", 1, deps=("T0-671",), intent=guard_intent,
                      project=Z_SLUG, path="src/test/java/surf/GuardTest.java",
                      hints=Z_GUARD_HINTS)
    else:
        guard = gtask("T2-673", "Guard", 2, deps=("T0-671",), intent=guard_intent,
                      project=Z_SLUG, path="src/main/java/surf/Guard.java", hints=Z_GUARD_HINTS)
        guard["observability"] = {"step_logs": ["packet received (IngressPacket)"]}
    entry_tester = gtask("T1-672", "EntryTest", 1, deps=("T0-671",),
                         intent=tester_intent or ("End-to-end request-path slice drives the "
                                                  "intake write surface and asserts the stored row"),
                         project=Z_SLUG, path="src/test/java/surf/EntryTest.java",
                         hints=entry_hints)
    entry = gtask("T2-672", "EntryHandler", 2, deps=entry_deps,
                  intent="POST /api/samples: the intake write surface accepts the device packet",
                  project=Z_SLUG, path="src/main/java/surf/EntryHandler.java",
                  hints=entry_hints)
    entry["layer"] = "interface"
    scaffold = gtask("T0-671", "Scaffold", 0, project=Z_SLUG, path="pom.xml",
                     intent="Generate the surf project root and build scaffold")
    scaffold["layer"] = "root"
    scaffold["export"] = task_queue.SCAFFOLD_EXPORT
    return [scaffold, guard, entry_tester, entry]


def z_reset():
    """Task records only: the section's strategy and spec must survive between cases, and
    a wildcard here would delete them with the board (they live in complete/ too)."""
    for folder in (settings.QUEUE_DIR, settings.ERROR_DIR, settings.COMPLETE_DIR):
        for stale in folder.glob(f"T[0-9]-*-{Z_SLUG}.json"):
            stale.unlink()


rc_z = emit(z_board())
check("Z9 (y2 REACH) an island guard - every duty claimed, the entry unit never pins it - is "
      "REFUSED naming the surface and both units (2026-11-18 probe B1: this plan was accepted)",
      bool(rc_z) and "intake write" in str(rc_z) and "T2-672" in str(rc_z), str(rc_z)[:260])
z_reset()
rc_z = emit(z_board(entry_hints=Z_ENTRY_PINNED,
                    tester_intent=("End-to-end request-path slice drives the intake write "
                                   "surface: AZ-01 permitted, denied, and the cross-owner case "
                                   "where a key owned by another tenant is refused")))
check("Z10 the SAME plan WIRED (entry pins the guard, its pair asserts the cross-owner case) is "
      "ACCEPTED - the law refuses the gap, not a style", rc_z is None, str(rc_z)[:260])
z_reset()
rc_z = emit(z_board(entry_deps=("T1-672", "T2-673"),
                    tester_intent=("End-to-end request-path slice drives the intake write "
                                   "surface: AZ-01 permitted, denied, cross-owner refused")))
check("Z11 an ordering edge alone (dependsOn, no collaborator pin) satisfies reach - the drain "
      "schedules on `dependsOn`, so the guard lands before the surface is frozen",
      rc_z is None, str(rc_z)[:200])
z_reset()
rc_z = emit(z_board(entry_hints=Z_ENTRY_PINNED))
check("Z12 (y3) wired but the paired stage-1 test never carries the CROSS-OWNER case: REFUSED "
      "- a rule proven only on its own unit test is a rule no request ever meets",
      bool(rc_z) and "CROSS-OWNER" in str(rc_z), str(rc_z)[:260])
for bad_stage in (1, 3):
    z_reset()
    rc_z = emit(z_board(guard_stage=bad_stage))
    check(f"Z13 (y1) a duty claimed only by a stage-{bad_stage} unit is REFUSED: no "
          "implementation carries it (probe B4/B4b: both were accepted)",
          bool(rc_z) and "claimed only by" in str(rc_z), str(rc_z)[:260])
z_reset()
unowned = z_board(entry_hints=Z_ENTRY_PINNED,
                  tester_intent=("End-to-end request-path slice drives the intake write "
                                 "surface: AZ-01 permitted, denied, cross-owner refused"))
unowned[0]["intent"] = "Generate the surf project root"
for record in unowned:
    if record["id"] == "T2-672":
        record["intent"] = "POST /api/samples accepts the device packet body"  # name dropped
rc_z = emit(unowned)
check("Z17 SURFACE OWNERSHIP: a declared surface no inbound unit names is REFUSED - otherwise "
      "the reach law could be dodged by never mentioning the surface",
      bool(rc_z) and "named by NO inbound unit" in str(rc_z), str(rc_z)[:240])
z_strategy()
_no_route = json.loads((ROOT / "blackboard" / "complete"
                        / f"execution-strategy-{Z_SLUG}.json").read_text())
for _s in _no_route["surfaces"]:
    if _s.get("kind") == "http":
        _s.pop("method", None)
        _s.pop("path", None)
(ROOT / "blackboard" / "complete" / f"execution-strategy-{Z_SLUG}.json").write_text(
    json.dumps(_no_route))
check("Z18 ROUTE JOIN AUTHORITY: an `http` surface with no tabled method+path is REFUSED at "
      "phase 1 (2026-11-24 v4: the surfaces table named the streaming surface but no path, so "
      "the first session GUESSED `GET /telemetry/stream` and the owning session served `GET "
      "/telemetry/stream/windows` - the two guards then cited different literals and the "
      "batch ping-ponged two repair sessions into a fatal; the route is a phase-1 PLAN fact, "
      "not a per-session guess)",
      bool(ddd.validate_strategy(Z_SLUG)) and "method" in str(ddd.validate_strategy(Z_SLUG))
      and "path" in str(ddd.validate_strategy(Z_SLUG)),
      str(ddd.validate_strategy(Z_SLUG))[:200])
z_strategy()
check("Z19 the restored strategy with tabled routes passes the gate again (the refusal is the "
      "missing columns, not the surface)",
      ddd.validate_strategy(Z_SLUG) is None, str(ddd.validate_strategy(Z_SLUG))[:160])
_inbound_units = getattr(task_queue, "_inbound_units")
_adapter = gtask("T2-674", "EventAdapter", 2, deps=("T0-671",),
                 intent="Unit IS the surface 'Consume events': typed events arrive from the "
                        "publisher and are windowed",
                 project=Z_SLUG, path="src/main/java/surf/application/EventAdapter.java")
_adapter["layer"] = "application"
check("Z20 (y5) SURFACE ENTRY IS PER-KIND: the detector that enforces surface OWNERSHIP reads "
      "an internal-call surface's ENTRY as the adapter that NAMES it - layer-neutral (2026-11-24 "
      "v4: the batch demanded a controller-shaped entry for a route-less consumer, and the "
      "repair answered by relabeling the consumer 'interface' while its package stayed "
      "/application/ - an HTTP-only law does not close the hole, it writes a layer lie)",
      _adapter not in _inbound_units([_adapter])
      and _adapter in _inbound_units([_adapter], ["consume events"]),
      str(_inbound_units([_adapter]))[:120])
z_reset()
# The resumed-board shape: units already ON the board (they predate the gate, so they claim
# nothing) - written straight to the queue, because the emit gate of today would refuse them.
(settings.QUEUE_DIR / f"T0-671-{Z_SLUG}.json").write_text(json.dumps(
    z_board()[0]))
(settings.QUEUE_DIR / f"T2-674-{Z_SLUG}.json").write_text(json.dumps(
    gtask("T2-674", "Reader", 2, deps=("T0-671",), intent="reads the stored rows back",
          project=Z_SLUG, path="src/main/java/surf/Reader.java",
          hints={"package": "com.surf.reader", "implements": [], "dependencies": [],
                 "methods": [{"signature": "rows()", "returns": "void"}]})))
_gaps_z = task_queue.security_claim_gaps(Z_SLUG)
check("Z14 security_claim_gaps reads the LIVE board (the resumed-board shape the emit gate "
      "structurally cannot police): duties no unit claims are reported for the pipeline to stop on",
      bool(_gaps_z) and any("security duty AZ-01" in line for line in _gaps_z),
      str(_gaps_z)[:200])
z_reset()
emit(z_board(entry_hints=Z_ENTRY_PINNED,
             tester_intent=("End-to-end request-path slice drives the intake write surface: "
                            "AZ-01 permitted, denied, cross-owner refused")))
# seed the /tmp planning state of THIS domain: digests, a slice, a draft and a symbol table
# - all scratch of the plan being archived, and replan must clear them (a next launch's
# claim step must never number itself against a plan that no longer exists)
(Path("/tmp") / f"phase2-digest-{Z_SLUG}.json").write_text("{}")
(Path("/tmp") / f"phase2-slice-{Z_SLUG}-intake.json").write_text("{}")
(task_queue.DRAFT_DIR).mkdir(parents=True, exist_ok=True)
(task_queue.DRAFT_DIR / f"{Z_SLUG}-intake.json").write_text("[]")
(task_queue.DRAFT_DIR / f"{Z_SLUG}-symbols-intake.json").write_text("{}")
moved = task_queue.replan_domain(Z_SLUG)
check("Z15 --replan archives the PLAN (strategy, spec, stage 1-3 records) and nothing else: "
      "stage 0 stays so the domain keeps its project root, the phases re-run because their "
      "inputs are gone, and the /tmp planning state (digest, slices, drafts, symbol tables) "
      "is dropped with the plan it described (2026-11-20 split: those files number the next "
      "plan's ids, and stale bytes would silently pre-number a fresh domain)",
      moved["strategy"] and moved["spec"] and moved["tasks"]
      and not (settings.COMPLETE_DIR / f"execution-strategy-{Z_SLUG}.json").is_file()
      and not (Path("/tmp") / f"phase2-digest-{Z_SLUG}.json").exists()
      and not (Path("/tmp") / f"phase2-slice-{Z_SLUG}-intake.json").exists()
      and not (task_queue.DRAFT_DIR / f"{Z_SLUG}-intake.json").exists()
      and not (task_queue.DRAFT_DIR / f"{Z_SLUG}-symbols-intake.json").exists()
      and (ROOT / "blackboard" / "archive" / f"execution-strategy-{Z_SLUG}.json").is_file()
      and (settings.QUEUE_DIR / f"T0-671-{Z_SLUG}.json").is_file()
      and not (settings.QUEUE_DIR / f"T2-672-{Z_SLUG}.json").is_file()
      and not (settings.COMPLETE_DIR / f"T2-672-{Z_SLUG}.json").is_file()
      and not list((settings.COMPLETE_DIR / f"T2-673-{Z_SLUG}.json").parent
                   .glob(f"T2-90*-{Z_SLUG}.json")),
      json.dumps(moved)[:200])
check("Z16 the hint that made a late spec advisory is gone: the pipeline stops the run on "
      "security claim gaps instead of printing and draining on",
      "[hint ] security" not in inspect.getsource(pipeline_mod.run)
      and "security claim gap(s)" in inspect.getsource(pipeline_mod.run))
z_reset()

_strategy_docs = [(SEC_REPO / ".opencode/agents/agent-strategy-architect.md").read_text(),
                  (SEC_REPO / ".github/agents/agent-strategy-architect.agent.md").read_text()]
_planner_docs2 = [(SEC_REPO / ".opencode/agents/agent-planner-architect.md").read_text(),
                  (SEC_REPO / ".github/agents/agent-planner-architect.agent.md").read_text()]
check("S26 each split agent's stated budget is the ENGINE's budget, sized for the calls its "
      "own contract demands (strategy: reads, skills, one strategy write, one scaffold emit; "
      "planner: three brief reads, skills, one draft, lint rounds) - the 2026-11-19 pairing "
      "of stated==engine survives the split per carrier, and only the PLANNER carries the "
      "mapping tables",
      settings.call_budget(settings.ARCHITECT_STRATEGY_AGENT) == 12
      and settings.call_budget(settings.ARCHITECT_PLANNER_AGENT) == 16
      and all("Budget <=12" in doc for doc in _strategy_docs)
      and all("Budget <=16" in doc for doc in _planner_docs2)
      and all("spring-security-architect: allow" in doc for doc in _planner_docs2[:1])
      and not any("spring-security-architect: allow" in doc for doc in _strategy_docs)
      and not any("task-decomposition-dag: allow" in doc for doc in _strategy_docs),
      f"{settings.call_budget(settings.ARCHITECT_STRATEGY_AGENT)}/"
      f"{settings.call_budget(settings.ARCHITECT_PLANNER_AGENT)}")

# --- R1: two orchestrator robustness laws (2026-11-24 v4/v6 live stops).
#     (1) the batch repair loop must not bill a round after a repair changed nothing -
#         v6: an operator SIGTERM landed between the first refusal and the second, the
#         engine re-emitted UNCHANGED drafts, refused identically, and launched the next
#         session anyway; a refusal the repair cannot touch is an operator decision.
#     (2) an agent child must never outlive the orchestrator - v4: the kill left an
#         orphan session streaming an unread transcript and billing turns.
import re as _r1_re
_pipe = (Path(__file__).resolve().parents[1] / "orchestrators/pipeline.py").read_text()
_r1_i = _pipe.find("reason = task_queue.emit_draft_batch(slug, drafted)")
_r1_body = _pipe[_r1_i:_pipe.find("\n    if reason:", _r1_i)] if _r1_i >= 0 else ""
_r1_claims = _pipe[:_r1_i]
check("R1a the batch repair loop guards the NO-OP round: fingerprint the drafts before "
      "and after each repair session and refuse to re-emit (or re-bill) identical bytes "
      "(2026-11-24 v6 live)",
      # (R3 2026-11-25) the fingerprint now runs over the ROUTED bucket's files:
      # a per-bucket repair that changes nothing is still unbillable, domain or not
      "_repair_fingerprint(slug, files) == before" in _r1_body
      and "NOT billed" in _r1_body.replace("\n", " ")
      and "_repair_fingerprint(slug, [context]) == before" in _r1_claims
      and "def _repair_fingerprint(slug, contexts):" in _pipe,
      _r1_body[:160])
_ar = (Path(__file__).resolve().parents[1] / "orchestrators/agent_runners.py").read_text()
_ar_cb = (Path(__file__).resolve().parents[1] / "orchestrators/copilot_backend.py").read_text()
check("R1b every spawned child is ADOPTED and killed when the orchestrator dies: the "
      "adoption shim + SIGTERM/SIGINT handler live in agent_runners, BOTH backends call "
      "adopt_child, and both RELEASE on completion so the death handler only ever kills "
      "live sessions (2026-11-24 v4 live: an orphan session billed turns after its parent "
      "was killed)",
      "signal.SIGTERM" in _ar and "signal.SIGINT" in _ar and "def adopt_child" in _ar
      and "def release_child" in _ar
      and "adopt_child(process)" in _ar and "release_child(process)" in _ar
      and "adopt_child(process)" in _ar_cb and "release_child(process)" in _ar_cb)

# R1d BEHAVIORAL: a SIGTERM'd orchestrator must leave NO agent process behind -
# the whole point of the adoption shim (2026-11-24 v6: budget kills of the node
# wrapper left the native copilot billed under init; a shim that only kills the
# wrapper is a shim that does not work).
import os as _r1d_os
import signal as _r1d_signal
import subprocess as _r1d_sub
import time as _r1d_time

_R1D_PARENT = (
    "import sys, time, os\n"
    "sys.path.insert(0, str(%r))\n"
    "import agent_runners\n"
    "p = agent_runners.subprocess.Popen([sys.executable, '-c', 'import time;"
    "subprocess.Popen([\'sleep\', \'300\']) as _; print(_, flush=True); time.sleep(280)'],"
    " stdout=-1, text=True, start_new_session=True)\n"
    "agent_runners.adopt_child(p)\n"
    "pid = int(p.stdout.readline())\n"
    "print('CHILD', pid, 'RUNNER', os.getpid(), flush=True)\n"
    "time.sleep(200)\n" % (str(Path(__file__).resolve().parents[1] / "orchestrators"),)
)
# the grandchild sleep is captured by the PARENT's group, not the child's own group;
# kill_child(process) SIGKILLs the registered child's GROUP, so a wrapper+native tree
# dies as one. The probe asserts the grandchild of a SIGTERM'd parent is gone.
_R1D_GRAND = (
    "import subprocess, time, sys\n"
    "kid = subprocess.Popen(['sleep', '300'])\n"
    "print(kid.pid, flush=True)\n"
    "time.sleep(280)\n"
)
_R1D_RUNNER = (
    "import sys, time, os\n"
    "sys.path.insert(0, str(%r))\n"
    "import agent_runners\n"
    "p = agent_runners.subprocess.Popen([sys.executable, '-c', %r],\n"
    "                                  stdout=-1, text=True, start_new_session=True)\n"
    "agent_runners.adopt_child(p)\n"
    "gp = int(p.stdout.readline())\n"
    "print('GRAND', gp, 'RUNNER', os.getpid(), flush=True)\n"
    "time.sleep(200)\n" % (str(Path(__file__).resolve().parents[1] / "orchestrators"),
                           _R1D_GRAND)
)
_r1d_r = _r1d_sub.Popen([sys.executable, "-c", _R1D_RUNNER],
                        stdout=_r1d_sub.PIPE, text=True,
                        cwd=str(Path(__file__).resolve().parents[1]))
try:
    _r1d_line = _r1d_r.stdout.readline().split()
    _r1d_grand = int(_r1d_line[1])
    _r1d_runner = int(_r1d_line[3])
    _r1d_time.sleep(0.5)
    _r1d_os.kill(_r1d_runner, _r1d_signal.SIGTERM)
    _r1d_time.sleep(1.5)
except (ValueError, IndexError):
    _r1d_grand, _r1d_runner = 0, 0
    print("[probe] R1d could not read the runner's pid line")
_r1d_alive = _r1d_grand > 0 and _r1d_os.path.exists(f"/proc/{_r1d_grand}")
try:
    _r1d_r.wait(timeout=10)
except Exception:
    pass
if _r1d_alive:
    _r1d_os.kill(_r1d_grand, _r1d_signal.SIGKILL)
check("R1d a SIGTERM'd orchestrator leaves NO agent process behind (behavioral: a real "
      "two-level spawn is TERM'd and the grandchild is reaped or the probe fails - the "
      "group kill, not the wrapper kill, is what the adoption shim exists for)",
      not _r1d_alive, f"grandchild {_r1d_grand} survived the parent's death")

# --- R2: the (p)-slice / format-mixing exception is stated by every carrier the
#     planning session reads, and the mixed draft the law demands is accepted by the
#     real validator (2026-11-24 v6: a mixing ban with no stated exception met the (p)
#     law and the session resolved the contradiction by DROPPING the requirement).
_p_brief = (Path(__file__).resolve().parents[1] / "orchestrators/prompts.py").read_text()
_p_prof0 = (Path(__file__).resolve().parents[1] / ".github/agents/agent-planner-architect.agent.md").read_text()
_p_prof1 = (Path(__file__).resolve().parents[1] / ".opencode/agents/agent-planner-architect.md").read_text()
_p_qr = (Path(__file__).resolve().parents[1] / ".opencode/skills/architect-practices/task-decomposition-dag/QUICKREF.md").read_text()
_p_skill = (Path(__file__).resolve().parents[1] / ".opencode/skills"
            / "architect-practices/task-decomposition-dag/SKILL.md").read_text()
check("R2a the (p) slice's lone stage-1 is the ONE named exception to one-shape-per-file "
      "in every LAW carrier a planning session reads (brief, quickref, contract) - the "
      "loop-only profiles defer the shape to the map (2026-11-25 carrier compression)",
      all("the (p) slice's lone stage-1" in " ".join(_txt.split())
          for _txt in (_p_brief, _p_qr, _p_skill)))

_mixed_batch = [{
    "n": 7, "project": "mixing-smoke", "layer": "domain", "feature": None,
    "dependsOn": ["T0-001"],
    "test": {"path": "src/test/java/x/CounterTest.java", "export": "CounterTest",
             "intent": "Counter counts up and resets at the cap: two increments assert 2, "
                       "reset asserts 0."},
    "code": {"path": "src/main/java/x/Counter.java", "export": "Counter",
             "intent": "Counter increments and wraps at the configured cap.",
             "ast_hints": {"package": "x", "implements": [], "dependencies": [],
                           "methods": [{"signature": "int next()", "returns": "int"}]}}},
    {"id": "T1-008", "targetAgent": "agent-tester", "stage": 1,
     "dependsOn": ["T0-001"], "path": "src/test/java/x/IngressSliceTest.java",
     "kind": "test", "layer": "interface", "feature": None, "export": "IngressSliceTest",
     "project": "mixing-smoke",
     "intent": "End-to-end slice drives the inbound request against the embedded store "
               "and asserts the durable row."}]
_mixed_exp, _mixed_errs = task_queue.expand_unit_draft(_mixed_batch)
_mixed_scaffold = {"id": "T0-001", "targetAgent": settings.STAGE_AGENTS[0],
                   "stage": 0, "dependsOn": [], "path": "pom.xml", "kind": "bootstrap",
                   "layer": "root", "feature": None, "export": "project_scaffold",
                   "project": "mixing-smoke", "intent": "scaffold",
                   "ast_hints": {"package": "x", "implements": [], "dependencies": [],
                                  "methods": []}}
_ar_src = (Path(__file__).resolve().parents[1] / "orchestrators/agent_runners.py").read_text()
_cb_src = (Path(__file__).resolve().parents[1] / "orchestrators/copilot_backend.py").read_text()
_r1c_adopt = (_ar_src[:_ar_src.find("def _dying")].count("adopt_child(process)")
              + _cb_src[:_cb_src.find("def run_discovery")].count("adopt_child(process)"))
# the call sites, not the def: agent_runners adopts inside _run_agent (4-space call),
# copilot_backend through the module reference; the helpers' own defs never match.
_r1c = ("\n    adopt_child(process)\n" in _ar_src
        and "agent_runners.adopt_child(process)" in _cb_src)
check("R1c the adopt call sits on the SPAWN path of both backends (module import of "
      "agent_runners included in copilot) and both spawn with start_new_session so "
      "kill_child can hit the group",
      "import agent_runners" in _cb_src and _r1c
      and "start_new_session=True" in _ar_src
      and "start_new_session=True" in _cb_src,
      "start_new_session=True" in _cb_src[:_cb_src.find("def run_discovery")])
check("R2b the MIXED draft the (p) law demands - a compact triad plus a lone stage-1 "
      "object - expands and validates without error: the gate accepts what the carriers "
      "teach (a law the validator contradicts is a format rule that eats requirements)",
      _mixed_errs == [] and [x["id"] for x in _mixed_exp] == ["T1-007", "T2-007", "T3-007", "T1-008"]
      and tasks_mod.validate(_mixed_exp[0], {**{x["id"]: x for x in _mixed_exp},
                                             "T0-001": _mixed_scaffold}) is None,
      str(_mixed_errs)[:160])

# --- SA. the risk register stops being a write-only field (2026-11-18).
#     `risks[]` was required to EXIST, its ids even resolved `spec_ref` citations, and then nothing read
#     its contents - while rule (y) and the profiles offered "an added unit OR a reported risk" as the
#     honest answer for a token the stack cannot realize. The risk branch led nowhere twice over: the
#     claim gate refuses any duty no unit claims, and the architect has no write path to the spec its
#     refusal message told it to amend.

def sa_risks(mutate=None):
    """Reset the SEC fixture's register to one control-backed risk, optionally break it."""
    spec = json.loads((settings.COMPLETE_DIR / f"security-spec-{SEC_SLUG}.json").read_text())
    entry = {"id": "R-01", "risk": "device credentials outlive their tenant binding",
             "likelihood": "medium", "impact": "high",
             "mitigation": "SD-01 rotation", "residual": "the rotation window itself"}
    spec["risks"] = [dict(entry)]
    if mutate:
        mutate(spec["risks"][0])
    (settings.COMPLETE_DIR / f"security-spec-{SEC_SLUG}.json").write_text(json.dumps(spec))
    return ddd.validate_security_spec(SEC_SLUG)

check("SA1 a risk backed by a control the spec declares passes (SD-01 exists in this artifact)",
      sa_risks() is None, str(sa_risks())[:200])
check("SA2 a risk whose mitigation names no entry in the spec is REFUSED - duty closure covered "
      "duties only, so a finding could dangle off the edge of the artifact unread",
      "cites no entry" in str(sa_risks(lambda r: r.update(
          mitigation="the platform team will handle this somewhere else"))), str(sa_risks())[:200])
check("SA3 a risk with NEITHER a control nor an accepted posture is REFUSED (an empty mitigation is "
      "the silent-drop shape: written down, owned by nobody, forgotten by the drain)",
      "neither a mitigation" in str(sa_risks(lambda r: r.update(mitigation=""))), str(sa_risks())[:200])
check("SA4 accepting a risk is legal ON THE RECORD: the posture prefix plus a stated residual passes",
      sa_risks(lambda r: r.update(mitigation="accepted: out-of-scope for this build",
                                  residual="credentials never rotate inside the boundary")) is None,
      str(sa_risks())[:200])
check("SA5 ... and an 'accepted' with no residual is still refused - silence is not acceptance",
      "must state what remains exposed" in str(sa_risks(lambda r: r.update(
          mitigation="accepted: we will not rotate here", residual=""))), str(sa_risks())[:200])
check("SA6 the register is READ by the pipeline on every launch, including the resume path where the "
      "spec was already valid and the phase printed nothing (an accepted exposure must be a line an "
      "operator saw, not a field that aged out of a JSON file)",
      "risk" in str(ddd.security_risks(SEC_SLUG)[0])
      and inspect.getsource(pipeline_mod.run).count("_surface_security_risks(slug)") >= 2
      and '[risk  ]' in inspect.getsource(pipeline_mod._surface_security_risks))
sec_spec()
_arch_profile = (SEC_REPO / ".opencode/agents/agent-planner-architect.md").read_text()
_claim_refusal = inspect.getsource(task_queue._security_claim_errors)
check("SA7 the unclaimed-duty refusal no longer orders the session to amend a file it cannot "
      "write (the planner's edit grant is the strategy + /tmp only - never a spec), and the "
      "gate names the lawful landing unit instead",
      "security-spec-*.json" not in _arch_profile.split("shell:")[0]
      and "execution-strategy-*.json" in _arch_profile.split("shell:")[0]
      and "reported risk never substitutes for a claiming unit" in _claim_refusal
      and "re-run the security phase" in _claim_refusal
      and "CONFIG unit" in _claim_refusal,
      _arch_profile.split("shell:")[0][-160:])

# --- SB. security is ALWAYS implemented, with exactly one lawful exception (2026-11-18).
#     Review question: does the flow implement the security strategy everywhere, and omit it only when
#     the business description says so? Enforcement was already unconditional (mandatory phase, fatal on
#     absence, non-empty matrix/duties, claim coverage + (y1)/(y2)/(y3)); what was missing was (a) the
#     waiver - and a waiver no agent may decide for itself - and (b) a real escape hatch: every later
#     phase iterates STRATEGY slugs, so a domain the architect never planned lost its spec in silence.
W_SLUG = "waiv"
W_SEED = ROOT / "seed-waiv.md"
W_SEED.write_text("# Bike Ops\n"
                  "This is an internal single-operator tool: it needs no authentication, "
                  "authorization or data protection at all.\n"
                  "Samples are ingested from the bench rig every second.\n")


def sb_slice(directive=None, source=True):
    report = {"schema_version": "1.0", "report_type": "domain-slice",
              "metadata": {"generated_at": "2026-11-18T00:00:00Z",
                           "agent": "domain-boundary-discovery"},
              "subdomain": {"name": "Waiv", "type": "core", "capability": "c", "why_distinct": "w"},
              "ubiquitous_language": [{"term": "Sample", "context": "In", "definition": "d"}],
              "bounded_contexts": [{"name": "In", "responsibility": "r", "in_scope": [],
                                    "out_of_scope": [], "ubiquitous_language": [], "invariants": [],
                                    "source_of_truth": [], "publishes": [], "consumes": [],
                                    "actors": ["bench rig"], "confidence": "high"}],
              "assumptions": []}
    if source:
        report["metadata"]["source_description"] = "seed-waiv.md"
    if directive:
        report["security_directive"] = directive
    (settings.DOMAIN_DIR / f"domain-boundary-{W_SLUG}.json").write_text(json.dumps(report))


def sb_strategy(slug):
    (settings.COMPLETE_DIR / f"execution-strategy-{slug}.json").write_text(json.dumps(
        {"slug": slug, "modules": [slug], "layers": ["domain"], "build_order": ["domain"],
         "risks": [], "bounded_contexts": ["In"],
         "surfaces": [{"name": "sample write", "kind": "http", "context": "In",
                       "operations": ["POST"], "method": "POST", "path": "/x"}],
         "observability": FULL_FLOOR}))


sb_slice()
check("SB1 no directive = SECURITY REQUIRED (the default survives: the waiver is an exception an "
      "agent must argue for with the user's own words, never an absent field)",
      ddd.security_waived(W_SLUG) is False and ddd.validate_security_directives() is None)
check("SB2 a strategy missing for a discovered slice is now FATAL: every later phase iterates "
      "strategy slugs, so the silent loss of one domain used to cancel its security phase too",
      W_SLUG in str(ddd.validate_strategy_coverage())
      and "no execution strategy" in str(ddd.validate_strategy_coverage()),
      str(ddd.validate_strategy_coverage())[:150])
sb_strategy(W_SLUG)
check("SB2b writing that one strategy clears the refusal for its domain (the gate names slugs, it "
      "does not blame the whole board)",
      W_SLUG not in str(ddd.validate_strategy_coverage() or ""),
      str(ddd.validate_strategy_coverage())[:150])
sb_slice(directive={"required": False, "source": "description",
                    "quote": "it needs no authentication, authorization or data protection at all"})
waived, note = ddd._waiver_note(W_SLUG)
check("SB3 a waiver copied VERBATIM from the description is honored, and the note names both the "
      "sentence and the file it was checked against (so a green run says who decided)",
      waived and "seed-waiv.md" in note and "no authentication" in note, f"{waived} {note}")
check("SB3b the waiver also satisfies the discovery post-check",
      ddd.validate_security_directives() is None, str(ddd.validate_security_directives())[:160])
sb_slice(directive={"required": False, "source": "description",
                    "quote": "the operators agreed security is not needed for this tool"})
waived, note = ddd._waiver_note(W_SLUG)
check("SB4 a PARAPHRASE is not a quote: refused, and the reason is returned to the session that can "
      "still fix it (discovery is the only agent holding the description text)",
      not waived and "not a sentence of" in note
      and "VERBATIM" in str(ddd.validate_security_directives()), f"{waived} {note}"[:160])
sb_slice(directive={"required": False, "source": "description",
                    "quote": "it needs no authentication, authorization or data protection at all"},
         source=False)
check("SB5 an unverifiable waiver is no waiver: without metadata.source_description there is no "
      "witness to grep, so the phase runs and the security strategy is implemented",
      not ddd.security_waived(W_SLUG)
      and "source_description" in str(ddd.validate_security_directives()),
      str(ddd.validate_security_directives())[:160])
sb_slice()
src_run = inspect.getsource(pipeline_mod.run)
src_tree = inspect.getsource(pipeline_mod._terminal_tree_report)
check("SB6 the flow acts on a verified waiver out loud: the security phase prints WAIVED with the "
      "quote and the file, the terminal tree verdict carries SECURITY WAIVED by directive, and the "
      "domain is never left looking defended",
      "WAIVED by the business description" in src_run and "_waiver_note(slug)" in src_run
      and "SECURITY WAIVED by directive" in src_tree and ddd.security_waived.__name__ in src_tree
      # and a waiver that arrives AFTER a spec was written discloses the contradiction instead of
      # letting the stale spec enforce claims silently (or the waived domain look un-waived)
      and "it now contradicts" in src_run and "BUT A SPEC IS ON DISK" in src_tree)
check("SB6b a waiver is never a shortcut past planning: coverage and directive verification run "
      "BEFORE the security loop can skip anything (an unplanned domain cannot waive its way out), and "
      "the surfaces contract is untouched by the waiver",
      src_run.index("validate_strategy_coverage()") < src_run.index("_waiver_note(slug)")
      and src_run.index("validate_security_directives()") < src_run.index("_waiver_note(slug)")
      and "validate_security_directives" in inspect.getsource(ddd.validate_domain_files)
      and "surfaces" in inspect.getsource(ddd.validate_strategy)
      and "security_directive" not in inspect.getsource(ddd.validate_strategy))
_backend_src = "".join((SEC_REPO / "orchestrators" / name).read_text()
                       for name in ("opencode_backend.py", "copilot_backend.py"))
check("SB7 both backends refuse to finish phase 1 while any discovered slice lacks a strategy - the "
      "repair happens inside the session that can still write it",
      _backend_src.count("ddd.validate_strategy_coverage()") == 2
      and "validate_security_directives" in inspect.getsource(ddd.validate_domain_files))
for stale in (settings.DOMAIN_DIR / f"domain-boundary-{W_SLUG}.json",
              settings.COMPLETE_DIR / f"execution-strategy-{W_SLUG}.json", W_SEED):
    stale.unlink(missing_ok=True)

# --- SD. the plan phase is a token budget: the batch shape and the intent wall (2026-11-18 audit).
def sd_hints(pkg, methods=None, deps=None):
    return {"package": pkg, "implements": [], "dependencies": deps or [],
            "methods": methods or [{"signature": "go()", "returns": "void",
                                    "semantics": "true ran, false did not"}]}


def sd_task(tid, stage, intent, export, deps=(), hints=None, path=None):
    rec = {"id": tid, "targetAgent": settings.STAGE_AGENTS[stage], "stage": stage,
           "dependsOn": list(deps), "path": path or f"src/main/java/m/{export}.java",
           "kind": settings.STAGE_KINDS[stage][0], "layer": "domain", "feature": None,
           "export": export, "intent": intent, "project": "mult"}
    if hints is not None:
        rec["ast_hints"] = hints
    return rec


def sd_emit(*batches):
    """One --emit call over SEVERAL draft files, exactly as the per-context shape emits."""
    for folder in (settings.QUEUE_DIR, settings.ERROR_DIR):
        for stale in folder.glob("*-mult.json"):
            stale.unlink()
    files = []
    for position, batch in enumerate(batches, start=1):
        file = ROOT / f"sd-draft-{position}.json"
        file.write_text(json.dumps(batch))
        files.append(str(file))
    return task_queue.emit_tasks(files)


CONTEXT_A = [sd_task("T2-720", 2, "owns the writer", "Writer", hints=sd_hints("com.m.a"))]
CONTEXT_B = [sd_task("T2-721", 2, "pins the writer across the file boundary", "Sender",
                     hints=sd_hints("com.m.b", deps=[{"type": "Writer", "task_id": "T2-720"}]))]
rc_sd = sd_emit(CONTEXT_A, CONTEXT_B)
check("SD1 per-context files still arrive as ONE batch: a pin whose producer lives in the other "
      "file resolves (the cross-context checks see the whole plan), so splitting the draft does not "
      "split the validation",
      rc_sd is None and (settings.QUEUE_DIR / "T2-720-mult.json").is_file()
      and (settings.QUEUE_DIR / "T2-721-mult.json").is_file(), str(rc_sd)[:220])
rc_sd = sd_emit(CONTEXT_A, CONTEXT_A)
check("SD1b one shared id space across the files: a duplicate in a sibling draft is refused, not "
      "silently queued twice",
      bool(rc_sd) and "already exists" in str(rc_sd), str(rc_sd)[:200])
for folder in (settings.QUEUE_DIR, settings.ERROR_DIR):
    for stale in folder.glob("*-mult.json"):
        stale.unlink()
long_intent = " ".join(f"word{i}" for i in range(181))
short_intent = " ".join(f"word{i}" for i in range(180))
wall = sd_task("T2-722", 2, long_intent, "Verbose", hints=sd_hints("com.m.c"))
check("SD2 the intent wall bites at PLANNING (23,585 tokens of plan, 52% of them prose; the "
      "biggest single output turn on record 40,442 tokens) - and only at planning: a resumed board "
      "with an old long intent stays readable, the same phase-order discipline as every other "
      "planning-only rule",
      "intent runs to 181 words" in str(tasks_mod.validate(wall, {}, planning=True))
      and tasks_mod.validate(wall, {}, planning=False) is None
      and tasks_mod.validate(sd_task("T2-723", 2, short_intent, "JustUnder",
                                     hints=sd_hints("com.m.d")), {}, planning=True) is None,
      str(tasks_mod.validate(wall, {}, planning=True))[:120])
_remedy = inspect.getsource(task_queue.emit_tasks)
check("SD3 the refusal text asks for an EDIT pass over the named task objects (measured: an edit "
      "cost 256-448 output tokens where the demanded rewrite cost 13,288) and still reports every "
      "error in one message, so the batch-report law that prevents re-emit loops is untouched",
      "by EDITING the named task objects" in _remedy and "never regenerate the whole plan" in _remedy
      and "one rewrite of the draft file" not in _remedy
      and "Every validation error is reported in ONE message" in _remedy)
_tasks_brief = prompts.build_planner_prompt(
    ROOT, "runner", "dom", "Alpha", "/tmp/tasks/dom-alpha.json",
    "/tmp/phase2-slice-dom-alpha.json", None,
    {"T1": "T1-010", "T2": "T2-010", "T3": "T3-010"}, ["Alpha", "Beta"])
_sd_profiles = [(SEC_REPO / ".opencode/agents/agent-planner-architect.md").read_text(),
                (SEC_REPO / ".github/agents/agent-planner-architect.agent.md").read_text()]
check("SD4 the generator-script ban lives in every carrier the planning phase reads (2026-11-18 "
      "live: the brief demanded 'a single JSON document' while step 3 said per-context files - "
      "the contradiction itself pushed the architect into gen_telemetry_tasks.py: 91k carried, "
      "41k worst single-turn output): the per-context brief bans scripts, teaches ONLY the "
      "one-array-one-file shape of THIS session's context, and both planner profiles carry the "
      "ban (the split makes the ban cheaper to obey: the session drafts exactly one file by "
      "construction, so the escape into a generator has no arithmetic left to justify it)",
      "generator script" in _tasks_brief and "single JSON document" not in _tasks_brief
      and "one JSON array" in _tasks_brief
      and "DRAFT one JSON array" in _tasks_brief
      and all("generator script" in b for b in _sd_profiles))
_closeout_src = inspect.getsource(tdd_engine._tester_close_out)
_sec_plan_skill = (SEC_REPO / ".opencode/skills/tech-stack-architect/spring-security-architect"
                   / "SKILL.md").read_text()
_manifest_task = {"id": "T0-799", "targetAgent": settings.STAGE_AGENTS[0], "stage": 0,
                  "dependsOn": [], "path": "pom.xml", "kind": "bootstrap", "layer": "root",
                  "feature": None, "export": "build-manifest",
                  "intent": "Move the verified pom.xml in place: add the security starter and "
                            "spring-security-test test-scoped; the parent owns versions.",
                  "project": "mult"}
_bad_manifest = dict(_manifest_task, dependsOn=["T0-798"])
check("SD5 the build-manifest duty has a lawful channel in EVERY carrier the security mapping "
      "reads (2026-11-18 live: spring-security-architect ordered 'schedule the manifest duty "
      "before any tester runs' while the tasks brief forbade ALL stage 0 output - the architect "
      "obeyed both, so no coordinate was scheduled and the drain died at the first red compile "
      "importing org.springframework.security.*): the brief names the ONE exception, the "
      "profiles teach it, the fatal states the remedy, the planning table names its channel, "
      "and the validator accepts the exact shape (layer root, empty dependsOn, kind bootstrap) "
      "while still refusing a staged manifest",
      "queued by the ENGINE from the stack table" in " ".join(_tasks_brief.split())
      and "You NEVER schedule a manifest" in " ".join(_tasks_brief.split())
      and all("schedule none" in b for b in _sd_profiles)
      and "Remedy" in _closeout_src and "build-manifest" in _closeout_src
      and "PHASE 1.5" in _sec_plan_skill
      and tasks_mod.validate(_manifest_task, {}, planning=True) is None
      and bool(tasks_mod.validate(_bad_manifest, {}, planning=True)),
      str(tasks_mod.validate(_manifest_task, {}, planning=True))[:160])
_drain_src = inspect.getsource(tdd_engine.drain_queue)
_sd_manifest = {"id": "T0-900", "targetAgent": settings.STAGE_AGENTS[0], "stage": 0,
                "dependsOn": [], "path": "pom.xml", "kind": "bootstrap", "layer": "root",
                "feature": None, "export": "build-manifest", "intent": "move the verified pom",
                "project": "mult"}
(settings.QUEUE_DIR / "T0-900-mult.json").write_text(json.dumps(_sd_manifest))
_sd_pending_manifest = tdd_engine._manifest_duty_pending("mult")
(settings.QUEUE_DIR / "T0-900-mult.json").unlink()
_sd_source = dict(_sd_manifest, path="src/main/java/m/Writer.java")
(settings.QUEUE_DIR / "T0-900-mult.json").write_text(json.dumps(_sd_source))
_sd_pending_source = tdd_engine._manifest_duty_pending("mult")
(settings.QUEUE_DIR / "T0-900-mult.json").unlink()
check("SD6 the resume classpath gate cannot deadlock the lawful remedy (2026-11-18 live: the "
      "emitted build-manifest duty sat in the queue while the gate re-read the pre-duty pom on "
      "EVERY relaunch - fataling on a gap the duty exists to fill; and a stale record whose file "
      "on disk was already reroute-clean was never re-recorded because the repair said 'nothing "
      "changed', so a package no file imports blocked the drain forever; and the skip-agent "
      "resume guard 'completed' the manifest duty without a session because the build file "
      "always already exists): the gate defers while a manifest duty is queued, the re-record "
      "is unconditional, the deferral predicate keys on a queued stage-0 bootstrap task whose "
      "path is a real build file, the skip guard exempts exactly that family, and a SCAFFOLD "
      "task on the same path is NOT a manifest duty",
      "_manifest_duty_pending" in _drain_src
      and "if not test_gate.repair_test_imports" not in _drain_src
      and "not _build_manifest_duty(task)" in _drain_src
      and _sd_pending_manifest and not _sd_pending_source
      and tdd_engine._build_manifest_duty(_sd_manifest)
      and not tdd_engine._build_manifest_duty(dict(_sd_manifest,
                                                   export=task_queue.SCAFFOLD_EXPORT))
      and not tdd_engine._build_manifest_duty(_sd_source))
check("SD7 the build-manifest duty's MUTATION is machine-verified (2026-11-18 live: the "
      "container halted the duty with the honest report 'T0-007 failed: no pom was moved', the "
      "session exited 0, the existence guard found the scaffold's own pom, and [done] landed "
      "against an untouched classpath - the false [done] then re-fataled every relaunch, "
      "because the deferral predicate had no queued duty to see anymore): the invoke seam "
      "refuses 'delivered' while the build file was not touched, and a failed duty is named "
      "as what it is",
      "build-manifest duty ended with" in _drain_src and "st_mtime < started" in _drain_src
      and 'what = ("build-manifest duty"' in _drain_src)
_orig_ext = test_gate.external_type_index
test_gate.external_type_index = lambda root: {"DatabaseClient": ["org.springframework.r2dbc.core.DatabaseClient"]}
_hole_task = {"id": "T2-037", "project": "holeproj",
              "path": "src/test/java/x/SliceTestSupport.java"}
_hallucinated = {"verdict_version": 2, "status": "compile_error",
                 "missing_symbols": ["Parameters"], "member_demands": [],
                 "package_symbol_demands": [{"symbol": "Parameters",
                                             "package": "org.springframework.r2dbc.core"}],
                 "blamed_files": ["R2dbcTelemetryRecordRepository.java"]}
_unknown_pkg = {"verdict_version": 2, "status": "compile_error",
                "missing_symbols": ["Ghost"], "member_demands": [],
                "package_symbol_demands": [{"symbol": "Ghost", "package": "com.nosuch.pkg"}],
                "blamed_files": ["A.java"]}
_holes_hallucinated = tdd_engine._unresolvable_missing(_hallucinated, _hole_task)
_holes_unknown = tdd_engine._unresolvable_missing(_unknown_pkg, _hole_task)
test_gate.external_type_index = _orig_ext
check("SD8 a class located INSIDE an existing classpath package is a payload defect of the "
      "importing unit, never a scheduling hole (2026-11-18 live: a coder wrote import "
      "org.springframework.r2dbc.core.Parameters; javac located the symbol in a RESOLVABLE "
      "package - no task can export classes into someone else's library - yet the classifier "
      "aborted a healthy domain at task 8 of ~110 telling the operator to run closure.py; "
      "with the symbol discarded the established all-foreign-blame rule defers the bystander "
      "and charges the guilty unit's own gate), while a package the classpath never provides "
      "stays a possible hole, conservatively",
      _holes_hallucinated == [] and _holes_unknown == ["Ghost"])
check("SD10 the wave cache's grammar version is ONE constant shared by the per-unit wave, the "
      "wave write, and the terminal suite gate (2026-11-18 live: the per-unit memo version moved "
      "with the widened demands but the three '-v9-' wave literals stayed behind, so every unit "
      "of the tree was served the PRE-demand verdict by _shared_verdict - full evidence in the "
      "log, zero member_demands in the field, everyone deferred, zero progress passes forever)",
      test_gate.WAVE_GRAMMAR not in ("v9",)
      and "-v9-" not in (SEC_REPO / "orchestrators/test_gate.py").read_text()
      and "-v9-" not in (SEC_REPO / "orchestrators/tdd_engine.py").read_text()
      and "WAVE_GRAMMAR" in (SEC_REPO / "orchestrators/tdd_engine.py").read_text())
_wave_src = inspect.getsource(test_gate.wave_gate_verdict)
check("SD11 a wave-build environment fault is never served as a unit verdict: it would reach "
      "green_test_result's memo write and replay under the unit's own fingerprint as 'cached "
      "verdict' forever (observed live 2026-11-18: a detached probe process with a wrong "
      "workspace root primed wave-telemetry-ingestion-v10-da39a3ee... - the empty-directory "
      "hash - with an EXEC_ERROR, teaching the drain a fact about a directory that never "
      "existed); the wave path now declines to None, leaving the loud EXEC_ERROR abort to the "
      "unit's scoped gate",
      "return None" in _wave_src and '"reason": str(exc)' not in _wave_src)
_sd12_task = {"id": "T2-019", "stage": 2, "project": "multk", "targetAgent": "agent-coder",
              "kind": "code", "layer": "infrastructure", "feature": None,
              "path": "src/main/java/x/R2dbcTelemetryRecordRepository.java",
              "export": "com.x.R2dbcTelemetryRecordRepository", "dependsOn": [],
              "intent": "append-only store adapter"}
_sd12_peer = {"id": "T2-780", "stage": 2, "project": "multk", "targetAgent": "agent-coder",
              "kind": "code", "layer": "application", "feature": None,
              "path": "src/main/java/x/IngestPacketUseCase.java",
              "export": "com.x.IngestPacketUseCase", "dependsOn": [], "intent": "the caller"}
(settings.QUEUE_DIR / "T2-780-multk.json").write_text(json.dumps(_sd12_peer))
(settings.QUEUE_DIR / "T2-019-multk.json").write_text(json.dumps(_sd12_task))
_ext11 = test_gate.external_type_index
test_gate.external_type_index = lambda root: {"DatabaseClient": ["org.springframework.r2dbc.core.DatabaseClient"]}
_sd12_result = {"verdict_version": 2, "status": "compile_error", "exit_code": 1,
                "missing_symbols": ["Parameters", "LATE"], "bean_demands": [],
                "problem_kinds": [{"file": "R2dbcTelemetryRecordRepository.java", "line": 13,
                                   "kind": "missing-symbol"},
                                  {"file": "IngestPacketUseCase.java", "line": 84,
                                   "kind": "missing-symbol"}],
                "blamed_files": ["R2dbcTelemetryRecordRepository.java",
                                 "IngestPacketUseCase.java"],
                "package_symbol_demands": [{"symbol": "Parameters",
                                            "package": "org.springframework.r2dbc.core"}],
                "member_demands": [{"member": "LATE", "owner": "ValidationStatus",
                                    "kind": "variable"}],
                "excerpt": ["[ERROR] /x/R2dbcTelemetryRecordRepository.java:[13,38] cannot find symbol"]}
_sd12_charged = tdd_engine._blocked_by_peers(_sd12_result, _sd12_task)
_sd12_control = json.loads(json.dumps(_sd12_result))
_sd12_control["package_symbol_demands"][0]["package"] = "com.nosuch.library"
_sd12_control["missing_symbols"] = ["Ghost"]
_sd12_deferred = tdd_engine._blocked_by_peers(_sd12_control, _sd12_task)
test_gate.external_type_index = _ext11
for _stale in (settings.QUEUE_DIR / "T2-780-multk.json", settings.QUEUE_DIR / "T2-019-multk.json"):
    _stale.unlink()
check("SD12 the own-file import of a class that an EXISTING library package does not provide "
      "is charged to the file's owner even while a peer's blamed file keeps the cascade rule "
      "true (2026-11-18 live: Parameters at line 13 of R2dbcTelemetryRecordRepository.java - "
      "T2-019's own file - was starved by the ANY-foreign defer because IngestPacketUseCase "
      "belonged to T2-017; consumed stayed 0 and the domain stuck forever on 75 blocked); a "
      "package the classpath never provides does not prove a hallucinated import and keeps the "
      "classic defer",
      _sd12_charged is False and _sd12_deferred is True)
_sd13_root = SEC_REPO / "gauntlet" / ".sd13-fork-corruption"
_sd13_reports = _sd13_root / "target" / "surefire-reports"
_sd13_reports.mkdir(parents=True, exist_ok=True)
_sd13_dump = _sd13_reports / "2026-11-18T17-11-37_934-jvmRun1.dumpstream"
_sd13_dump.write_text("# Created at 2026-11-18T17:11:39.227\nTruncated class file\n")
_sd13_detected = test_gate._fork_boot_corruption(_sd13_root)
_sd13_dump.unlink()
_sd13_clean = test_gate._fork_boot_corruption(_sd13_root)
# (2026-11-25 review fix) the SAME wound in the other stacks: a Gradle fork crash
# reports under build/test-results, and a killed tsc build leaves a TRUNCATED
# .tsbuildinfo that poisons every later run before any test exists
(_sd13_root / "build" / "test-results").mkdir(parents=True)
_sd13_gradle = _sd13_root / "build" / "test-results" / "attach-jvmRun1.dumpstream"
_sd13_gradle.write_text("Error while running fork\n")
_sd13_gradle_detected = test_gate._fork_boot_corruption(_sd13_root)
_sd13_gradle.unlink()
_sd13_tsinfo = _sd13_root / "tsconfig.tsbuildinfo"
_sd13_tsinfo.write_text("{\"program\": {\"half-wri")
_sd13_tsc_detected = test_gate._fork_boot_corruption(_sd13_root)
_sd13_healed = test_gate.heal_interrupted_build(_sd13_root)
_sd13_after_heal = test_gate._fork_boot_corruption(_sd13_root)
# heal_interrupted_build already removed target/ and build/ wholesale - exactly
# what a killed build leaves the next build to inhale; only the fixture root survives
import shutil as _sd13_sh
_sd13_sh.rmtree(_sd13_root, ignore_errors=True)
check("SD13 the engine recognizes a FORK BOOT death on corrupted build output as a tooling "
      "wound, not a verdict (2026-11-18 live: an operator SIGTERM during an mvn build left a "
      "truncated .class; every forked JVM then died before running a single test - status=error, "
      "tests=0 - and the wave/memo/ledger machinery laundered that empty verdict into a tree-wide "
      "fact, charging units and closing 'informed' replays on a failure nobody's code caused): "
      "the detector reads the surefire dumpstreams and distinguishes wound from clean; "
      "the SAME wound via Gradle's build/test-results dumps or a truncated TypeScript "
      "incremental cache is recognized too, and heal_interrupted_build deletes every "
      "regenerable output that exists (2026-11-25 review fix - the recovery was "
      "Maven-only, a SIGTERM inside a gradle/tsc build became a phantom board-wide "
      "defect)",
      _sd13_detected and not _sd13_clean
      and _sd13_gradle_detected and _sd13_tsc_detected
      and "tsconfig.tsbuildinfo" in _sd13_healed and not _sd13_after_heal)
_gate_src_sd13 = inspect.getsource(test_gate.green_test_result)
_wave_src_sd13 = inspect.getsource(test_gate.wave_gate_verdict)
_term_src_sd13 = inspect.getsource(tdd_engine.terminal_suite_gate)
check("SD13b the corruption repair path exists at every door: the scoped gate wipes target and "
      "re-runs BEFORE memo/wave publish; the wave door drops the cached verdict and falls to "
      "the scoped heal; the terminal gate wipes and rebuilds once",
      "_fork_boot_corruption" in _gate_src_sd13 and "wiping target" in _gate_src_sd13
      and _gate_src_sd13.index("_fork_boot_corruption")
      < _gate_src_sd13.index('if result.get("status") == "passed":')
      and "_fork_boot_corruption" in _wave_src_sd13
      # (2026-11-25 review fix) the wipe moved from a Maven-literal rmtree(root/"target")
      # at every door to ONE heal boundary knowing every regenerable output directory
      and "heal_interrupted_build" in _term_src_sd13
      and "_fork_boot_corruption" in _term_src_sd13)
_sd14_err = settings.ERROR_DIR / "T2-791-multipoison.json"
_sd14_err.write_text(json.dumps({"id": "T2-791", "error": "test gate: ... [WOVEN-CLEAN: payload "
                                 "compiles and the suite completes with it in the tree]"}))
_sd14_behavioral = tdd_engine._source_is_proven_poison("T2-791")
_sd14_err.write_text(json.dumps({"id": "T2-791", "error": "dependsOn T2-790 not resolvable"}))
_sd14_cascade = tdd_engine._source_is_proven_poison("T2-791")
_sd14_err.write_text(json.dumps({"id": "T2-791", "error": "test gate: status=compile_error; ..."}))
_sd14_real_poison = tdd_engine._source_is_proven_poison("T2-791")
_sd14_err.unlink()
_quar_src = inspect.getsource(tdd_engine.quarantine_dependents)
check("SD14 a cascade-quarantined dependent keeps its woven payload unless the BLOCKER's own "
      "evidence proves tree-breaking poison (2026-11-18 live: T2-035 was re-quarantined with a "
      "WOVEN-CLEAN behavioral failure, the cascade logic still reverted T2-037's SliceTestSupport, "
      "and the vanished class broke EVERY sibling's WOVEN-CLEAN probe - each revert re-poisoned "
      "the compile, a rollback chain through mutual destruction; reverting a victim of a "
      "scheduling stall is how one quarantine becomes forty blocked units)",
      not _sd14_behavioral and not _sd14_cascade and _sd14_real_poison
      and "_source_is_proven_poison(source)" in _quar_src
      and "woven payload kept through the cascade" in _quar_src
      and 'startswith("dependsOn")' in inspect.getsource(tdd_engine.drain_queue))
_te_export = "com.x.TelemetryEvent"
check("SD9 the demand-owner grammar covers every javac spelling of the surface (nested "
      "OUTER.Inner, package-qualified, simple) - the exact owner!=export comparison charged "
      "nobody for a constant demanded on TelemetryEvent.Type and 75 units deferred on each "
      "other in a two-node deferral cycle (caller defers: symbol miss = cascade; callee "
      "defers: all blamed files foreign), while a package never on the classpath is still "
      "nobody's type",
      tdd_engine._owner_matches_export("TelemetryEvent.Type", _te_export)
      and tdd_engine._owner_matches_export("com.x.TelemetryEvent.Type", _te_export)
      and tdd_engine._owner_matches_export("com.x.TelemetryEvent", _te_export)
      and tdd_engine._owner_matches_export("TelemetryEvent", _te_export)
      and not tdd_engine._owner_matches_export("OtherEvent.Type", _te_export)
      and not tdd_engine._owner_matches_export("com.other.Helper", _te_export))
_sd9_peer = {"id": "T2-777", "targetAgent": "agent-coder", "stage": 2, "dependsOn": [],
             "path": "src/main/java/x/Caller.java", "kind": "code", "layer": "domain",
             "feature": None, "export": "com.x.Caller", "intent": "calls the enum constant",
             "project": "mult9"}
_sd9_self = {"id": "T2-778", "targetAgent": "agent-coder", "stage": 2, "dependsOn": [],
             "path": "src/main/java/x/Color.java", "kind": "code", "layer": "domain",
             "feature": None, "export": "com.x.Color", "intent": "the enum itself",
             "project": "mult9"}
(settings.QUEUE_DIR / "T2-777-mult9.json").write_text(json.dumps(_sd9_peer))
_sd9_result = {"verdict_version": 2, "status": "compile_error", "exit_code": 1,
               "missing_symbols": ["LATE"],
               "member_demands": [{"owner": "com.x.Color", "kind": "variable", "member": "LATE"}],
               "problem_kinds": [], "bean_demands": [],
               "blamed_files": ["Caller.java"],
               "excerpt": ["[ERROR] /x/Caller.java:[7,99] cannot find symbol"]}
_sd9_method = json.loads(json.dumps(_sd9_result))
_sd9_method["member_demands"][0]["kind"] = "method"
_sd9_blocked_const = tdd_engine._blocked_by_peers(_sd9_result, _sd9_self)
_sd9_blocked_method = tdd_engine._blocked_by_peers(_sd9_method, _sd9_self)
(settings.QUEUE_DIR / "T2-777-mult9.json").unlink()
check("SD9 a javac-proven MEMBER (variable/property) demanded on this unit's own exported "
      "type is charged to the type's owner even when every blamed file is a peer's call site "
      "(the constant cannot be repaired at the caller - deferring the owner while the caller "
      "also defers is the cycle that blocked all 75 units live 2026-11-18), while a METHOD "
      "demand keeps the seed-002 rule (its spelling is proven only by the callers' own-file "
      "attempts, so the callee still waits)",
      _sd9_blocked_const is False and _sd9_blocked_method is True)

# --- SF. rule (z): shared literals are tabled, not prose (2026-11-19, the R1/R2 roots).
#     R1 froze the metrics facade's delivered spelling against the consumer test's planned
#     spelling - both artifacts were frozen law, the coder between them died 3/3. R2 froze a
#     controller test posting a route no contract served. The two `ast_hints` fields plus this
#     gate are the repair; every case below is the live shape, kept stack-neutral.
VOC_SLUG = "voc"
(settings.COMPLETE_DIR / f"execution-strategy-{VOC_SLUG}.json").write_text(json.dumps({
    "slug": VOC_SLUG, "language": "Java 21", "modules": [VOC_SLUG],
    "layers": ["domain", "application"], "build_order": ["domain"],
    "bounded_contexts": ["Voc"],
    "surfaces": [{"name": "voc ingest", "kind": "http", "context": "Voc",
                  "operations": ["POST"], "method": "POST", "path": "/x"}],
    "contexts_without_inbound": [],
    "persistence": {"data_model": "voc_row (id, value)"},
    "observability": {"correlation_key": "cid", "step_logs": ["voc accepted"],
                      "audit_trail": {"port": "Audit.record(A)"},
                      "metrics": [{"name": "voc.accepted", "type": "counter", "tags": []}],
                      "export": {"logs": "structured file sink"}}}))


def voc_reset():
    for folder in (settings.QUEUE_DIR, settings.ERROR_DIR, settings.COMPLETE_DIR):
        for stale in folder.glob(f"T[0-4]-6[45][0-9]-{VOC_SLUG}.json"):
            stale.unlink()


VOC_SCAFFOLD = gtask("T0-640", "Scaffold", 0, project=VOC_SLUG, path="pom.xml",
                     intent="Generate the voc project root")
VOC_SCAFFOLD["layer"] = "root"
VOC_SCAFFOLD["export"] = task_queue.SCAFFOLD_EXPORT
VOC_FACADE_OK = {"package": "com.voc.obs", "implements": [], "dependencies": [],
                 "methods": [{"signature": "accepted()", "returns": "void"}],
                 "meters": [{"name": "voc.accepted", "duty": "owns"}]}
VOC_CONS_OK = {"package": "com.voc.app", "implements": [],
               "dependencies": [{"type": "Facade", "task_id": "T2-641"}],
               "methods": [{"signature": "run()", "returns": "void"}],
               "meters": [{"name": "voc.accepted", "duty": "uses"}],
               "routes": [{"method": "POST", "path": "/voc/ingest", "duty": "serves"}]}


def voc_pair(num, facade_hints, cons_hints, cons_intent=None, cons_sem=None):
    cons_intent = cons_intent or ("answers POST /voc/ingest, counting each accepted sample")
    facade_t = gtask(f"T1-{num}", "FacadeTest", 1, deps=("T0-640",), project=VOC_SLUG,
                     path=f"src/test/java/voc/Facade{num}Test.java", hints=facade_hints)
    facade = gtask(f"T2-{num}", "Facade", 2, deps=(f"T1-{num}",), project=VOC_SLUG,
                   hints=facade_hints)
    cons_t = gtask(f"T1-{num + 1}", "UseCaseTest", 1, deps=("T0-640",), project=VOC_SLUG,
                   path=f"src/test/java/voc/UseCase{num + 1}Test.java",
                   intent=cons_intent, hints=cons_hints)
    cons = gtask(f"T2-{num + 1}", "UseCase", 2, deps=(f"T1-{num + 1}", f"T2-{num}"),
                 project=VOC_SLUG, intent=cons_intent, hints=cons_hints)
    cons["observability"] = {"step_logs": ["voc accepted"]}
    return [VOC_SCAFFOLD, facade_t, facade, cons_t, cons]


# R1 exact shape: the facade registers one spelling, the plan/floor/consumer use another.
facade_drift = json.loads(json.dumps(VOC_FACADE_OK))
facade_drift["meters"] = [{"name": "voc.validation.failed", "duty": "owns"}]
cons_floor = json.loads(json.dumps(VOC_CONS_OK))
cons_floor["meters"] = [{"name": "voc.samples.validation_failed", "duty": "uses"}]
voc_reset()
rc_sf = emit(voc_pair(641, facade_drift, cons_floor))
check("SF1 the R1 pair is REFUSED at emit: a meter 'uses' no unit owns, naming the closest "
      "tabled spelling and the off-plan owned name (2026-11-18 live: both spellings became "
      "frozen law and the coder between them died 3/3)",
      bool(rc_sf) and "voc.samples.validation_failed" in str(rc_sf)
      and "OWNED by none" in str(rc_sf) and "closest tabled spelling" in str(rc_sf)
      and "voc.validation.failed" in str(rc_sf) and "never planned it" in str(rc_sf),
      str(rc_sf)[:300])
voc_reset()
rc_sf = emit(voc_pair(641, VOC_FACADE_OK, VOC_CONS_OK))
check("SF2 the same plan with ONE verbatim spelling (facade owns, consumer uses, twins "
      "mirror, floor claimed) is ACCEPTED - the law refuses the drift, not the vocabulary",
      rc_sf is None, str(rc_sf)[:300])

facade2 = json.loads(json.dumps(VOC_FACADE_OK))
own_two = voc_pair(651, VOC_FACADE_OK, VOC_CONS_OK)
for record in own_two:
    if record["id"] == "T2-652":
        other = json.loads(json.dumps(VOC_FACADE_OK))
        record["ast_hints"] = other
        record["path"] = "src/main/java/voc/Second.java"
        record["export"] = "Second"
voc_reset()
rc_sf = emit(own_two)
check("SF3 a meter OWNED by two units is REFUSED - rule (l)'s one owner is now machine-checkable "
      "(the double registration the plan could hide in prose)",
      bool(rc_sf) and "OWNED by units" in str(rc_sf), str(rc_sf)[:220])

(settings.COMPLETE_DIR / f"execution-strategy-{VOC_SLUG}.json").write_text(json.dumps({
    "slug": VOC_SLUG, "observability": {
        "correlation_key": "cid", "step_logs": ["voc accepted"],
        "audit_trail": {"port": "Audit.record(A)"},
        "metrics": [{"name": "voc.accepted", "type": "counter", "tags": []},
                    {"name": "voc.rejected", "type": "counter", "tags": []}],
        "export": {"logs": "structured file sink"}}}))
voc_reset()
rc_sf = emit(voc_pair(641, VOC_FACADE_OK, VOC_CONS_OK))
check("SF4 a floor meter NO unit owns is REFUSED once the whole domain carries the fields - "
      "completeness, the half rule (u)'s fuzzy pairing could not see verbatim",
      bool(rc_sf) and "voc.rejected" in str(rc_sf) and "tables it" in str(rc_sf),
      str(rc_sf)[:260])

# R2 exact shape: the test posts a route no table serves, while the unit's prose spells it.
cons_r2 = json.loads(json.dumps(VOC_CONS_OK))
r2_batch = voc_pair(641, VOC_FACADE_OK, cons_r2)
for record in r2_batch:
    if record["id"] == "T1-642":
        record["intent"] = "posts /voc/packets and expects 202"
(settings.COMPLETE_DIR / f"execution-strategy-{VOC_SLUG}.json").write_text(json.dumps({
    "slug": VOC_SLUG, "observability": {
        "correlation_key": "cid", "step_logs": ["voc accepted"],
        "audit_trail": {"port": "Audit.record(A)"},
        "metrics": [{"name": "voc.accepted", "type": "counter", "tags": []}],
        "export": {"logs": "structured file sink"}}}))
voc_reset()
rc_sf = emit(r2_batch)
check("SF5 the R2 pair is REFUSED: a staged unit spells a route ('/voc/packets') its own table "
      "does not carry - the frozen test of 2026-11-18 posted a URI no contract served and the "
      "deny-by-default chain answered 500 for every one of its six cases",
      bool(rc_sf) and "/voc/packets" in str(rc_sf) and "ast_hints.routes does not carry it"
      in str(rc_sf), str(rc_sf)[:260])

guard_hints = {"package": "com.voc.guard", "implements": [], "dependencies": [],
               "methods": [{"signature": "admits(String cid)", "returns": "boolean",
                            "semantics": "true admits the caller, false denies it"}],
               "routes": [{"method": "POST", "path": "/voc/ingest", "duty": "uses"}]}
guard_batch = voc_pair(641, VOC_FACADE_OK, VOC_CONS_OK) + [
    gtask("T1-643", "GuardTest", 1, deps=("T0-640",), project=VOC_SLUG,
          path="src/test/java/voc/Guard1203Test.java",
          intent="the guard admits POST /voc/ingest callers, denies the rest",
          hints=guard_hints),
    gtask("T2-643", "Guard", 2, deps=("T1-643",), project=VOC_SLUG,
          intent="the guard admits POST /voc/ingest callers, denies the rest",
          hints=guard_hints)]
voc_reset()
rc_sf = emit(guard_batch)
check("SF6 a guard citing the served (method, path) VERBATIM with duty 'uses' ACCEPTS - the "
      "citation is the join, not a second claim of the route", rc_sf is None, str(rc_sf)[:260])
unserved = json.loads(json.dumps(guard_hints))
unserved["routes"] = [{"method": "POST", "path": "/voc/gone", "duty": "uses"}]
for record in unserved if isinstance(unserved, list) else []:
    pass
guard_batch2 = voc_pair(645, VOC_FACADE_OK, VOC_CONS_OK)
guard_batch2[-2]["ast_hints"] = unserved
guard_batch2[-1]["ast_hints"] = unserved
guard_batch2[-2]["intent"] = "the guard admits POST /voc/gone callers, denies the rest"
guard_batch2[-1]["intent"] = "the guard admits POST /voc/gone callers, denies the rest"
voc_reset()
rc_sf = emit(guard_batch2)
check("SF6b a cited route SERVED by no unit is REFUSED naming the route (the (y2) reach "
      "doctrine, generalized to every request-path literal)",
      bool(rc_sf) and "/voc/gone" in str(rc_sf) and "SERVED by none" in str(rc_sf),
      str(rc_sf)[:260])

double = json.loads(json.dumps(VOC_CONS_OK))
pair = voc_pair(651, VOC_FACADE_OK, VOC_CONS_OK)
second = gtask("T2-653", "SecondIn", 2, deps=("T2-1221", "T2-652"), project=VOC_SLUG,
               intent="answers POST /voc/ingest with summary counts", hints=double)
second_t = gtask("T1-653", "SecondInTest", 1, deps=("T0-640",), project=VOC_SLUG,
                 path="src/test/java/voc/Second1231Test.java",
                 intent="answers POST /voc/ingest with summary counts", hints=double)
voc_reset()
rc_sf = emit(pair + [second_t, second])
check("SF7 a route `serves`ed by TWO units is REFUSED - two handlers, one path, is the same "
      "double-ownership class SF3 refuses for meters",
      bool(rc_sf) and "/voc/ingest" in str(rc_sf) and "serves`ed by units" in str(rc_sf),
      str(rc_sf)[:260])

twin_bad = voc_pair(641, VOC_FACADE_OK, VOC_CONS_OK)
for record in twin_bad:
    if record["id"] == "T1-642":
        record["ast_hints"] = json.loads(json.dumps(VOC_CONS_OK))
        record["ast_hints"]["routes"] = [{"method": "POST", "path": "/voc/ingest",
                                          "duty": "uses"}]
voc_reset()
rc_sf = emit(twin_bad)
_sf8_twin = json.loads((settings.QUEUE_DIR / "T1-642-voc.json").read_text())
check("SF8 the test/code twins of one unit carrying DIFFERENT tables is HEALED, not "
      "refused (2026-11-25 wire tier): the CODE side owns the interface and the engine "
      "mirrors its table onto the test twin before the joins read it - the carriers "
      "promised 'z4 by construction' since the compact form shipped, a BOARD-object "
      "draft kept two typed copies, and the v5 run paid a full repair round for a drift "
      "it manufactured itself; the emitted T1 now carries the code-side table byte-"
      "identical, the pair freeze class cannot recur at any tier (seed-002 regen)",
      rc_sf is None and _sf8_twin["ast_hints"] == twin_bad[4]["ast_hints"],
      str(rc_sf)[:220])

board_twin = voc_pair(641, VOC_FACADE_OK, VOC_CONS_OK)
for record in board_twin:
    if record["stage"] == 1 or str(record.get("id")) == "T0-640":
        continue
late = voc_pair(641, VOC_FACADE_OK, VOC_CONS_OK)
late = [r for r in late if str(r.get("id")) != "T1-642"]
for record in late:
    if record["id"] == "T2-642":
        record["ast_hints"] = json.loads(json.dumps(VOC_CONS_OK))
        record["ast_hints"]["meters"] = [{"name": "voc.accepted", "duty": "owns"}]
voc_reset()
(settings.COMPLETE_DIR / "T1-642-voc.json").write_text(json.dumps(
    gtask("T1-642", "UseCaseTest", 1, deps=("T0-640",), project=VOC_SLUG,
          path="src/test/java/voc/UseCase642Test.java",
          intent="asserts the recorded facts", hints=VOC_CONS_OK)))
rc_sf = emit(late)
check("SF9 a staged task contradicting the table its twin ALREADY carries on the board is "
      "REFUSED naming the delivered twin and --replan (a regen may add the vocabulary keys, "
      "never re-spell the shared ones)",
      bool(rc_sf) and "T1-642" in str(rc_sf) and "--replan" in str(rc_sf), str(rc_sf)[:260])
(settings.COMPLETE_DIR / "T1-642-voc.json").unlink()

prose_safe = json.loads(json.dumps(VOC_CONS_OK))
safe_batch = voc_pair(641, VOC_FACADE_OK, prose_safe,
                      cons_intent=("answers POST /voc/ingest; consumes application/json and "
                                   "produces text/event-stream; reads ${DB_URL} from the "
                                   "environment"))
voc_reset()
rc_sf = emit(safe_batch)
check("SF10 the route scan does NOT fire on media types, env placeholders or relative paths "
      "(over-refusing a lawful plan is the same defect wearing the other uniform)",
      rc_sf is None, str(rc_sf)[:260])

bad_duty = json.loads(json.dumps(VOC_CONS_OK))
bad_duty["meters"] = [{"name": "voc.accepted", "duty": "records"}]
voc_reset()
rc_sf = emit(voc_pair(641, VOC_FACADE_OK, bad_duty))
check("SF11 an off-schema vocabulary duty is refused at SHAPE time ('records' is not a duty: "
      "the enums are the closed set)",
      bool(rc_sf) and "duty in ['owns', 'uses']" in str(rc_sf), str(rc_sf)[:200])

prose_meter = voc_pair(641, VOC_FACADE_OK, VOC_CONS_OK)
for record in prose_meter:
    if record["id"] in ("T1-641", "T2-641"):
        record["ast_hints"] = json.loads(json.dumps(VOC_FACADE_OK))
        record["ast_hints"]["meters"] = []
voc_reset()
rc_sf = emit(prose_meter)
check("SF12 a unit whose COLLABORATOR table was emptied while consumers still cite the meter "
      "is caught by the ownership half, not by silence: 'uses' with an empty owner list is "
      "'OWNED by none' (the D15 regen could launder a name only while prose was the join)",
      bool(rc_sf) and "OWNED by none" in str(rc_sf), str(rc_sf)[:260])
# SF19/SF20: THE WRITABLE CHANNEL (2026-11-19 operator review - the prompt-contract trap:
#     a stage-2 unit whose path is a template file has no writer on this board - the weaver
#     splices source, the text route serves configuration documents, and no agent authors
#     .st/.txt; the plan must move the artifact into a type or a config document).
WCH = "wch"
def wch_units(path):
    s = gtask("T0-655", "Scaffold", 0, project=WCH, path="pom.xml", intent="Generate the wch root")
    s["layer"] = "root"
    s["export"] = task_queue.SCAFFOLD_EXPORT
    h = {"package": "com.wch.p", "implements": [], "dependencies": [],
         "methods": [{"signature": "system()", "returns": "String"}]}
    t1 = gtask("T1-656", "PromptContractTest", 1, deps=("T0-655",), project=WCH,
               path="src/test/java/wch/PromptContractTest.java", hints=h,
               intent="asserts the five contract members")
    t2 = gtask("T2-656", "PromptContract", 2, deps=("T1-656",), project=WCH, hints=h,
               path=path, intent="the versioned prompt contract: role, placeholders, "
                                  "output-schema ref, refusal text")
    t2["layer"] = "application"
    return [s, t1, t2]

for _f in list(settings.QUEUE_DIR.glob("T?-65*-wch.json")) + list(settings.ERROR_DIR.glob("T?-65*-wch.json")):
    _f.unlink()
rc_sf = emit(wch_units("src/main/resources/prompts/system.st"))
check("SF19 a stage-2 unit planned onto a template file is REFUSED at emit - no writer on "
      "this board authors .st/.txt/.md, so the duty would deadlock at its first red gate "
      "(the D4 class: a duty with no lawful channel)",
      bool(rc_sf) and "system.st" in str(rc_sf)
      and "no agent of this board authors template or text files" in str(rc_sf),
      str(rc_sf)[:220])
for _f in list(settings.QUEUE_DIR.glob("T?-65*-wch.json")) + list(settings.ERROR_DIR.glob("T?-65*-wch.json")):
    _f.unlink()
rc_sf = emit(wch_units("src/main/java/com/wch/p/PromptContract.java"))
check("SF20 the SAME unit ACCEPTS as a source type (the Java-home remedy named by the "
      "refusal) - the contract becomes tabled members the tester asserts and the weaver "
      "lands", rc_sf is None, str(rc_sf)[:220])
for _f in list(settings.QUEUE_DIR.glob("T?-65*-wch.json")):
    _f.unlink()

voc_reset()

# --- z5: property paths are shared literals (R4), and z6: a guard's products are
#     visible to the surface it guards (R3). Both joins ride _shared_literal_errors.
CFG_SLUG = "cfg"


def cfg_scaffold():
    s = gtask("T0-631", "Scaffold", 0, project=CFG_SLUG, path="pom.xml",
              intent="Generate the cfg project root")
    s["layer"] = "root"
    s["export"] = task_queue.SCAFFOLD_EXPORT
    return s


def cfg_reset():
    for folder in (settings.QUEUE_DIR, settings.ERROR_DIR, settings.COMPLETE_DIR):
        for stale in folder.glob(f"T[0-9]-63[0-9]-{CFG_SLUG}.json"):
            stale.unlink()


CFG_BIND = {"package": "com.cfg.creds", "implements": [], "dependencies": [],
            "methods": [],
            "config": [{"path": "demo.creds", "kind": "list",
                        "fields": ["id", "secret-hash", "scope"]}]}
CFG_WRITE_BAD = {"package": "com.cfg", "implements": [], "dependencies": [], "methods": [],
                 "config": [{"path": "demo.creds.secret-hash", "kind": "value"}]}
CFG_WRITE_OK = {"package": "com.cfg", "implements": [], "dependencies": [], "methods": [],
                "config": [{"path": "demo.creds", "kind": "list",
                            "fields": ["id", "secretHash", "scope"]}]}


def cfg_units(num, write_hints):
    """binder family `num` + config-writer family `num+1` (twins share tables)."""
    bind_t = gtask(f"T1-{num}", "Creds", 1, deps=("T0-631",), project=CFG_SLUG,
                   path=f"src/test/java/cfg/Creds{num}Test.java", hints=CFG_BIND,
                   intent="the credential list binds demo.creds entries (id, secret-hash, scope)")
    bind = gtask(f"T2-{num}", "Creds", 2, deps=(f"T1-{num}",), project=CFG_SLUG,
                 hints=CFG_BIND,
                 intent="the credential list binds demo.creds entries (id, secret-hash, scope)")
    bind["layer"] = "application"
    bind_t["layer"] = "application"
    w_t = gtask(f"T1-{num + 1}", "AppYml", 1, deps=("T0-631",), project=CFG_SLUG,
                path=f"src/test/java/cfg/AppYml{num + 1}Test.java", hints=write_hints,
                intent="the loader binds the seeded credential entries")
    w = gtask(f"T2-{num + 1}", "AppYml", 2, deps=(f"T1-{num + 1}",), project=CFG_SLUG,
              path="src/main/resources/application.yml", hints=write_hints,
              intent="runtime config application.yml seeds the credential entries "
                     "for every profile the plan names")
    w["layer"] = "shared"
    w_t["layer"] = "shared"
    w["export"] = "application.yml"
    return [cfg_scaffold(), bind_t, bind, w_t, w]


cfg_reset()
rc_sf = emit(cfg_units(632, CFG_WRITE_BAD))
check("SF13 the R4 pair is REFUSED: the record tables `demo.creds` as a LIST while the config "
      "contract seeds a dotted child `demo.creds.secret-hash` - no binder reads a scalar child "
      "of a list and no writer can satisfy both (2026-11-19 live: devices list vs "
      "devices.secret-hash, the credential store booted empty forever)",
      bool(rc_sf) and "demo.creds.secret-hash" in str(rc_sf) and "tabled as a LIST" in str(rc_sf),
      str(rc_sf)[:260])
cfg_reset()
rc_sf = emit(cfg_units(632, CFG_WRITE_OK))
check("SF14 the citation pair ACCEPTS across relaxed-binding spellings (the writer's camel "
      "field `secretHash` IS the binder's kebab `secret-hash` - the canonical form is the "
      "runtime's own), one path, one kind, one field set",
      rc_sf is None, str(rc_sf)[:260])
cfg_reset()
rc_sf = emit(cfg_units(632, {"package": "com.cfg", "implements": [], "dependencies": [],
                             "methods": []}))
_sf15_written = json.loads((settings.QUEUE_DIR / "T2-633-cfg.json").read_text())
check("SF15 coverage is a WIRE, not a refusal and not a typing job (2026-11-25 PHASE "
      "1.5): a configuration-artifact unit that carries no table while the board tables "
      "paths receives EVERY binder entry VERBATIM at the batch - kind and element fields "
      "included - so the shape stays owned by the record that binds it and the document "
      "unit still answers for the full surface (the old empty-table refusal taught "
      "sessions to copy; the wire makes the copy deterministic and frees the lint to "
      "judge completeness)",
      rc_sf is None
      and [str(e.get("path")) for e in _sf15_written["ast_hints"]["config"]] == ["demo.creds"]
      and _sf15_written["ast_hints"]["config"][0].get("kind") == "list", str(rc_sf)[:260])


CHN_SLUG = "chn"


def chn_batch(entry_extra_deps, guard_methods, guard_deps):
    s = gtask("T0-678", "Scaffold", 0, project=CHN_SLUG, path="pom.xml",
              intent="Generate the chn project root")
    s["layer"] = "root"
    s["export"] = task_queue.SCAFFOLD_EXPORT
    mgr_h = {"package": "com.chn.auth", "implements": [], "dependencies": [],
             "methods": [{"signature": "authenticate(String id, String secret)",
                          "returns": "Mono<String>"}]}
    guard_h = {"package": "com.chn.sec", "implements": [], "dependencies": guard_deps,
               "methods": guard_methods,
               "routes": [{"method": "POST", "path": "/chn/ing", "duty": "uses"}]}
    entry_deps = ["T1-677"] + [str(d["task_id"]) for d in entry_extra_deps]
    entry_h = {"package": "com.chn.app", "implements": [], "dependencies": entry_extra_deps,
               "methods": [{"signature": "run()", "returns": "void"}],
               "routes": [{"method": "POST", "path": "/chn/ing", "duty": "serves"}]}
    units = [s,
             gtask("T1-675", "ManagerBeanTest", 1, deps=("T0-678",), project=CHN_SLUG,
                   path="src/test/java/chn/ManagerBeanTest.java", hints=mgr_h,
                   intent="asserts the credential check answers both branches"),
             gtask("T2-675", "ManagerBean", 2, deps=("T1-675",), project=CHN_SLUG,
                   hints=mgr_h, intent="authenticates per-device credentials, admits or denies"),
             gtask("T1-676", "GuardCfgTest", 1, deps=("T0-678",), project=CHN_SLUG,
                   path="src/test/java/chn/GuardCfgTest.java", hints=guard_h,
                   intent="the chain admits POST /chn/ing scoped callers and denies the rest"),
             gtask("T2-676", "GuardCfg", 2, deps=("T1-676", "T2-675"), project=CHN_SLUG,
                   hints=guard_h,
                   intent="the chain configuration builds the guard for POST /chn/ing"),
             gtask("T1-677", "IngressTest", 1, deps=("T0-678",), project=CHN_SLUG,
                   path="src/test/java/chn/IngressTest.java", hints=entry_h,
                   intent="the ingress adapter answers POST /chn/ing"),
             ]
    entry = gtask("T2-677", "Ingress", 2, deps=tuple(entry_deps), project=CHN_SLUG,
                  hints=entry_h, intent="the ingress adapter answers POST /chn/ing")
    return units + [entry]


CHAIN_METHODS = [{"signature": "chain(Httpish http, ManagerBean manager)",
                  "returns": "ChainHandle"}]
CHAIN_DEPS = [{"type": "ManagerBean", "task_id": "T2-675"}]


def chn_reset():
    for folder in (settings.QUEUE_DIR, settings.ERROR_DIR, settings.COMPLETE_DIR):
        for stale in folder.glob(f"T[0-9]-67[5-9]-{CHN_SLUG}.json"):
            stale.unlink()


chn_reset()
rc_sf = emit(chn_batch([{"type": "GuardCfg", "task_id": "T2-676"}],
                       CHAIN_METHODS, CHAIN_DEPS))
_sf16 = json.loads((settings.QUEUE_DIR / f"T2-677-{CHN_SLUG}.json").read_text())
check("SF16 the R3 shape is CLOSED BY THE ENGINE at the batch (2026-11-25 bottleneck pass: "
      "z6's transitive pin closure is graph arithmetic - sessions drifted it and paid a "
      "repair family for it; the manifest wire SP10 proved the pattern): the surface that "
      "pins its guard but not the guard's own concrete product gets the missing "
      "{type, task_id} collaborator AND the dependsOn edge written into the EMITTED record "
      "- the batch no longer refuses what Python can complete, and _shared_literal_errors "
      "keeps the join as the assertion behind the wire (rule (z6) as wiring, not typing)",
      rc_sf is None
      and {"type": "ManagerBean", "task_id": "T2-675"}
          in _sf16["ast_hints"]["dependencies"]
      and "T2-675" in _sf16["dependsOn"]
      and {"type": "ManagerBean", "task_id": "T2-675"} in json.loads(
          (settings.QUEUE_DIR / f"T1-677-{CHN_SLUG}.json").read_text()
      )["ast_hints"]["dependencies"],
      str(rc_sf)[:300])
chn_reset()
rc_sf = emit(chn_batch([{"type": "GuardCfg", "task_id": "T2-676"},
                        {"type": "ManagerBean", "task_id": "T2-675"}],
                       CHAIN_METHODS, CHAIN_DEPS))
check("SF17 the same plan ACCEPTS once the surface also pins the guard's product - the pin is "
      "the contract that lets the tester double what the container must build (the live "
      "T2-025 pattern, generalized)", rc_sf is None, str(rc_sf)[:300])
chn_reset()
rc_sf = emit(chn_batch([{"type": "GuardCfg", "task_id": "T2-676"}],
                       [{"signature": "chain(Httpish http)", "returns": "ChainHandle"}], []))
check("SF18 the law does not fire on framework-only parameters: no PROJECT product is named, "
      "nothing more to pin - over-refusing a lawful plan is the same defect wearing the "
      "other uniform", rc_sf is None, str(rc_sf)[:300])
chn_reset()


# --- PG. the performance and AI phases (2026-11-19): two more stack-agnostic spec gates
#     cloned from the security contract - verbatim keying to phase 1, closed measurement
#     kinds (the R5 lesson: deterministic or unclaimed), duty closure, leak refusal - and
#     the AI directive, the mirror of the security waiver with flipped polarity.
PFS = "pfs"
settings.DOMAIN_DIR.mkdir(parents=True, exist_ok=True)
settings.CONTEXT_MAP_DIR.mkdir(parents=True, exist_ok=True)
(settings.COMPLETE_DIR / f"execution-strategy-{PFS}.json").write_text(json.dumps({
    "slug": PFS, "language": "Java 21", "modules": [PFS],
    "bounded_contexts": ["Intake"],
    "surfaces": [{"name": "intake write", "kind": "http", "context": "Intake",
                  "operations": ["POST"], "method": "POST", "path": "/x"}],
    "contexts_without_inbound": [],
    "persistence": {"data_model": "telemetry_record (device_key, value)"},
    "observability": FULL_FLOOR, "risks": []}))


def perf_spec(**over):
    spec = {
        "schema_version": "1.0", "report_type": "performance-spec", "slug": PFS,
        "metadata": {"generated_at": "2026-11-19T00:00:00-03:00",
                     "agent": "agent-performance-architect", "inputs": ["execution-strategy"],
                     "confidence": "high"},
        "assumptions": [{"id": "PA-01", "text": "bursty device traffic, tenfold peaks",
                         "source": "intake write"}],
        "workload": {"entries": [{"id": "WB-01", "surface": "intake write",
                                  "driver": "peak arrival, bounded payload",
                                  "data": ["telemetry_record"]}],
                     "surfaces_exempt": []},
        "budgets": [{"id": "PB-01", "target": "in-flight packets per instance",
                     "limit": "a finite admission bound with a declared rejection",
                     "capability": "rate-limit",
                     "measurement": {"kind": "status-code",
                                     "assertion": "saturation answers the declared status"}}],
        "invariants": [{"id": "PI-01", "rule": "no unbounded queue or buffer on any path",
                        "capability": "drop-policy"}],
        "duties": [
            {"spec_ref": "PB-01", "obligation": "admit up to the bound, refuse above",
             "capability": "rate-limit", "unit_kind": "admission-control"},
            {"spec_ref": "PI-01", "obligation": "every queue ships with its bound and policy",
             "capability": "drop-policy", "unit_kind": "resource-ceiling"}],
        "risks": [], "open_questions": []}
    spec.update(over)
    (settings.COMPLETE_DIR / f"performance-spec-{PFS}.json").write_text(json.dumps(spec))
    return spec


perf_spec()
check("PG1 a lawful performance spec passes the gate (workload keyed VERBATIM to the surface "
      "table, deterministic measurements, duties closed)",
      ddd.validate_performance_spec(PFS) is None, str(ddd.validate_performance_spec(PFS))[:220])
bad = perf_spec(); bad["budgets"][0]["measurement"]["kind"] = "latency-p99"
(settings.COMPLETE_DIR / f"performance-spec-{PFS}.json").write_text(json.dumps(bad))
check("PG2 a wall-clock measurement is REFUSED naming the closed kind set - the R5 class "
      "prevented at the spec, not discovered at the gate ('p99 under 200ms' flakes in CI)",
      "latency-p99" in str(ddd.validate_performance_spec(PFS))
      and "clock" in str(ddd.validate_performance_spec(PFS)).lower(),
      str(ddd.validate_performance_spec(PFS))[:240])
bad = perf_spec(); bad["workload"]["entries"][0]["surface"] = "the big intake endpoint"
bad["workload"]["surfaces_exempt"] = [{"surface": "ghost read"}]
(settings.COMPLETE_DIR / f"performance-spec-{PFS}.json").write_text(json.dumps(bad))
reason_pg = str(ddd.validate_performance_spec(PFS))
check("PG3 paraphrased surface names, an exemption for an undeclared surface, and the covered "
      "surface losing its row are ALL refused - the verbatim join-key law, security's, reused",
      "the big intake endpoint" in reason_pg and "ghost read" in reason_pg
      and "NO workload entry" in reason_pg, reason_pg[:280])
bad = perf_spec(); bad["duties"] = [d for d in bad["duties"] if d["spec_ref"] != "PI-01"]
(settings.COMPLETE_DIR / f"performance-spec-{PFS}.json").write_text(json.dumps(bad))
check("PG4 an invariant with no owning duty is REFUSED (duty closure is one contract, not a "
      "per-section option)", "PI-01" in str(ddd.validate_performance_spec(PFS)),
      str(ddd.validate_performance_spec(PFS))[:180])
bad = perf_spec(); bad["budgets"][0]["limit"] = "pool sized by hikaricp defaults"
(settings.COMPLETE_DIR / f"performance-spec-{PFS}.json").write_text(json.dumps(bad))
check("PG5 a vendor name in the artifact is REFUSED (the leak law is not security-only - a "
      "performance spec that names a product decided the architect's job)",
      "hikaricp" in str(ddd.validate_performance_spec(PFS)),
      str(ddd.validate_performance_spec(PFS))[:180])
bad = perf_spec(); bad["duties"][0]["capability"] = "in-flight-cap"
bad["budgets"][0]["capability"] = "in-flight-cap"
(settings.COMPLETE_DIR / f"performance-spec-{PFS}.json").write_text(json.dumps(bad))
check("PG5b a capability OUTSIDE the skill's closed token vocabulary is REFUSED (2026-11-24 v4 "
      "live: the skill named families but not sizes/streaming tokens, so the spec coined "
      "payload-limit-style terms, the architect table missed them, the digest carried "
      "table_row null, and the planner borrowed the CLOSEST row - nearest-row is how a duty "
      "acquires a mechanism it never asked for)",
      "in-flight-cap" in str(ddd.validate_performance_spec(PFS))
      and "outside the closed performance token set" in str(ddd.validate_performance_spec(PFS)),
      str(ddd.validate_performance_spec(PFS))[:220])
_check_tokens = ddd._performance_capability_tokens()
check("PG5c the closed set is PARSED LIVE from the performance-strategy skill (not a second "
      "list to drift): every token the spec fixture uses is in it, the four tokens the v4 "
      "report needed are there, and the family words are lowercase-kebab",
      {"rate-limit", "bounded-semaphore", "bounded-buffer", "page-size-limit", "payload-limit",
       "bounded-window", "subscriber-limit", "pool-limit", "timeout-budget",
       "read-through-cache", "negative-cache", "idempotent-retry", "bounded-attempts",
       "bounded-queue", "backpressure", "drop-policy", "batch-load"} <= _check_tokens
      and all(tok.islower() and " " not in tok for tok in _check_tokens),
      str(sorted(_check_tokens))[:220])
perf_spec()
_table_text = (Path(__file__).resolve().parents[1]  # carriers live in the REAL repo, not the
      # rebased engine sandbox - same reason _digest_table_rows resolves against the module root
     / ".opencode/skills/tech-stack-architect/spring-performance-architect/"
                "SKILL.md").read_text()
_missing = sorted(tok for tok in _check_tokens if tok not in _table_text)
check("PG5d the ACTIVE stack table keys every closed token in its first column - a skill token "
      "with no row is the gap that sent v4's planner to the closest row (digest gaps list "
      "would fire, but the refusal belongs to the spec, not the plan)",
      not _missing, f"rows missing for {_missing}")

AIS = "ais"
(settings.COMPLETE_DIR / f"execution-strategy-{AIS}.json").write_text(json.dumps({
    "slug": AIS, "language": "Java 21", "modules": [AIS],
    "bounded_contexts": ["Ask"],
    "surfaces": [{"name": "ask surface", "kind": "http", "context": "Ask",
                  "operations": ["POST"], "method": "POST", "path": "/x"}],
    "persistence": {"data_model": "answer_record (question)"},
    "observability": FULL_FLOOR, "risks": []}))
(settings.CONTEXT_MAP_DIR / f"context-map-{AIS}.json").write_text(json.dumps(
    {"slug": AIS, "cross_boundary_flows": [{"name": "question to model", "from": "Ask",
                                            "to": "Model"}]}))
DESC_PG = ROOT / "desc-ais.md"
DESC_PG.write_text("The service answers operator questions with generated text over its own "
                   "telemetry data. Everything else is ordinary ingestion.\n")
(settings.DOMAIN_DIR / f"domain-boundary-{AIS}.json").write_text(json.dumps({
    "schema_version": "1.0", "report_type": "domain-slice",
    "metadata": {"generated_at": "2026-11-19T00:00:00-03:00",
                 "agent": "domain-boundary-discovery-specialist",
                 "source_description": str(DESC_PG)},
    "subdomain": {"name": "ais", "type": "core", "capability": "ask", "why_distinct": "x"},
    "ubiquitous_language": [], "bounded_contexts": [], "assumptions": [],
    "ai_directive": {"required": True,
                     "quote": "The service answers operator questions with generated text over "
                              "its own telemetry data.",
                     "source": "description"}}))
check("PG7 the AI trigger is honored ONLY on a VERBATIM sentence of the description (the "
      "waiver's witness law, flipped polarity)",
      ddd.ai_required(AIS)[0] is True and "answers operator questions" in ddd.ai_required(AIS)[1]
      and ddd.validate_ai_directives() is None, str(ddd.ai_required(AIS))[:200])
slice_pg = json.loads((settings.DOMAIN_DIR / f"domain-boundary-{AIS}.json").read_text())
slice_pg["ai_directive"]["quote"] = "the users obviously wanted chatbots"
(settings.DOMAIN_DIR / f"domain-boundary-{AIS}.json").write_text(json.dumps(slice_pg))
check("PG7b a PARAPHRASE is no trigger - required:false-equivalent by force: the phase must "
      "not run on a sentence the user never wrote, and the reason is fatal, not silent",
      ddd.ai_required(AIS)[0] is False
      and ddd.validate_ai_directives() is not None, str(ddd.ai_required(AIS))[:160])
slice_pg["ai_directive"]["quote"] = ("The service answers operator questions with generated "
                                     "text over its own telemetry data.")
(settings.DOMAIN_DIR / f"domain-boundary-{AIS}.json").write_text(json.dumps(slice_pg))


def ai_spec(**over):
    spec = {
        "schema_version": "1.0", "report_type": "ai-spec", "slug": AIS,
        "metadata": {"generated_at": "2026-11-19T00:00:00-03:00",
                     "agent": "agent-ai-architect", "inputs": ["execution-strategy"],
                     "confidence": "high"},
        "assumptions": [{"id": "AA-01", "text": "answers cite only the caller-visible rows",
                         "source": "ask surface"}],
        "model_roles": [{"id": "AR-01", "role": "answer generation",
                         "statefulness": "session", "memory_technique": "sliding-window", "memory_technique": "sliding-window", "data_classes": ["answer_record"]}],
        "capabilities": [{"id": "AC-01", "surface_or_flow": "ask surface",
                          "requirement": "every prompt is the versioned contract, never an "
                                         "ad-hoc string",
                          "capability": "prompt-contract",
                          "measurement": {"kind": "stub-call-count",
                                          "assertion": "the stub port is called exactly once "
                                                       "per request"}},
                         {"id": "AC-02", "surface_or_flow": "question to model",
                          "requirement": "model output is schema-validated before trusted",
                          "capability": "structured-output-guard",
                          "measurement": {"kind": "schema-validation",
                                          "assertion": "a violating output answers the declared "
                                                       "refusal"}}],
        "invariants": [{"id": "AM-01",
                        "rule": "no test path reaches a live endpoint; every port answers "
                                "from its stub",
                        "capability": "offline-model-port"}],
        "duties": [
            {"spec_ref": "AC-01", "obligation": "own the versioned prompt contract",
             "capability": "prompt-contract", "unit_kind": "prompt-contract"},
            {"spec_ref": "AC-02", "obligation": "validate the output schema at the port",
             "capability": "structured-output-guard", "unit_kind": "output-validator"},
            {"spec_ref": "AM-01", "obligation": "ship the offline stand-in with the port",
             "capability": "offline-model-port", "unit_kind": "offline-stub"}],
        "risks": [], "open_questions": []}
    spec.update(over)
    (settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(spec))
    return spec


ai_spec()
check("PG8 a lawful AI spec passes: closed tokens, roles with statefulness AND data classes, "
      "flow-keyed capability (verbatim against the context map), deterministic measurements, "
      "the offline invariant present, duties closed",
      ddd.validate_ai_spec(AIS) is None, str(ddd.validate_ai_spec(AIS))[:240])
bad = ai_spec(); bad["invariants"] = []
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(bad))
check("PG8b an AI spec without the offline-port invariant is REFUSED: a plan that CAN call "
      "the world from CI will, billing real tokens - the mandatory law, not a suggestion",
      "offline-model-port" in str(ddd.validate_ai_spec(AIS)), str(ddd.validate_ai_spec(AIS))[:180])
bad = ai_spec(); bad["capabilities"][0]["capability"] = "hallucination-guard"
bad["duties"][0]["capability"] = "hallucination-guard"
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(bad))
reason_pg = str(ddd.validate_ai_spec(AIS))
check("PG8c a token OUTSIDE the closed AI vocabulary is REFUSED (the mapping table has no "
      "row for an invented capability - the honest channel is the skill's list or "
      "open_questions)", "hallucination-guard" in reason_pg
      and "CLOSED" in reason_pg.upper() or "closed" in reason_pg, reason_pg[:200])
bad = ai_spec(); bad["capabilities"][0]["surface_or_flow"] = "the chat thing"
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(bad))
check("PG8d a capability keyed to no declared surface and no context-map flow is REFUSED - "
      "floating AI behavior is invented behavior", "the chat thing" in
      str(ddd.validate_ai_spec(AIS)), str(ddd.validate_ai_spec(AIS))[:200])
ai_spec()

# PG14: the multi-agent trio (operator review 2026-11-19): topology, termination, human
# custody, role bindings - and the spec_ref restriction the schema's "SAME closed token"
# clause demanded (AR-/AA- rows carry no capability; a duty citing them was undefined law).
def ma_spec():
    spec = json.loads(json.dumps(ai_spec()))
    spec["model_roles"][0]["statefulness"] = "durable"
    spec["model_roles"] += [
        {"id": "AR-02", "role": "worker generation", "statefulness": "none",
         "data_classes": ["answer_record"]}]
    spec["capabilities"] += [
        {"id": "AC-03", "surface_or_flow": "ask surface",
         "requirement": "delegation edges are closed",
         "capability": "agent-handoff", "roles": ["AR-01", "AR-02"],
         "measurement": {"kind": "deterministic-count",
                         "assertion": "an unlisted edge is refused by the router"}},
        {"id": "AC-04", "surface_or_flow": "ask surface",
         "requirement": "irreversible actions wait for approval",
         "capability": "human-approval-gate", "roles": ["AR-01"],
         "measurement": {"kind": "status-code",
                         "assertion": "unapproved execution refused"}},
        {"id": "AC-05", "surface_or_flow": "ask surface",
         "requirement": "tools stay guarded while gated", "capability": "tool-call-guard",
         "measurement": {"kind": "deterministic-count",
                         "assertion": "only enumerated operations run"}}]
    spec["invariants"] += [
        {"id": "AM-02", "rule": "at most 8 turns, then the declared cycle-break outcome",
         "capability": "loop-budget-cap", "roles": ["AR-01", "AR-02"]}]
    spec["duties"] += [
        {"spec_ref": "AC-03", "obligation": "the router enumerates AR-01 -> AR-02 edges",
         "capability": "agent-handoff", "unit_kind": "orchestration-router"},
        {"spec_ref": "AC-04", "obligation": "propose/execute split persisted",
         "capability": "human-approval-gate", "unit_kind": "approval-gate"},
        {"spec_ref": "AC-05", "obligation": "tools delegate only",
         "capability": "tool-call-guard", "unit_kind": "tool-guard"},
        {"spec_ref": "AM-02", "obligation": "governor counts turns on the cycle",
         "capability": "loop-budget-cap", "unit_kind": "loop-governor"}]
    (settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(spec))
    return spec


check("PG14 a lawful multi-agent spec passes: handoff over declared roles, its termination "
      "invariant, an approval bound to a guard, duties on rule rows only",
      ma_spec() is not None and ddd.validate_ai_spec(AIS) is None,
      str(ddd.validate_ai_spec(AIS))[:240])
_ma = ma_spec()
_ma["duties"][0]["spec_ref"] = "AR-01"
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG14b a duty citing a MODEL ROLE is REFUSED - 'the SAME closed token as the rule it "
      "discharges' is undefined for a row without a capability (the schema bug of the "
      "review): roles are context, cited inside obligations, never discharged",
      "AR-01" in str(ddd.validate_ai_spec(AIS))
      and "not a dischargeable rule" in str(ddd.validate_ai_spec(AIS)),
      str(ddd.validate_ai_spec(AIS))[:200])
_ma = ma_spec()
_ma["duties"][1]["spec_ref"] = "AA-01"
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG14c a duty citing an ASSUMPTION is refused by the same law",
      "AA-01" in str(ddd.validate_ai_spec(AIS))
      and "not a dischargeable rule" in str(ddd.validate_ai_spec(AIS)),
      str(ddd.validate_ai_spec(AIS))[:160])
_ma = ma_spec()
_ma["invariants"] = [i for i in _ma["invariants"] if i["capability"] != "loop-budget-cap"]
_ma["duties"] = [d for d in _ma["duties"] if d["capability"] != "loop-budget-cap"]
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG14d the TOPOLOGY TERMINATION law: an agent-handoff capability with no "
      "loop-budget-cap invariant is REFUSED - each call valid and small while the LOOP "
      "spins forever, the AI class of the unbounded queue no per-unit gate could see",
      "spin forever" in str(ddd.validate_ai_spec(AIS)), str(ddd.validate_ai_spec(AIS))[:200])
_ma = ma_spec()
_ma["capabilities"] = [c for c in _ma["capabilities"] if c["capability"] != "tool-call-guard"]
_ma["duties"] = [d for d in _ma["duties"] if d["capability"] != "tool-call-guard"]
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG14e a human-approval-gate with no tool-call-guard is REFUSED - an approval gate "
      "around nothing is ceremony; the gate must guard the high-impact tool",
      "ceremony" in str(ddd.validate_ai_spec(AIS)), str(ddd.validate_ai_spec(AIS))[:180])
_ma = ma_spec()
_ma["capabilities"][2]["roles"] = ["AR-99"]
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG14f a role binding to an undeclared agent is REFUSED - every agent in the "
      "topology must be an agent in the plan (a model_roles row)",
      "AR-99" in str(ddd.validate_ai_spec(AIS))
      and "model_roles" in str(ddd.validate_ai_spec(AIS)),
      str(ddd.validate_ai_spec(AIS))[:180])
_ma = ma_spec()
_ma["invariants"][-1]["roles"] = ["AR-77"]
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG14g the same binding law covers the INVARIANT rows: a loop-budget-cap naming an "
      "agent the plan never declared is refused - the cycle it caps involves a ghost "
      "(roles bind on capability AND invariant rows, schema 2026-11-19 alignment)",
      "AR-77" in str(ddd.validate_ai_spec(AIS))
      and "model_roles" in str(ddd.validate_ai_spec(AIS)),
      str(ddd.validate_ai_spec(AIS))[:180])
_ma = ma_spec()
_ma["capabilities"].append(
    {"id": "AC-09", "surface_or_flow": "ask surface",
     "requirement": "the answer streams incremental chunks then a terminal completion",
     "capability": "incremental-progress-stream", "roles": ["AR-01", "AR-02"],
     "measurement": {"kind": "stub-call-count",
                     "assertion": "N chunk events precede the terminal completion event"}})
_ma["duties"].append(
    {"spec_ref": "AC-09", "obligation": "the port emits chunk events then completion",
     "capability": "incremental-progress-stream", "unit_kind": "stream-delivery"})
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG15 the DELIVERY-SHAPE token passes the whole gate: closed vocabulary, deterministic "
      "measurement, role binding, duty on a rule row - the spec can now tell phase 2 "
      "stream-vs-hold without naming any transport",
      ddd.validate_ai_spec(AIS) is None, str(ddd.validate_ai_spec(AIS))[:240])
_ma["capabilities"][-1]["requirement"] = ("the handler returns SSE events for the answer "
                                          "chunks")
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG16 naming the TRANSPORT in the spec is REFUSED: SSE/websocket/gRPC belong to the "
      "mapping tier - the spec states the shape (events then completion), phase 2 picks the "
      "protocol of the concrete surface (an internal consumer may not be HTTP at all)",
      "SSE" in str(ddd.validate_ai_spec(AIS)) and "TRANSPORT" in str(ddd.validate_ai_spec(AIS)),
      str(ddd.validate_ai_spec(AIS))[:200])
ai_spec()

# PG17-PG19: memory tier & technique laws (2026-11-19 operator review): the tier is decided
# by triggers, three of them machine-checked; the technique is required with any memory.
_ma = ma_spec()
del _ma["model_roles"][0]["memory_technique"]
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG17 a session/durable role with NO memory_technique is REFUSED - a tier without a "
      "compaction/retrieval rule leaves context-budget-cap unpaired (what is truncated?) and "
      "phase 2 naming a store from memory; statefulness is half a decision",
      "memory_technique" in str(ddd.validate_ai_spec(AIS)), str(ddd.validate_ai_spec(AIS))[:220])
_ma = ma_spec()
_ma["model_roles"][1]["memory_technique"] = "sliding-window"
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG17b a STATELESS role declaring a technique is refused the other way - none has no "
      "memory to manage (an envelope-complete worker states no technique)",
      "statelessness declares no memory" in str(ddd.validate_ai_spec(AIS)),
      str(ddd.validate_ai_spec(AIS))[:180])
_ma = ma_spec()
_ma["model_roles"][0]["statefulness"] = "session"
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG18 the approval trigger, machine-enforced: a `human-approval-gate` bound to a "
      "session-state role is REFUSED - an awaiting_approval that resumes through an inbound "
      "surface cannot live in a process that may restart or rebalance (in-memory approval is "
      "a workflow that silently forgets it was waiting)",
      "durable by law" in str(ddd.validate_ai_spec(AIS)), str(ddd.validate_ai_spec(AIS))[:220])
_ma = ma_spec()
_ma["model_roles"][0]["memory_technique"] = "semantic-episodic"
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG19a semantic-episodic WITHOUT a retrieval-scope-guard capability is REFUSED - "
      "embedded recall reaches across sessions by design; unscoped it reaches across tenants "
      "(a disclosure with good recall)",
      "retrieval-scope-guard" in str(ddd.validate_ai_spec(AIS)), str(ddd.validate_ai_spec(AIS))[:200])
_ma = ma_spec()
_ma["model_roles"][0]["data_classes"] = ["chat_history"]
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG19b durable memory whose data classes match no concept in the strategy's "
      "`persistence.data_model` is REFUSED with the open_questions route named - durable "
      "without a persisted concept is the shared-blackboard/audit trigger decided twice and "
      "stored nowhere",
      "chat_history" in str(ddd.validate_ai_spec(AIS)) and "open_questions" in str(ddd.validate_ai_spec(AIS)),
      str(ddd.validate_ai_spec(AIS))[:240])
_ma = ma_spec()
_ma["model_roles"][0]["memory_technique"] = "semantic-episodic"
_ma["capabilities"].append(
    {"id": "AC-09", "surface_or_flow": "ask surface",
     "requirement": "semantic recall is tenant-scoped before hydration",
     "capability": "retrieval-scope-guard", "roles": ["AR-01"],
     "measurement": {"kind": "deterministic-count",
                     "assertion": "a foreign-scope query returns nothing"}})
_ma["duties"].append(
    {"spec_ref": "AC-09", "obligation": "the store re-checks permits before hydrating recall",
     "capability": "retrieval-scope-guard", "unit_kind": "retrieval-adapter"})
(settings.COMPLETE_DIR / f"ai-spec-{AIS}.json").write_text(json.dumps(_ma))
check("PG19c the lawful semantic memory ACCEPTS: durable role + semantic-episodic + "
      "retrieval-scope-guard capability + a duty on the rule row - all four memory laws "
       "satisfied at once",
      ddd.validate_ai_spec(AIS) is None, str(ddd.validate_ai_spec(AIS))[:220])
ai_spec()

ai_spec()

# PG9/PG10: the claim channel - performance duties must be claimed at emit, (y1)-form.
CLM = "clm"
(settings.COMPLETE_DIR / f"execution-strategy-{CLM}.json").write_text(json.dumps({
    "slug": CLM, "language": "Java 21", "modules": [CLM], "bounded_contexts": ["C"],
    "surfaces": [{"name": "c write", "kind": "http", "context": "C", "operations": ["POST"], "method": "POST", "path": "/x"}],
    "persistence": {"data_model": "c_row (id)"},
    "observability": FULL_FLOOR, "risks": []}))
(settings.COMPLETE_DIR / f"performance-spec-{CLM}.json").write_text(json.dumps({
    "schema_version": "1.0", "report_type": "performance-spec", "slug": CLM,
    "metadata": {"agent": "agent-performance-architect"},
    "assumptions": [],
    "workload": {"entries": [{"id": "WB-01", "surface": "c write", "driver": "bursty",
                              "data": ["c_row"]}], "surfaces_exempt": []},
    "budgets": [{"id": "PB-07", "target": "in-flight", "limit": "bounded",
                 "capability": "rate-limit",
                 "measurement": {"kind": "status-code", "assertion": "429 under saturation"}}],
    "invariants": [], "duties": [
        {"spec_ref": "PB-07", "obligation": "admit up to the bound, refuse above",
         "capability": "rate-limit", "unit_kind": "admission-control"}],
    "risks": [], "open_questions": []}))
_clm_scaffold = gtask("T0-681", "Scaffold", 0, project=CLM, path="pom.xml",
                      intent="Generate the clm root")
_clm_scaffold["layer"] = "root"
_clm_scaffold["export"] = task_queue.SCAFFOLD_EXPORT
_clm_h = {"package": "com.clm.a", "implements": [], "dependencies": [],
          "methods": [{"signature": "run()", "returns": "void"}]}
_clm_t = gtask("T1-682", "Admit", 1, deps=("T0-681",), project=CLM,
               path="src/test/java/clm/AdmitTest.java", hints=_clm_h,
               intent="asserts admission")
_clm_steplog_claim = ["packet received (IngressPacket)"]
_clm_u = gtask("T2-682", "Admit", 2, deps=("T1-682",), project=CLM, hints=_clm_h,
               intent="the guard admits the flow")
_clm_u["observability"] = {"step_logs": _clm_steplog_claim}
settings.QUEUE_DIR.glob("*.json")
for _f in list(settings.QUEUE_DIR.glob("T?-68*-clm.json")):
    _f.unlink()
rc_pg = emit([_clm_scaffold, _clm_t, _clm_u])
check("PG9 emit REFUSES a plan whose stage-2 units never claim the performance duty "
      "(spec_ref + capability verbatim, the (y1) claim form reused): an advisory spec is "
      "the C-gap story repeating for load rules",
      bool(rc_pg) and "PB-07" in str(rc_pg) and "rate-limit" in str(rc_pg)
      and "claimed by no stage-2 unit" in str(rc_pg), str(rc_pg)[:280])
_clm_u["intent"] = ("the guard admits the flow: PB-07 rate-limit, saturation answers "
                    "the declared status")
_clm_t["intent"] = "asserts PB-07 rate-limit refuses above the bound"
for _f in list(settings.QUEUE_DIR.glob("T?-68*-clm.json")) + \
        list(settings.ERROR_DIR.glob("T?-68*-clm.json")):
    _f.unlink()
rc_pg = emit([_clm_scaffold, _clm_t, _clm_u])
check("PG10 the SAME plan ACCEPTS once the pair is spelled inside the enforcing stage-2 "
      "unit - the gate refuses the gap, not a style (and the claim line carries --replan "
      "as the operator remedy for a spec that arrived late)",
      rc_pg is None, str(rc_pg)[:280])
check("PG11 planning_claim_gaps reads the LIVE board with the same reading the emit gate "
      "applied: the claimed duty clears (the resume branch's question is discharge, "
      "not parseability)",
      task_queue.planning_claim_gaps(CLM) == []
      and (settings.QUEUE_DIR / "T2-682-clm.json").is_file(),
      str(task_queue.planning_claim_gaps(CLM))[:200])
# PG12: replan now archives the two new specs beside security's
(settings.COMPLETE_DIR / f"performance-spec-pg2x.json").write_text(json.dumps({"slug": "pg2x"}))
(settings.COMPLETE_DIR / f"ai-spec-pg2x.json").write_text(json.dumps({"slug": "pg2x"}))
moved_pg = task_queue.replan_domain("pg2x")
check("PG12 --replan archives the performance and AI specs beside the strategy and security "
      "spec - a late or stale spec now has the ONE lawful remedy, not operator file surgery",
      moved_pg["performance"] and moved_pg["ai"]
      and not (settings.COMPLETE_DIR / "performance-spec-pg2x.json").exists()
      and not (settings.COMPLETE_DIR / "ai-spec-pg2x.json").exists())
_pg_src = inspect.getsource(pipeline_mod.run)
check("PG13 the pipeline runs BOTH new phases between the specs' inputs and decomposition, "
      "stops on their refusals and open questions, fatals on planning claim gaps, and "
      "discloses the directive in the terminal verdict (source-order assertion, zero "
      "billed sessions)",
      _pg_src.index("validate_ai_directives") < _pg_src.index("run_performance")
      < _pg_src.index("run_ai") < _pg_src.index("architect writing application tasks")
      and "planning_claim_gaps" in _pg_src
      and "AI BY DIRECTIVE" in inspect.getsource(pipeline_mod._terminal_tree_report))

# --- DG. the phase-2 duty digest (2026-11-20): the engine must join duties to their rule
#     rows BEFORE the architect session, so one read replaces three specs + three tables.
#     Uses the SEC fixture plus a throwaway strategy (deleted after): the join is what the
#     architect pays turns for, and a digest that misses a join is a silent recall invitation.
sec_spec()
_dg_strategy = settings.COMPLETE_DIR / f"execution-strategy-{SEC_SLUG}.json"
_sec_data = json.loads(SEC_FILE.read_text())
_dg_ctx = sorted({str(inv.get("owner_context") or "").strip() for inv in _sec_data.get("invariants", [])
                  if str(inv.get("owner_context") or "").strip()} | {"Intake"})
_dg_strategy.write_text(json.dumps({
    "schema_version": "1.0", "report_type": "execution-strategy", "slug": SEC_SLUG,
    "bounded_contexts": _dg_ctx,
    "surfaces": [{"name": r["surface"], "kind": "http", "context": _dg_ctx[0],
                  "operations": ["post"], "traced_from": "sec", "method": "POST", "path": "/x"}
                 for r in _sec_data["authorization_matrix"] if r.get("surface")],
    "contexts_without_inbound": [], "modules": [], "layers": [], "build_order": [],
    "risks": [], "module_layout": {"base_package": "com.example.sec", "packages": [],
                                   "integration": []},
    "persistence": {"drivers": [], "data_model": [], "queries": [], "migration_plan": [],
                    "backup_recovery": "", "open_questions": []},
    "observability": {"contexts": _dg_ctx, "correlation_key": "trace",
                      "step_logs": {_dg_ctx[0]: ["sample.received"],
                                    _dg_ctx[-1]: ["window.emitted"]},
                      "audit_trail": {}, "metrics": [],
                      "export": {"schema": "jsonl", "sink": "logs/app.ndjson"}},
}, ), encoding="utf-8")
try:
    _dg_path, _dg_problems = ddd.write_phase2_digest(SEC_SLUG)
    _dg = json.loads(_dg_path.read_text(encoding="utf-8")) if _dg_path and _dg_path.is_file() else {}
    check("DG1 the digest carries duty->rule joins (test_duty arrives attached), expanded "
          "covers ids, and ONLY the mapping rows the duties claim - written to /tmp so the "
          "tasks phase reads one file where it read six (the context-blow-up root fix)",
          _dg_problems == [] and _dg.get("duties") and _dg.get("rules")
          and all(d["spec_ref"] in _dg["rules"] for d in _dg["duties"])
          and all(cid in _dg["rules"] for d in _dg["duties"] for cid in d["covers"])
          and any("test_duty" in (r.get("entry") or {}) for r in _dg["rules"].values())
          and _dg.get("mechanisms", {}).get("security", {}).get("rows")
          and str(_dg_path).startswith("/tmp/phase2-digest-")
          and _dg["specs"]["security"] == "present",
          str(_dg_problems)[:200])
    _dg2path, _dg2problems = ddd.write_phase2_digest("no-such-domain")
    check("DG2 a domain without a strategy reports a problem instead of a half digest - the "
          "pipeline stops on it before billing an architect session that would hunt files",
          _dg2problems and "no readable execution strategy" in " ".join(_dg2problems))

    # DG3-DG5: the 2026-11-20 split made the digest PER-CONTEXT and made the MECHANISM
    # TRAVEL with the duty - the planner copies a row, it does not read a table.
    _dg_duties = _dg.get("duties") or []
    print("DBG DG3 duties:", json.dumps(_dg_duties)[:600])
    print("DBG DG3 build_coordinates:", json.dumps(_dg.get("build_coordinates"))[:400])
    print("DBG DG3 gaps:", json.dumps(_dg.get("mechanisms", {}).get("security", {}).get("unmapped_duties")))
    check("DG3 every duty arrives pre-joined to its matched mapping-table row (the cells "
          "the intent copies - identifier + config key), the honest None marks exactly the "
          "duties listed as unmapped, and the table's Build-coordinates ride the digest - "
          "so a lawful plan never opens a mapping table (item 3: the digest IS the "
          "pre-filtered skill read)",
          _dg_duties
          and all("table_row" in d for d in _dg_duties)
          and any((d.get("table_row") or {}).get("cells") for d in _dg_duties)
          and all(bool((d.get("table_row") or {}).get("cells"))
                  == (f"{d['spec_ref']}:{str(d.get('capability', '')).lower()}/"
                      f"{str(d.get('unit_kind', '')).lower()}"
                      not in (_dg.get("mechanisms", {}).get("security", {})
                              .get("unmapped_duties") or []))
                  for d in _dg_duties if d["spec"] == "security")
          and _dg.get("build_coordinates", {}).get("security", {}).get("rows")
          and "starter-security" in json.dumps(_dg.get("build_coordinates")))
    _dg_first = _dg.get("draft_order")[0]
    (Path("/tmp") / f"phase2-slice-{SEC_SLUG}-ghost-context.json").write_text("{}", encoding="utf-8")
    (Path("/tmp") / f"strategy-slice-{SEC_SLUG}-ghost-context.json").write_text("{}", encoding="utf-8")
    _sl_path, _sl_problems = ddd.write_phase2_digest_slice(SEC_SLUG, _dg_first)
    _sl = json.loads(_sl_path.read_text(encoding="utf-8")) if _sl_path else {}
    _sl_other = ddd.write_phase2_digest_slice(SEC_SLUG, _dg.get("draft_order")[-1])[0]
    _sl_other_d = json.loads(_sl_other.read_text(encoding="utf-8")) if _sl_other else {}
    check("DG4 the per-context digest slice is PURE ACTIONABLE RECORDS (2026-11-20 audit "
          "round 2: the slice carried a 5.2KB rules map duplicating what the duties already "
          "joined, plus observability/data_model bytes that belong to the strategy slice): "
          "every duty arrives with its join keys ON the duty (surface/test_duty/measurement "
          "merged off the rule row), duty keys stay inside the declared set, table_rows are "
          "cells-only, mechanisms carry no rows array, and the slice holds NO rules, "
          "surfaces, data_model or observability keys - those ride the strategy slice or the "
          "full digest (the repair pass's input); attribution and the first-slice home still "
          "hold, and BOTH slice prefixes prune superseded context names",
          _sl_problems == [] and _sl.get("context") == _dg_first
          and len(_sl["duties"]) == len([d for d in _dg_duties
                                         if ddd._duty_context(d, _dg["rules"],
                                                              _dg["surfaces"]) == _dg_first])
          and _dg_duties
          and len(json.loads(
              ddd.write_phase2_digest_slice(SEC_SLUG, ddd.ROOT_CONTEXT)[0]
              .read_text(encoding="utf-8"))["duties"]) == len([d for d in _dg_duties
                                                               if ddd._duty_context(
                                                                   d, _dg["rules"],
                                                                   _dg["surfaces"]) is None])
          and all(ddd._duty_context(d, _dg["rules"], _dg["surfaces"]) is None
                  for d in json.loads(
                      ddd.write_phase2_digest_slice(SEC_SLUG, ddd.ROOT_CONTEXT)[0]
                      .read_text(encoding="utf-8"))["duties"])
          and all(set(d.keys()) <= set(ddd.SLICE_DUTY_KEYS) for d in _sl["duties"])
          and all(("surface" in d and "test_duty" in d) for d in _sl["duties"]
                  if d.get("spec") == "security"
                  and str(d.get("spec_ref", "")).startswith("AZ"))
          and all(not (d.get("table_row") or {}).get("header") for d in _sl["duties"])
          and all("rows" not in m for m in _sl.get("mechanisms", {}).values())
          and not any(k in _sl for k in ("rules", "surfaces", "data_model", "observability"))
          # the ROOT slice is the DOCUMENTED exemption: it owns the whole-domain keys
          and all(k in json.loads(ddd.write_phase2_digest_slice(
              SEC_SLUG, ddd.ROOT_CONTEXT)[0].read_text(encoding="utf-8"))
              for k in ("rules", "surfaces"))
          and not (Path("/tmp") / f"phase2-slice-{SEC_SLUG}-ghost-context.json").exists()
          and not (Path("/tmp") / f"strategy-slice-{SEC_SLUG}-ghost-context.json").exists()
          and (_dg.get("draft_order")[-1] == _dg_first
               or _sl_other_d.get("duties") == []
               or all(ddd._duty_context(d, _dg["rules"], _dg["surfaces"]) in
                      (None, _dg.get("draft_order")[-1]) for d in _sl_other_d["duties"])))
    _ss = json.loads(ddd.strategy_slice_path(SEC_SLUG, _dg_first).read_text(encoding="utf-8"))
    check("DG6 the strategy slice is what lets the session STOP reading the full plan: it "
          "carries exactly this context's surfaces, an observability block whose step_logs "
          "are keyed to this context alone, and persistence only when the domain owns a "
          "store (this fixture declares none - the slice says null instead of shipping "
          "Flyway lines the streaming context never plans against); the operator-facing "
          "phase-1 output (risks, build_order) is not planning input and stays out "
          "(2026-11-20 audit: the full 8.6KB strategy, other contexts included, rode every "
          "per-context session's every turn)",
          all(str(s.get("context", "")).strip() == _dg_first for s in _ss.get("surfaces") or [])
          and list((_ss.get("observability") or {}).get("step_logs") or {}) == [_dg_first]
          and _ss.get("persistence") is None
          and "risks" not in _ss and "build_order" not in _ss
          and _ss.get("slug") == SEC_SLUG and _ss.get("context") == _dg_first
          and set(_ss.keys()) <= {"slug", "context", "project_root", "tech_stack", "layers",
                                  "module_layout", "surfaces", "contexts_without_inbound",
                                  "persistence", "observability",
                                  "composition_root_surfaces", "rules"}
          # 2026-11-24: the root tables ride WHOLE on purpose - an entry-wide admission unit
          # decides every route of the composition root (the gateway chain's "rest denied"
          # sealed a stream route the filtered view had dropped), and the strategy's rule
          # values are the planner's only copy of the description's literals.
          and len(_ss.get("composition_root_surfaces") or []) == len(_dg.get("surfaces") or [])
          and {str(s.get("context", "")).strip()
               for s in _ss.get("composition_root_surfaces") or []} ==
              {str(s.get("context", "")).strip() for s in _dg.get("surfaces") or []}
          and isinstance(_ss.get("rules"), list))
    _order = _dg.get("draft_order") or []
    check("DG5 the draft order is a permutation of the bounded contexts (provider edges from "
          "the context map decide the sequence; no context dropped, none invented) - the "
          "symbol table of the drafted prefixes is therefore the ONLY pin source a session "
          "can ever legitimately need for backward references",
          sorted(_order) == sorted(_dg.get("bounded_contexts") or [])
          and ddd.context_draft_order("no-such-domain") == [])

    # BC. the build_coordinates edge (2026-11-24 operator review): the key the planner brief
    # promises must be UNCONDITIONAL (a key that sometimes exists is a field every session
    # pays to hunt and disprove), EMPTY lawful on stacks that ship no external manifest, and
    # never filled with another stack's coordinates by the table resolution.
    def _bc_fixture(slug, tech_stack):
        (settings.COMPLETE_DIR / f"execution-strategy-{slug}.json").write_text(json.dumps({
            "schema_version": "1.0", "report_type": "execution-strategy", "slug": slug,
            "bounded_contexts": ["Ctx"],
            "surfaces": [{"name": "S1", "kind": "http", "context": "Ctx",
                          "operations": ["post"], "traced_from": "x", "method": "POST", "path": "/x"}],
            "contexts_without_inbound": [], "modules": [], "layers": [], "build_order": [],
            "risks": [], "rules": [], "tech_stack": tech_stack,
            "module_layout": {"base_package": "p", "packages": [], "integration": []},
            "persistence": {}, "observability": {"contexts": ["Ctx"], "correlation_key": "t",
                "step_logs": {"Ctx": ["a.received"]}, "audit_trail": {}, "metrics": [],
                "export": {"schema": "jsonl", "sink": "l.ndjson"}}}), encoding="utf-8")
        (settings.COMPLETE_DIR / f"security-spec-{slug}.json").write_text(json.dumps({
            "schema_version": "1.0", "report_type": "security-spec", "slug": slug,
            "metadata": {}, "assumptions": [], "trust_boundaries": [],
            "principals": [{"id": "P-01", "name": "dev", "kind": "device", "source": "actors",
                            "authentication": "required", "credential_capability": "proof",
                            "identity_claims": []}],
            "data_classification": [],
            "authorization_matrix": [{"id": "AZ-01", "surface": "S1", "operation": "POST",
                "principal_ids": ["P-01"], "roles": [], "scopes": [], "ownership_rule": "public",
                "client_supplied_ids": [], "decision_point": {"layer": "application",
                "component": "C"}, "default": "deny", "effect_on_deny": "unauthenticated",
                "fields_read": [], "fields_written": [], "audit_event": "x",
                "test_duty": "permitted, denied, cross-owner"}],
            "invariants": [], "secrets": {"inventory": [], "handling_rules": []},
            "error_policy": {"allowed_fields": ["code"], "never_expose": [],
                             "security_audit_events": []},
            "duties": [{"spec_ref": "AZ-01", "obligation": "prove the device", "capability": "proof",
                        "unit_kind": "credential-handling", "owner_context": "Ctx"}],
            "risks": [], "open_questions": []}), encoding="utf-8")
    _bc_files = []
    try:
        _bc_results = {}
        for _bc_slug, _bc_ts in (("bcjava", {"language": "Java 21",
                                            "framework": "Spring Boot 3 WebFlux"}),
                                 ("bcpy", {"language": "Python 3.12", "framework": "FastAPI 0.115"}),
                                 ("bclegacy", {})):
            _bc_files += [settings.COMPLETE_DIR / f"execution-strategy-{_bc_slug}.json",
                          settings.COMPLETE_DIR / f"security-spec-{_bc_slug}.json"]
            _bc_fixture(_bc_slug, _bc_ts)
            _dp, _dprob = ddd.write_phase2_digest(_bc_slug)
            _full = json.loads(_dp.read_text(encoding="utf-8"))
            _sp, _sprob = ddd.write_phase2_digest_slice(_bc_slug, "Ctx")
            _slice = json.loads(_sp.read_text(encoding="utf-8"))
            _bc_results[_bc_slug] = (_dprob, _sprob, _full, _slice)
        _bj_p, _bj_sp, _bfull, _bslice = _bc_results["bcjava"]
        _py_p, _py_sp, _pfull, _pslice = _bc_results["bcpy"]
        _lg_p, _lg_sp, _lfull, _lslice = _bc_results["bclegacy"]
        check("BC1 build_coordinates is UNCONDITIONAL on both the whole digest and every "
              "per-context slice (2026-11-24: the brief promises the key; a digest that "
              "omitted it on a stack with no mapping table would send the planner hunting a "
              "field it cannot prove absent) - Java keeps its table's coordinates, the "
              "Python-shaped plan gets the key PRESENT AS EMPTY plus table:null plus every "
              "duty under unmapped_duties (never Spring rows copied into a non-Java plan), "
              "and a strategy with no tech_stack keeps the historical default map",
              _bj_p == [] and _py_p == [] and _lg_p == [] and _bj_sp == [] and _py_sp == []
              and "build_coordinates" in _bfull and _bfull["build_coordinates"].get("security", {})
              and "build_coordinates" in _bslice and _bslice["build_coordinates"].get("security")
              and "build_coordinates" in _pfull and _pfull["build_coordinates"] == {}
              and "build_coordinates" in _pslice and _pslice["build_coordinates"] == {}
              and _pfull["mechanisms"]["security"]["table"] is None
              and _pslice["mechanisms"]["security"]["unmapped_duties"]
              and "spring" not in json.dumps(_pslice).lower()
              and "build_coordinates" in _lslice and _lslice["build_coordinates"].get("security"))

    finally:
        for _bcf in _bc_files:
            _bcf.unlink(missing_ok=True)
        for _slug in ("bcjava", "bcpy", "bclegacy"):
            for _pat in (f"phase2-digest-{_slug}.json", f"phase2-slice-{_slug}-*.json",
                         f"strategy-slice-{_slug}-*.json"):
                for _f in Path("/tmp").glob(_pat):
                    _f.unlink(missing_ok=True)


    # EXP/CTX/TOOL. the 2026-11-24 planner performance pass: compact-unit expansion is
    # deterministic, the session context arrives pre-concatenated, and the profile grants
    # no search tools the brief already forbids.
    _ex_units = [
        {"n": 5, "project": "expp", "layer": "domain", "feature": None,
         "dependsOn": {"test": ["T0-001"], "code": ["T2-002"]},
         "test": {"path": "src/test/java/d/CTest.java", "export": "CTest", "intent": "i1"},
         "code": {"path": "src/main/java/d/C.java", "export": "C", "intent": "i2",
                  "ast_hints": {"package": "com.d", "implements": [], "dependencies": [],
                                "methods": [{"signature": "go()", "returns": "void"}],
                                "meters": [], "routes": [], "config": []},
                  "observability": {"step_logs": ["c.tick"]}}},
        {"n": 7, "project": "expp", "layer": "application", "feature": None,
         "test": {"path": "src/test/java/d/UTest.java", "export": "UTest", "intent": "u1"},
         "code": {"path": "src/main/java/d/U.java", "export": "U", "intent": "u2"}}]
    _ex_tasks, _ex_errs = task_queue.expand_unit_draft(_ex_units)
    _ex_by = {str(t.get("id")): t for t in _ex_tasks}
    check("EXP1 the compact UNIT form expands DETERMINISTICALLY (2026-11-24 performance pass):"
          " 2 units -> 6 canonical records; stage/agent/kind derived (tester/test, coder/code,"
          " evaluator/refactor); the ONE ast_hints lands byte-identical on T1 and T2 (z4 by"
          " construction); T2 dependsOn prepends its own T1 before the listed producers; T3"
          " shares the code path with a generated default intent when none is given; the unit's"
          " observability rides the STAGE-2 record; canonical records pass through untouched and"
          " malformed units are refused with ERR pointers, not crashes",
          _ex_errs == [] and len(_ex_tasks) == 6
          and _ex_by["T1-005"]["targetAgent"] == "agent-tester"
          and _ex_by["T2-005"]["targetAgent"] == "agent-coder"
          and _ex_by["T3-005"]["targetAgent"] == "agent-evaluator"
          and _ex_by["T3-005"]["kind"] == "refactor" and _ex_by["T3-005"]["path"] == "src/main/java/d/C.java"
          and _ex_by["T1-005"]["ast_hints"] == _ex_by["T2-005"]["ast_hints"]
          and _ex_by["T2-005"]["dependsOn"] == ["T1-005", "T0-001", "T2-002"]
          and _ex_by["T1-005"]["dependsOn"] == ["T0-001"]
          and _ex_by["T3-007"]["intent"] and "no behavior" in _ex_by["T3-007"]["intent"]
          and _ex_by["T2-005"]["observability"] == {"step_logs": ["c.tick"]}
          and "ast_hints" not in _ex_by["T1-007"]
          and task_queue.expand_unit_draft([{"stage": 1, "id": "T1-001"}])[0][0].get("id") == "T1-001"
          and bool(task_queue.expand_unit_draft([{"n": "x"}])[1]))
    def _ex_unit(deps):
        return {"n": 9, "project": "expp", "layer": "domain", "feature": None,
                "dependsOn": deps,
                "test": {"path": "t/XT.java", "export": "XT", "intent": "i"},
                "code": {"path": "s/X.java", "export": "X", "intent": "j",
                         "ast_hints": {"package": "a", "implements": [], "dependencies": [],
                                        "methods": [], "meters": [], "routes": [],
                                        "config": []}}}
    _ex_manifest = tq1, tq2 = task_queue.expand_unit_draft(
        [_ex_unit({"test": ["T1-001"], "code": ["T0-006", "T2-002"]})])[0][:2]
    _ex_flat = task_queue.expand_unit_draft([_ex_unit(["T0-001", "T0-006"])])[0][:2]
    _ex_testonly = task_queue.expand_unit_draft(
        [_ex_unit({"test": ["T0-001", "T1-001"], "code": ["T2-002"]})])[0][:2]
    check("EXP2 stage-0 bootstrap ids are UNIT facts, not side facts (2026-11-24 edge case):"
          " a build-manifest or scaffold id listed only under code propagates to the TEST"
          " record too (the tester's first red compiles against the same classpath - the"
          " manifest-precedes-compile law survives compact dependsOn), a test-only T0 id"
          " propagates to code, a FLAT dependsOn list is honored unit-wide rather than"
          " dropped, and side-specific T1-/T2- pins never migrate across sides",
          tq1["dependsOn"] == ["T0-006", "T1-001"]
          and "T0-006" in tq2["dependsOn"] and tq2["dependsOn"][0] == "T1-009"
          and "T1-001" not in tq2["dependsOn"] and "T2-002" not in tq1["dependsOn"]
          and _ex_flat[0]["dependsOn"] == ["T0-001", "T0-006"]
          and _ex_flat[1]["dependsOn"] == ["T1-009", "T0-001", "T0-006"]
          and _ex_testonly[0]["dependsOn"] == ["T0-001", "T1-001"]
          and "T0-001" in _ex_testonly[1]["dependsOn"]
          and "T2-002" not in _ex_testonly[0]["dependsOn"])
    _ctx_dir = settings.COMPLETE_DIR
    _ctx_strategy = _ctx_dir / "execution-strategy-expc.json"
    _ctx_strategy.write_text(json.dumps({"slug": "expc", "tech_stack": {}}), encoding="utf-8")
    _ctx_ss = Path("/tmp/strategy-slice-expc-Ctx.json")
    _ctx_ds = Path("/tmp/phase2-slice-expc-Ctx.json")
    _ctx_ss.write_text('{"surfaces": []}', encoding="utf-8")
    _ctx_ds.write_text('{"duties": []}', encoding="utf-8")
    _ctx_msg = prompts.build_planner_prompt(
        "/root", "r.py", "expc", "Ctx", "/tmp/tasks/expc-Ctx.json", str(_ctx_ds),
        None, {1: "T1-900"}, [], "/tmp/tasks/expc-Ctx.gaps.json", strategy_slice_path=_ctx_ss)
    _ctx_file = Path("/tmp/planner-context-expc-ctx.md")
    _ctx_text = _ctx_file.read_text(encoding="utf-8") if _ctx_file.is_file() else ""
    check("CTX1 the engine pre-concatenates the session input: build_planner_prompt writes"
          " ONE planner-context file carrying the marked STRATEGY SLICE, DIGEST SLICE, SYMBOL"
          " TABLE and CONTRACT QUICKREF sections (the 4-6 sequential reads collapse into one"
          " round-trip), and the brief routes the session to that file while still printing"
          " the provenance paths",
          _ctx_file.is_file()
          and "SECTION: STRATEGY SLICE" in _ctx_text and "SECTION: DIGEST SLICE" in _ctx_text
          and "SECTION: SYMBOL TABLE" in _ctx_text and "SECTION: CONTRACT QUICKREF" in _ctx_text
          and "surfaces" in _ctx_text and "duties" in _ctx_text
          and str(_ctx_file) in _ctx_msg and "READ EXACTLY THESE" in _ctx_msg)
    _ctx_file.unlink(missing_ok=True)
    _ctx_ss.unlink(missing_ok=True); _ctx_ds.unlink(missing_ok=True)
    _ctx_strategy.unlink(missing_ok=True)
    check("TOOL1 the planner's tools are only what its own law allows (2026-11-24): the"
          " brief forbids searching (no discovery redo, never glob a skills folder, no"
          " reading application code) - a granted search tool is an invitation the session"
          " pays for on every later turn; the Copilot mirror grants read/execute/edit, the"
          " OpenCode mirror denies glob, grep and list",
          '"read", "execute", "edit"'
          in (SEC_REPO / ".github/agents/agent-planner-architect.agent.md").read_text()
          and "search" not in (SEC_REPO / ".github/agents/agent-planner-architect.agent.md")
          .read_text().split("---\n", 2)[1]
          and "glob: deny" in (SEC_REPO / ".opencode/agents/agent-planner-architect.md").read_text()
          and "grep: deny" in (SEC_REPO / ".opencode/agents/agent-planner-architect.md").read_text()
          and "list: deny" in (SEC_REPO / ".opencode/agents/agent-planner-architect.md").read_text())
    # --- SP. the per-context PLANNING lifecycle (claim / lint / symbols / batch emit).
    _SP_SLUG = "splx"
    task_queue.clear_drafts(_SP_SLUG)
    _sp_alpha = task_queue.draft_path(_SP_SLUG, "Alpha")
    _sp_beta = task_queue.draft_path(_SP_SLUG, "Beta")
    _sp_alpha.parent.mkdir(parents=True, exist_ok=True)

    def _sp_task(tid, stage, export, deps=(), pins=()):
        return {"id": tid, "targetAgent": settings.STAGE_AGENTS[stage], "stage": stage,
                "dependsOn": list(deps), "path": f"src/main/java/m/{export}.java",
                "kind": settings.STAGE_KINDS[stage][0], "layer": "domain", "feature": None,
                "export": export, "project": _SP_SLUG,
                "intent": f"{export} owns its state and answers through the tabled methods.",
                "ast_hints": {"package": "com.m.splx", "implements": [],
                              "dependencies": [{"type": t, "task_id": p} for t, p in pins],
                              "methods": [{"signature": "go()", "returns": "void"}],
                              "meters": [], "routes": [], "config": []}}

    _sp_a1 = task_queue.next_task_id(2)  # stage 2 units: stage-correct ids from the start
    _sp_a2 = f"T2-{int(_sp_a1.split('-')[1]) + 1:03d}"
    _sp_alpha.write_text(json.dumps([
        _sp_task(_sp_a1, 2, "AlphaOne"),
        _sp_task(_sp_a2, 2, "AlphaTwo", deps=[_sp_a1])]), encoding="utf-8")
    _sp_p1, _sp_ren1 = task_queue.claim_draft(_SP_SLUG, "Alpha")
    # Beta is numbered AS IF IT WERE THE FIRST CONTEXT - the miscount the split makes
    # possible, and the arithmetic Python owns: claim renumbers Beta, never Alpha.
    _sp_beta.write_text(json.dumps([
        _sp_task(_sp_a1, 2, "BetaOne"),
        _sp_task(_sp_a2, 2, "BetaTwo", deps=[_sp_a1], pins=[("AlphaOne", _sp_a1)])]),
        encoding="utf-8")
    _sp_p2, _sp_ren2 = task_queue.claim_draft(_SP_SLUG, "Beta")
    _sp_beta_after = json.loads(_sp_beta.read_text(encoding="utf-8"))
    print("DBG SP1 p1:", _sp_p1, "ren1:", _sp_ren1, "p2:", _sp_p2, "ren2:", _sp_ren2)
    print("DBG SP1 beta_after:", json.dumps(_sp_beta_after)[:400])
    check("SP1 claim_draft joins a draft's ids to the board's number space IN PYTHON: a "
          "colliding id is renumbered and the file's own dependsOn and pin references "
          "follow, the earlier context keeps its ids, Beta's VALID backward pin to Alpha "
          "is NOT rewritten (it was never a collision), and no repair session is ever "
          "billed for arithmetic the machine can do",
          _sp_p1 == [] and _sp_ren1 == {}
          and set(_sp_ren2) == {_sp_a1, _sp_a2}
          and _sp_p2 == []
          and {t["id"] for t in _sp_beta_after} == set(_sp_ren2.values())
          and json.loads(_sp_alpha.read_text(encoding="utf-8"))[0]["id"] == _sp_a1
          and _sp_beta_after[1]["dependsOn"] == [_sp_ren2[_sp_a1]]
          and _sp_beta_after[1]["ast_hints"]["dependencies"][0]["task_id"] == _sp_a1)
    _sp_fwd = task_queue.draft_path(_SP_SLUG, "Gamma")
    _sp_g1 = task_queue.next_task_id(2)  # after the claims: a real 3-digit successor
    _sp_d1 = f"T2-{int(_sp_g1.split('-')[1]) + 1:03d}"
    _sp_fwd.write_text(json.dumps([
        _sp_task(_sp_g1, 2, "GammaOne", deps=["T9-999"])]), encoding="utf-8")
    _sp_lint = task_queue.lint_draft(_sp_fwd)
    _sp_ok = task_queue.draft_path(_SP_SLUG, "Delta")
    _sp_ok.write_text(json.dumps([_sp_task(_sp_d1, 2, "DeltaOne")]), encoding="utf-8")
    _sp_lint_ok = task_queue.lint_draft(_sp_ok)
    print("DBG SP2 lint:", repr(_sp_lint)[:400])
    print("DBG SP2 lint_ok:", repr(_sp_lint_ok)[:400])
    check("SP2 --lint is the deterministic single-file gate: a dangling reference (an id no "
          "drafted context or file holds - here one not even numbered right) is refused "
          "with an ERR pointer naming the unit and field, a clean file gets LINT-CLEAN "
          "with the batch laws explicitly DEFERRED (the claims a later context owns are not "
          "this file's verdict), and the refusal teaches the split's law - pin the symbol "
          "table or the queue, never a guessed or forward id",
      _sp_lint.startswith("ERR [")
      and any(line.startswith("ERR [") and "dependsOn" in line
              for line in _sp_lint.splitlines())
      and ("not yet drafted" in _sp_lint.lower() or "cannot be pinned" in _sp_lint.lower())
      and _sp_lint_ok.startswith("LINT-CLEAN") and "DEFERRED" in _sp_lint_ok)
    _sp_batch_reason = task_queue.emit_draft_batch(_SP_SLUG, ["Alpha", "Beta"])
    check("SP3 the ENGINE-side batch emit still validates the plan as ONE unit across the "
          "per-context files (Beta's renumbered unit resolves its cross-file pin against "
          "Alpha in the same batch), and any refusal it prints is a batch of `ERR "
          "[pointer]` lines with the edit-not-rewrite remedy - the batch law F1 bought "
          "survives the split with zero sessions spent on it",
      (_sp_batch_reason is None
       or ("references no task" not in str(_sp_batch_reason)
           and all(line.startswith("ERR [") or line.startswith("Fix EVERY") or ":" not in line
                   for line in str(_sp_batch_reason).splitlines() if line.strip()))))
    _sp_symbols_path = task_queue.DRAFT_DIR / "splx-symbols.json"
    _, _sp_sym_problems = task_queue.draft_symbol_table(
        _SP_SLUG, ["Alpha", "Beta"], _sp_symbols_path)
    _sp_syms = json.loads(_sp_symbols_path.read_text(encoding="utf-8"))
    print("DBG SP4:", json.dumps(_sp_syms)[:500])
    check("SP4 the symbol table gives the NEXT context exactly its lawful pin vocabulary: "
          "every exported unit of the drafted contexts by id, signature and shared-literal "
          "tables, plus the next-free numbers - the brief's third input, built in Python so "
          "no session pays to re-read the drafts it joins against",
          _sp_sym_problems == []
          and _sp_syms["drafted_contexts"] == ["Alpha", "Beta"]
          and {u["export"] for u in _sp_syms["units"]} >= {"AlphaOne", "BetaTwo"}
          and all(v.startswith(f"{k}-") for k, v in _sp_syms["next_free"].items())
          and len(_sp_syms["units"]) == 4)

    # SP5/SP6: the stage-0 family law for the split (2026-11-20 operator edge case).
    # Every context's session shares ONE build file; two contexts may each notice a
    # missing coordinate. The domain ships ONE scaffold and ONE build-manifest - the
    # linter and the batch emit refuse the twin naming the first, and the symbol table
    # carries the scheduled manifest with its VERBATIM intent so a later context never
    # re-schedules a coordinate it already carries.
    def _sp_manifest(mid):
        return {"id": mid, "targetAgent": "agent-container", "stage": 0, "dependsOn": [],
                "path": "pom.xml", "kind": "bootstrap", "layer": "root", "feature": None,
                "export": "build-manifest", "project": _SP_SLUG,
                "intent": "Add spring-boot-starter-security and spring-security-test "
                          "test-scoped to the build file; the parent owns versions."}

    _sp_m1 = task_queue.next_task_id(0)
    _sp_eps = task_queue.draft_path(_SP_SLUG, "Epsilon")
    # SP10's law now governs this fixture too: with a manifest scheduled, the stage-2
    # unit MUST reach it transitively - the lawful shape the new gate demands
    _sp_eps.write_text(json.dumps([
        _sp_manifest(_sp_m1),
        _sp_task(task_queue.next_task_id(2), 2, "EpsilonOne", deps=[_sp_m1])]),
        encoding="utf-8")
    _sp_l_eps = task_queue.lint_draft(_sp_eps)
    _sp_m2 = f"T0-{int(_sp_m1.split('-')[1]) + 1:03d}"
    _sp_m3 = f"T0-{int(_sp_m1.split('-')[1]) + 2:03d}"
    _sp_zeta = task_queue.draft_path(_SP_SLUG, "Zeta")
    _sp_zeta.write_text(json.dumps([_sp_manifest(_sp_m2)]), encoding="utf-8")
    _sp_l_zeta = task_queue.lint_draft(_sp_zeta)
    _sp_twin = task_queue.draft_path(_SP_SLUG, "Twin")
    _sp_twin.write_text(json.dumps([_sp_manifest(_sp_m2), _sp_manifest(_sp_m3)]),
                        encoding="utf-8")
    _sp_l_twin = task_queue.lint_draft(_sp_twin)
    _sp_emit_eps = task_queue.emit_draft_batch(_SP_SLUG, ["Epsilon"])
    _sp_emit_twin = task_queue.emit_tasks([str(_sp_twin)])
    check("SP5 the ONE-stage-0-family law is machine-enforced at BOTH tiers: the first "
          "build-manifest drafts and emits clean, a second context's manifest is refused at "
          "lint naming the FIRST task, a twin inside one file is refused too, and the batch "
          "emit carries the same refusal (2026-11-20 edge: the split shares one build file "
          "across sessions - without this gate both manifests run and last-write-wins picks "
          "the delivered pom while the first duty silently vanishes)",
      _sp_l_eps.startswith("LINT-CLEAN")
      and _sp_l_zeta.startswith("ERR") and "second 'build-manifest'" in _sp_l_zeta
      and _sp_m1 in _sp_l_zeta
      and "second 'build-manifest'" in _sp_l_twin
      and _sp_emit_eps is None
      and _sp_emit_twin and "second 'build-manifest'" in _sp_emit_twin)
    _sp_syms2_path = task_queue.DRAFT_DIR / "splx-symbols-2.json"
    _, _sp_sym2_problems = task_queue.draft_symbol_table(
        _SP_SLUG, ["Epsilon"], _sp_syms2_path)
    _sp_syms2 = json.loads(_sp_syms2_path.read_text(encoding="utf-8"))
    check("SP6 the symbol table answers the duplication before it happens: `build_manifest` "
          "carries the scheduled task's id and VERBATIM intent (the session's own coordinate "
          "check), stage-0 tasks stay OUT of the pin vocabulary (a scaffold/manifest is not "
          "a collaborator), and the brief teaches consult-first / report-dont-duplicate "
          "(AS4f pins the carriers; this pins the data)",
      _sp_sym2_problems == []
      and [m["id"] for m in _sp_syms2["build_manifest"]] == [_sp_m1]
      and "spring-boot-starter-security" in _sp_syms2["build_manifest"][0]["intent"]
      and {u["stage"] for u in _sp_syms2["units"]} == {2})

    # SP7 (PHASE 1.5, 2026-11-25 root restructure): the ONE stage-0 build manifest is
    # ENGINE data. plan_build_manifest reads the digest's build_coordinates rows (the
    # stack table's machine rows), filters conditional SCOPE cells against the PLANNED
    # capability set, and queues the single task before any session runs - the first-
    # drafter bootstrap, the missing_coordinates channel and the asymmetric first-
    # context load are all deleted. Conditional rows test the safe direction: a planned
    # capability schedules its row, an unplanned one does not, and the unconditional
    # plus test-scope rows always land (an under-included coordinate kills the first
    # red compile; an over-included one costs one inert dependency).
    _SP7_SLUG = "sply"
    task_queue.clear_drafts(_SP7_SLUG)

    def _sp7_digest_file(slug, rows, caps):
        Path(f"/tmp/phase2-digest-{slug}.json").write_text(json.dumps({
            "slug": slug,
            "duties": [{"spec": "security", "spec_ref": f"AZ-{i:02d}", "capability": c}
                       for i, c in enumerate(caps, 1)],
            "build_coordinates": {"security": {"table": "t.md", "rows": rows}},
        }), encoding="utf-8")

    _sp7_rows = [["org.example:starter-security", "compile"],
                 ["org.example:starter-bearer",
                  "compile, ONLY when `bearer-jwt-proof` is planned"],
                 ["org.example:starter-validation", "compile, with `boundary-validation`"],
                 ["org.example:test-lib", "**test**"]]
    (settings.QUEUE_DIR / f"T0-730-{_SP7_SLUG}.json").write_text(json.dumps(
        {"id": "T0-730", "targetAgent": settings.STAGE_AGENTS[0], "stage": 0,
         "dependsOn": [], "path": "pom.xml", "kind": settings.STAGE_KINDS[0][0],
         "layer": "root", "feature": None, "export": "project_scaffold",
         "project": _SP7_SLUG, "intent": "Generate the project root"}))
    _sp7_real = ddd.write_phase2_digest
    try:
        ddd.write_phase2_digest = lambda slug: (
            Path(f"/tmp/phase2-digest-{slug}.json"), [])
        _sp7_digest_file(_SP7_SLUG, _sp7_rows,
                         ["device-credential-proof", "bearer-jwt-proof"])
        _sp7_id, _sp7_notes, _sp7_probs = ddd.plan_build_manifest(_SP7_SLUG)
        _sp7_rec = json.loads((settings.QUEUE_DIR
                               / f"{_sp7_id}-{_SP7_SLUG}.json").read_text())
        _sp7_again_id, _sp7_again_notes, _ = ddd.plan_build_manifest(_SP7_SLUG)
        _sp7_bytes2 = (settings.QUEUE_DIR
                       / f"{_sp7_id}-{_SP7_SLUG}.json").read_text()
        _sp7_digest_file("splm", [], [])
        _sp7_none_id, _sp7_none_notes, _sp7_none_probs = ddd.plan_build_manifest("splm")
        _sp7_digest_file("spqz", [["org.example:starter-security", "compile"]],
                         ["device-credential-proof"])
        _sp7_scaffoldless_id, _, _sp7_scaffoldless_probs = ddd.plan_build_manifest("spqz")
        check("SP7 the ONE stage-0 build manifest is PHASE 1.5 ENGINE data: the "
              "unconditional row and the test-scope row are always scheduled, a "
              "conditional row lands exactly when its capability is planned and stays "
              "out when it is not, the queued record is the stage-0 bootstrap shape at "
              "the scaffold's own build-file path, a second call keeps the already-"
              "queued record byte-exact and names it (resume idempotence), an empty "
              "row set schedules NOTHING with a disclosed note, and rows with no "
              "scaffold on the board STOP naming phase 1 - no session ever schedules "
              "or patches the manifest again (2026-11-25: before this move 'whichever "
              "context drafts first' owned it and siblings patched through gaps files)",
          _sp7_probs == [] and _sp7_id is not None
          and _sp7_rec["export"] == "build-manifest" and _sp7_rec["path"] == "pom.xml"
          and _sp7_rec["stage"] == 0
          and _sp7_rec["targetAgent"] == settings.STAGE_AGENTS[0]
          and "org.example:starter-security" in _sp7_rec["intent"]
          and "org.example:starter-bearer" in _sp7_rec["intent"]
          and "org.example:test-lib" in _sp7_rec["intent"]
          and "starter-validation" not in _sp7_rec["intent"]
          and _sp7_again_id == _sp7_id
          and any("already" in n for n in _sp7_again_notes)
          and _sp7_bytes2 == (settings.QUEUE_DIR
                              / f"{_sp7_id}-{_SP7_SLUG}.json").read_text()
          and _sp7_none_id is None and _sp7_none_probs == []
          and any("NO manifest" in n for n in _sp7_none_notes)
          and _sp7_scaffoldless_id is None and _sp7_scaffoldless_probs
          and "phase 1" in _sp7_scaffoldless_probs[0],
          f"{_sp7_probs} {_sp7_none_notes} {_sp7_scaffoldless_probs} "
          + json.dumps(_sp7_rec)[:200])
    finally:
        ddd.write_phase2_digest = _sp7_real
    _sp7_legacy = task_queue.apply_coordinate_gaps(_SP7_SLUG, ["Ghost"])
    check("SP7b the deleted gap channel stays callable as an honest no-op: "
          "apply_coordinate_gaps returns ([], []) for any input, so a resume that "
          "still holds an old .gaps.json can neither ghost-patch nor ghost-refuse",
      _sp7_legacy == ([], []))

    # SP8 (2026-11-20 resume economics; RE-HOMED 2026-11-25 to CONTENT HASHES - R2):
    # the budget-killed planner's draft was LINT-CLEAN - the run's RESULT - yet the
    # next launch wiped every draft unconditionally and would re-bill the whole
    # context for it. Freshness is now a hash contract, not a wall-clock race: the
    # sidecar claim stamps carries the exact bytes of every binding input the draft
    # was validated against; a rewrite of a binding input flips it, an edit of the
    # derivative map does not, and touch-only churn re-bills NOTHING (the mtime
    # design re-billed provably compliant drafts whenever a doc was resaved).
    import os as _os
    _SP8b_SLUG = "splw"
    task_queue.clear_drafts(_SP8b_SLUG)
    _sp8_strategy = settings.COMPLETE_DIR / f"execution-strategy-{_SP8b_SLUG}.json"
    _sp8_strategy.write_text(json.dumps({"slug": _SP8b_SLUG}), encoding="utf-8")
    _sp8_draft = task_queue.draft_path(_SP8b_SLUG, "Alpha")
    _sp8_bytes = json.dumps([{"id": "T2-950", "project": _SP8b_SLUG}])
    _sp8_draft.write_text(_sp8_bytes, encoding="utf-8")
    task_queue.stamp_draft_meta(_SP8b_SLUG, "Alpha")
    _sp8_kept = task_queue.draft_is_fresh(_SP8b_SLUG, "Alpha")
    _sp8_strategy.write_text(json.dumps({"slug": _SP8b_SLUG, "rewritten": True}),
                             encoding="utf-8")
    _sp8_stale = task_queue.draft_is_fresh(_SP8b_SLUG, "Alpha")
    _sp8_strategy.write_text(json.dumps({"slug": _SP8b_SLUG}), encoding="utf-8")
    _sp8_rehashed_back = task_queue.draft_is_fresh(_SP8b_SLUG, "Alpha")
    _sp8_draft.unlink()
    _sp8_missing = task_queue.draft_is_fresh(_SP8b_SLUG, "Alpha")
    # the map/contract hierarchy: QUICKREF is the derivative MAP (not a hashed input -
    # a wording fix must never re-bill a compliant draft); SKILL.md IS a hashed input -
    # a content change older-dates every draft, a touch-without-change does not.
    _sp8_dag = SEC_REPO / ".opencode/skills/architect-practices/task-decomposition-dag"
    _sp8_qr = _sp8_dag / "QUICKREF.md"
    _sp8_sk = _sp8_dag / "SKILL.md"
    _sp8_qr_orig, _sp8_sk_orig = _sp8_qr.read_bytes(), _sp8_sk.read_bytes()
    _sp8_draft.write_text(_sp8_bytes, encoding="utf-8")
    task_queue.stamp_draft_meta(_SP8b_SLUG, "Alpha")
    try:
        _sp8_qr.write_bytes(_sp8_qr_orig + b"\n")
        _sp8_map_edit = task_queue.draft_is_fresh(_SP8b_SLUG, "Alpha")
        _sp8_qr.write_bytes(_sp8_qr_orig)
        _sp8_sk.write_bytes(_sp8_sk_orig + b"\n")
        _sp8_contract_edit = task_queue.draft_is_fresh(_SP8b_SLUG, "Alpha")
    finally:
        _sp8_qr.write_bytes(_sp8_qr_orig)
        _sp8_sk.write_bytes(_sp8_sk_orig)
    _sp8_restored = task_queue.draft_is_fresh(_SP8b_SLUG, "Alpha")
    _sp8_touch = None
    _sp8_src = (SEC_REPO / "orchestrators/pipeline.py").read_text()
    check("SP8 draft_is_fresh is the resume gate on CONTENT HASHES: a claimed draft "
          "whose hashes match every binding input is kept, a rewritten strategy flips "
          "it and re-writing the old bytes back re-heals it (hashes, not clocks), a "
          "normative SKILL.md CONTENT edit makes it stale while a QUICKREF map edit "
          "does not (map drift is caught by lint/emit: the gate is the law), an "
          "absent/sidecarless/malformed draft is never trusted, and the loop clears "
          "ONLY stale bytes and claims kept drafts without spawning a session",
      _sp8_kept and not _sp8_stale and _sp8_rehashed_back and not _sp8_missing
      and _sp8_map_edit and not _sp8_contract_edit and _sp8_restored
      and "[resume]" in _sp8_src and "draft_is_fresh" in _sp8_src
      and "clear_drafts(slug)" not in _sp8_src,
      f"kept={_sp8_kept} stale={_sp8_stale} back={_sp8_rehashed_back} "
      f"map={_sp8_map_edit} contract={_sp8_contract_edit} rest={_sp8_restored}")
    _sp8_strategy.unlink(missing_ok=True)

    # SP9 the symbol-table fold (2026-11-20 context audit: 46K of symbols for one
    # provider context = 57 entries carrying 23 tables three times each; the T1/T2 pair
    # is IDENTICAL by law (z4), so the pair's table rides ONCE on the stage-2 entry and
    # the twin becomes a pointer):
    _SP9_SLUG = "spfk"
    task_queue.clear_drafts(_SP9_SLUG)
    _sp9_hint = {"package": "com.m.f", "implements": [], "dependencies": [],
                 "methods": [{"signature": "go()", "returns": "void"}],
                 "meters": [{"name": "f.meter", "duty": "owns"}],
                 "routes": [{"method": "POST", "path": "/f", "duty": "serves"}],
                 "config": [{"path": "f.limit", "kind": "value"}]}
    _sp9_units = [
        {"id": "T1-960", "targetAgent": "agent-tester", "stage": 1, "dependsOn": [],
         "path": "src/test/java/m/GoTest.java", "kind": "test", "layer": "domain",
         "feature": None, "export": "GoTest", "project": _SP9_SLUG, "intent": "t",
         "ast_hints": _sp9_hint},
        {"id": "T2-960", "targetAgent": "agent-coder", "stage": 2, "dependsOn": ["T1-960"],
         "path": "src/main/java/m/Go.java", "kind": "code", "layer": "domain",
         "feature": None, "export": "Go", "project": _SP9_SLUG, "intent": "c",
         "ast_hints": _sp9_hint},
        {"id": "T3-960", "targetAgent": "agent-evaluator", "stage": 3,
         "dependsOn": ["T2-960"], "path": "src/main/java/m/Go.java", "kind": "refactor",
         "layer": "domain", "feature": None, "export": "Go", "project": _SP9_SLUG,
         "intent": "r", "ast_hints": _sp9_hint}]
    task_queue.draft_path(_SP9_SLUG, "Fold").write_text(json.dumps(_sp9_units),
                                                       encoding="utf-8")
    _sp9_sym = task_queue.DRAFT_DIR / "spfk-symbols.json"
    _, _sp9_problems = task_queue.draft_symbol_table(_SP9_SLUG, ["Fold"], _sp9_sym)
    _sp9 = json.loads(_sp9_sym.read_text(encoding="utf-8"))
    _sp9_by_id = {u["id"]: u for u in _sp9["units"]}
    check("SP9 the symbol-table fold is lossless for pins and heavy-byte for tables: the "
          "stage-2 entry is the table's ONE home (methods/meters/routes/config as plain "
          "lists), the twin stage-1 and stage-3 entries carry a `table_of` pointer instead "
          "of a third copy, every id a session may pin is still present, and the pair law "
          "(z4) is what makes this lossless - a symbol table a session cannot read is "
          "context, a symbol table that reads like the draft is waste",
      _sp9_problems == []
      and _sp9_by_id["T2-960"]["meters"] == ["f.meter"]
      and _sp9_by_id["T2-960"]["routes"] == ["POST /f"]
      and _sp9_by_id["T2-960"]["config"] == ["f.limit"]
      and _sp9_by_id["T2-960"]["methods"] == ["go()"]
      and _sp9_by_id["T1-960"].get("table_of") == "T2-960"
      and _sp9_by_id["T3-960"].get("table_of") == "T2-960"
      and "ast_hints" not in json.dumps(_sp9_by_id["T1-960"])
      and {"T1-960", "T2-960", "T3-960"} <= {u["id"] for u in _sp9["units"]})
    # SP10 (2026-11-20 root fix, AS15's prose law promoted to the machine tier): a
    # scheduled build-manifest adds coordinates to the module's build file, and a module
    # test compile pulls the WHOLE module classpath in every stack (Maven, Gradle, npm,
    # pip alike) - so EVERY stage-1/2 task of the project must reach the manifest
    # through dependsOn, transitively. The gate reads ONLY board structure: the export
    # marker and the dependency closure - zero framework vocabulary.
    _SP10_SLUG = "spo"
    task_queue.clear_drafts(_SP10_SLUG)

    def _sp10_task(tid, stage, deps, export_suffix=""):
        return {"id": tid, "targetAgent": settings.STAGE_AGENTS[stage], "stage": stage,
                "dependsOn": list(deps),
                "path": ("src/test/java/m/GTest.java" if stage == 1
                         else "src/main/java/m/G.java"),
                "kind": settings.STAGE_KINDS[stage][0], "layer": "domain",
                "feature": None, "export": "G" + export_suffix, "project": _SP10_SLUG,
                "intent": f"G stage {stage} obeys the manifest ordering",
                "ast_hints": {"package": "com.m.spo", "implements": [],
                              "dependencies": [],
                              "methods": [{"signature": "go()", "returns": "void"}],
                              "meters": [], "routes": [], "config": []}}

    _sp10_m = task_queue.next_task_id(0)
    _sp10_t1 = task_queue.next_task_id(1)
    _sp10_t2 = task_queue.next_task_id(2)
    _sp10_manifest = {"id": _sp10_m, "targetAgent": "agent-container", "stage": 0,
                      "dependsOn": [], "path": "pom.xml", "kind": "bootstrap",
                      "layer": "root", "feature": None, "export": "build-manifest",
                      "project": _SP10_SLUG, "intent": "Add org.example:starter-x"}
    _sp10_draft = task_queue.draft_path(_SP10_SLUG, "Draft")
    _sp10_draft.write_text(json.dumps([
        _sp10_manifest,
        _sp10_task(_sp10_t1, 1, []),
        _sp10_task(_sp10_t2, 2, [_sp10_t1])]), encoding="utf-8")
    _sp10_rej = task_queue.emit_tasks([str(_sp10_draft)])
    # 2026-11-24 tier split: the BATCH emit wires the missing manifest edge mechanically
    # (a manifest scheduled by a LATER context could never be pinned by the first draft -
    # refusing billed a repair session to type an id into a list), and the emitted record
    # carries the edge; single-file lint still refuses the same shape at drafting time.
    _sp10_wired = None
    for _p in settings.QUEUE_DIR.glob(f"*-{_SP10_SLUG}.json"):
        _rec = json.loads(_p.read_text())
        if _rec.get("id") == _sp10_t1:
            _sp10_wired = _sp10_m in _rec.get("dependsOn", [])
    _sp10_lint = task_queue.lint_draft(_sp10_draft)
    for _q in list(settings.QUEUE_DIR.glob(f"*-{_SP10_SLUG}.json")) + \
              list(settings.COMPLETE_DIR.glob(f"*-{_SP10_SLUG}.json")):
        _q.unlink()
    # lawful shape: T1 depends on the manifest; T2 reaches it THROUGH T1 - transitive
    _sp10_draft.write_text(json.dumps([
        _sp10_manifest,
        _sp10_task(_sp10_t1, 1, [_sp10_m]),
        _sp10_task(_sp10_t2, 2, [_sp10_t1])]), encoding="utf-8")
    _sp10_ok = task_queue.emit_tasks([str(_sp10_draft)])
    _sp10_draft.unlink(missing_ok=True)
    for _q in list(settings.QUEUE_DIR.glob("*-spo.json")) + \
              list(settings.COMPLETE_DIR.glob("*-spo.json")):
        _q.unlink()
    check("SP10 the manifest-precedes-compile gate is machine-enforced, each tier with the "
          "remedy its actor can execute (2026-11-20 law; 2026-11-24 tier split): a single-file "
          "lint BEFORE the batch REFUSES a stage-2 with no path to the scheduled "
          "build-manifest naming both ids (drafting-time hygiene the session fixes itself), "
          "while the BATCH emit WIRES the edge mechanically and accepts - the emitted unit "
          "now dependsOn the manifest (the manifest may arrive with a LATER context, so the "
          "first draft could never pin it; the 2026-11-24 batch refused 46 objects into a "
          "billed repair pass to type ids into lists); transitive reach counts (the T2 "
          "reaching the manifest through its T1 accepts), and a project without a manifest "
          "is never touched - the law is board structure, identical for Maven, Gradle, npm "
          "and pip, with no annotation or artifact name anywhere in the check",
      _sp10_rej is None and _sp10_wired
      and _sp10_lint.startswith("ERR") and "build-manifest" in _sp10_lint
      and _sp10_ok is None)
    # SP11 (2026-11-25, PHASE 1.5 coverage wire): the ONE configuration-artifact unit
    # is scheduled by the ROOT pass and its table is COMPLETED by the engine: every
    # path any stage-2 unit of the project tables is copied VERBATIM from the binder
    # into the config unit's ast_hints.config at the batch emit (values included), so
    # no session ever seeds another context's keys and no gaps file exists to patch
    # them. The refusals that remain are the ones Python cannot invent data for: NO
    # config unit at all, and one path with two different values.
    _SP11_SLUG = "spm"
    task_queue.clear_drafts(_SP11_SLUG)

    def _sp11_task(tid, export, cfg=()):
        return {"id": tid, "targetAgent": settings.STAGE_AGENTS[2], "stage": 2,
                "dependsOn": [],
                "path": ("src/main/resources/application.yml" if export == "AppConfig"
                         else f"src/main/java/m/{export}.java"),
                "kind": settings.STAGE_KINDS[2][0], "layer": "domain", "feature": None,
                "export": export, "project": _SP11_SLUG,
                "intent": (f"{export} seeds the externalized configuration surface."
                           if export == "AppConfig" else
                           f"{export} binds and reads its own tabled property paths."),
                "ast_hints": {"package": "com.m.spm", "implements": [], "dependencies": [],
                              "methods": [{"signature": "go()", "returns": "void"}],
                              "meters": [], "routes": [],
                              "config": [dict(c) for c in cfg]}}

    _sp11_alpha = task_queue.draft_path(_SP11_SLUG, "Alpha")
    _sp11_beta = task_queue.draft_path(_SP11_SLUG, "Beta")
    _sp11_alpha.write_text(json.dumps([
        _sp11_task("T2-756", "AppConfig"),
        _sp11_task("T2-757", "AlphaOne",
                   cfg=[{"path": "telemetry.alpha.rate", "kind": "value",
                         "value": "25"}])]), encoding="utf-8")
    _sp11_beta.write_text(json.dumps([
        _sp11_task("T2-758", "BetaOne",
                   cfg=[{"path": "telemetry.beta.window-seconds", "kind": "value",
                         "value": "60"}])]), encoding="utf-8")
    _sp11_emit = task_queue.emit_draft_batch(_SP11_SLUG, ["Alpha", "Beta"])
    _sp11_host = json.loads((settings.QUEUE_DIR / f"T2-756-{_SP11_SLUG}.json").read_text())
    _sp11_paths = sorted(str(e.get("path")) for e in _sp11_host["ast_hints"]["config"])
    # the refusal shapes: no host at all, and two values for one path
    _SP11b_SLUG = "spn"
    task_queue.clear_drafts(_SP11b_SLUG)
    _sp11n_alpha = task_queue.draft_path(_SP11b_SLUG, "Alpha")
    _sp11n_alpha.write_text(json.dumps([
        _sp11_task("T2-751", "OrphanBinder",
                   cfg=[{"path": "telemetry.orphan.key", "kind": "value"}])]),
        encoding="utf-8")
    __sp11n_alpha_batch = json.loads(_sp11n_alpha.read_text())
    for _t in __sp11n_alpha_batch:
        _t["project"] = _SP11b_SLUG
    _sp11n_alpha.write_text(json.dumps(__sp11n_alpha_batch), encoding="utf-8")
    _sp11n_refused = task_queue.emit_draft_batch(_SP11b_SLUG, ["Alpha"]) or ""
    _SP11c_SLUG = "spr"
    task_queue.clear_drafts(_SP11c_SLUG)
    _sp11c_alpha = task_queue.draft_path(_SP11c_SLUG, "Alpha")
    _sp11c_alpha.write_text(json.dumps([
        _sp11_task("T2-761", "AppConfig"),
        _sp11_task("T2-762", "BinderOne",
                   cfg=[{"path": "telemetry.shared.cap", "kind": "value",
                         "value": "10000"}]),
        _sp11_task("T2-763", "BinderTwo",
                   cfg=[{"path": "telemetry.shared.cap", "kind": "value",
                         "value": "5000"}])]), encoding="utf-8")
    __sp11c_alpha_batch = json.loads(_sp11c_alpha.read_text())
    for _t in __sp11c_alpha_batch:
        _t["project"] = _SP11c_SLUG
    _sp11c_alpha.write_text(json.dumps(__sp11c_alpha_batch), encoding="utf-8")
    _sp11c_refused = task_queue.emit_draft_batch(_SP11c_SLUG, ["Alpha"]) or ""
    check("SP11 config coverage is a WIRE, not a typing job and not a channel: the "
          "batch copies every binder's {path, kind, value} VERBATIM into the ONE "
          "configuration-artifact unit before the joins read it (no session seeds "
          "another context's key, no gaps file patches anything), the batch then "
          "passes with both paths on the emitted config record; a board with bound "
          "paths and NO config unit is refused naming the path and the ROOT pass, "
          "and one path tabled with two different values is refused naming the "
          "conflicting VALUES (rule (l)'s impossible pair made machine-visible by "
          "(z5)'s value field)",
      _sp11_emit is None
      and _sp11_paths == ["telemetry.alpha.rate", "telemetry.beta.window-seconds"]
      and any(str(e.get("path")) == "telemetry.beta.window-seconds"
              and str(e.get("value")) == "60" for e in _sp11_host["ast_hints"]["config"])
      and "telemetry.orphan.key" in _sp11n_refused
      and "configuration-artifact unit" in _sp11n_refused
      and "telemetry.shared.cap" in _sp11c_refused and "VALUES" in _sp11c_refused,
      f"emit={str(_sp11_emit)[:200]} paths={_sp11_paths} "
      f"orphan={_sp11n_refused[:160]} vals={_sp11c_refused[:200]}")

    # SP12 (2026-11-25 bleeding stop, v6 live): the batch is ONE unit of truth - a
    # record in the FIRST file of the batch may pin an id the LAST file defines. Staging
    # used to validate file-by-file as it loaded, so the forward sibling read
    # "dependsOn T2-038 not resolvable", the rejected record skipped `staged`, the z4
    # mirror and coverage wires skipped IT, its twin then refused as a phantom
    # "delivered" drift, and the repair session answered the ordering artifact by
    # hand-inventing pins into other drafts. Batch-first indexing makes file order
    # incapable of manufacturing refusals.
    _SP12_SLUG = "spf"
    task_queue.clear_drafts(_SP12_SLUG)

    def _sp12_task(tid, export, deps):
        return {"id": tid, "targetAgent": settings.STAGE_AGENTS[2], "stage": 2,
                "dependsOn": list(deps),
                "path": f"src/main/java/m/{export}.java",
                "kind": settings.STAGE_KINDS[2][0], "layer": "domain",
                "feature": None, "export": export, "project": _SP12_SLUG,
                "intent": f"{export} owns its tabled behavior and pins its producer.",
                "ast_hints": {"package": "com.m.spf", "implements": [],
                              "dependencies": [],
                              "methods": [{"signature": "go()", "returns": "void"}],
                              "meters": [], "routes": [], "config": []}}

    _sp12_scaffold = {"id": "T0-840", "targetAgent": settings.STAGE_AGENTS[0], "stage": 0,
                      "dependsOn": [], "path": "pom.xml",
                      "kind": settings.STAGE_KINDS[0][0], "layer": "root",
                      "feature": None, "export": "project_scaffold",
                      "project": _SP12_SLUG, "intent": "Generate the project root"}
    _sp12_gate = _sp12_task("T2-841", "Gate", ["T0-840", "T2-842"])
    _sp12_gate["ast_hints"]["dependencies"] = [{"type": "Controller", "task_id": "T2-842"}]
    _sp12_a = task_queue.draft_path(_SP12_SLUG, "Alpha")
    _sp12_b = task_queue.draft_path(_SP12_SLUG, "Beta")
    _sp12_a.write_text(json.dumps([_sp12_scaffold, _sp12_gate]), encoding="utf-8")
    _sp12_b.write_text(json.dumps([_sp12_task("T2-842", "Controller", ["T0-840"])]),
                       encoding="utf-8")
    _sp12_emit = task_queue.emit_draft_batch(_SP12_SLUG, ["Alpha", "Beta"])
    check("SP12 batch-first indexing: a draft that pins an id its SIBLING file (staged "
          "later in the same batch) defines resolves - file order cannot manufacture "
          "'not resolvable' refusals, the rejected-record cascade (skipped mirror, "
          "phantom twin-drift, hand-invented repair pins) is structurally dead, and the "
          "batch emits clean",
      _sp12_emit is None
      and (settings.QUEUE_DIR / f"T2-841-{_SP12_SLUG}.json").is_file()
      and (settings.QUEUE_DIR / f"T2-842-{_SP12_SLUG}.json").is_file(),
      str(_sp12_emit)[:260])

    # SP13/SH8 (2026-11-25 task audit): the classes the batch structurally could not
    # see - a pin without its dependsOn edge, a request-path slice naming no isolation
    # choice - are now a wire and a lint refusal, and the map + brief carry the law
    # sentence. SP13 pins the wire; SH8 pins the refusal; the carrier sentences are
    # pinned in the skills suite.
    _SP13_SLUG = "spg"
    task_queue.clear_drafts(_SP13_SLUG)
    _sp13_alpha = task_queue.draft_path(_SP13_SLUG, "Alpha")
    _sp13_beta = task_queue.draft_path(_SP13_SLUG, "Beta")

    def _sp13_rec(tid, export, deps=(), pins=()):
        return {"id": tid, "targetAgent": settings.STAGE_AGENTS[2], "stage": 2,
                "dependsOn": list(deps),
                "path": f"src/main/java/m/{export}.java",
                "kind": settings.STAGE_KINDS[2][0], "layer": "domain",
                "feature": None, "export": export, "project": _SP13_SLUG,
                "intent": f"{export} owns its tabled behavior.",
                "ast_hints": {"package": "com.m.spg", "implements": [],
                              "dependencies": [{"type": t, "task_id": p} for t, p in pins],
                              "methods": [{"signature": "go()", "returns": "void"}],
                              "meters": [], "routes": [], "config": []}}

    # Beta drafted FIRST in its file, pinning a producer that only Alpha's later file
    # defines AND omitting the edge - the exact v7 T2-005 shape
    _sp13_beta.write_text(json.dumps([_sp13_rec("T2-851", "Consumer",
                                                pins=[("Facade", "T2-850")])]),
                          encoding="utf-8")
    _sp13_alpha.write_text(json.dumps([_sp13_rec("T2-850", "Facade")]), encoding="utf-8")
    _sp13_reason = task_queue.emit_draft_batch(_SP13_SLUG, ["Alpha", "Beta"])
    _sp13_written = json.loads((settings.QUEUE_DIR / f"T2-851-{_SP13_SLUG}.json").read_text())
    check("SP13 pin-edge closure is a WIRE: a stage-2 that pins a producer without the "
          "dependsOn edge gets the edge appended mechanically at the batch (and at claim), "
          "disclosed like every other mechanical join - the payload contract's 'the "
          "producer must also be in dependsOn' survived three carriers and no gate, and "
          "the v7 audit found the missed edge shipping (2026-11-25)",
      _sp13_reason is None and "T2-850" in [str(d) for d in _sp13_written["dependsOn"]],
      str(_sp13_reason)[:200])
    for _q in list(settings.QUEUE_DIR.glob(f"*-{_SP13_SLUG}.json")):
        _q.unlink()
    task_queue.clear_drafts(_SP13_SLUG)

    _SH8_SLUG = "shy8"
    task_queue.clear_drafts(_SH8_SLUG)
    _sh8_draft = task_queue.draft_path(_SH8_SLUG, "Solo")

    def _sh8_slice(intent):
        return [{"id": "T1-860", "targetAgent": settings.STAGE_AGENTS[1], "stage": 1,
                 "dependsOn": [], "path": "src/test/java/m/SliceTest.java",
                 "kind": settings.STAGE_KINDS[1][0], "layer": "interface",
                 "feature": None, "export": "SliceTest", "project": _SH8_SLUG,
                 "intent": intent,
                 "ast_hints": {"package": "com.m.shy8", "implements": [],
                               "dependencies": [],
                               "methods": [{"signature": "go()", "returns": "void"}],
                               "meters": [],
                               "routes": [{"method": "POST", "path": "/sh",
                                          "duty": "serves"}],
                               "config": []}},
                {"id": "T2-860", "targetAgent": settings.STAGE_AGENTS[2], "stage": 2,
                 "dependsOn": ["T1-860"], "path": "src/main/java/m/Controller.java",
                 "kind": settings.STAGE_KINDS[2][0], "layer": "interface",
                 "feature": None, "export": "Controller", "project": _SH8_SLUG,
                 "intent": "Controller answers POST /sh and appends the durable row.",
                 "ast_hints": {"package": "com.m.shy8", "implements": [],
                               "dependencies": [],
                               "methods": [{"signature": "go()", "returns": "void"}],
                               "meters": [],
                               "routes": [{"method": "POST", "path": "/sh",
                                          "duty": "serves"}],
                               "config": []}}]

    _sh8_draft.write_text(json.dumps(_sh8_slice(
        "End-to-end request-path slice drives POST /sh and asserts the appended row "
        "and the counted meter.")), encoding="utf-8")
    _sh8_lint = task_queue.lint_draft(str(_sh8_draft))
    _sh8_draft.write_text(json.dumps(_sh8_slice(
        "End-to-end request-path slice drives POST /sh; each case seeds a UNIQUE "
        "device id and asserts only its own appended row.")), encoding="utf-8")
    _sh8_lint_ok = task_queue.lint_draft(str(_sh8_draft))
    _sh8_noname = task_queue.lint_draft(str(task_queue.draft_path(_SH8_SLUG, "Ghost")))
    task_queue.clear_drafts(_SH8_SLUG)
    check("SH8 the slice isolation law has its machine leg at LINT: a stage-1 that "
          "spells a slice marker without naming UNIQUE identity / RELATIVE delta / "
          "CLEANUP is refused with the exact choice sentence (naming one passes); a "
          "draft with no slice is untouched by the check; and a missing file stays a "
          "clean refusal",
      _sh8_lint.startswith("ERR") and "isolation choice" in _sh8_lint
      and "UNIQUE" in _sh8_lint and _sh8_lint_ok.startswith("LINT-CLEAN")
      and _sh8_noname.startswith("ERR"), f"{_sh8_lint[:200]} | {_sh8_lint_ok[:120]}")

    # SP14 (2026-11-25 bleeding stop): the engine injects the domain's REAL slug into
    # the worked example. The static exemplar's fake `"project": "telemetry"` was
    # copied faithfully by live sessions, each then burning sed/edit rounds (and a
    # whole repair session) rewriting the field - a placeholder a session cannot know
    # belongs to the engine, printed exactly like every other concrete.
    _sp14_real = prompts._resolved_stack_skills
    _sp14_root = settings.ROOT
    prompts._resolved_stack_skills = lambda slug: (
        [".opencode/skills/tech-stack/java-springboot3/SKILL.md"], None, None)
    settings.ROOT = SEC_REPO  # the example is read from the REAL skill tree
    try:
        _sp14_out = prompts.worked_draft_example("spexample")
    finally:
        settings.ROOT = _sp14_root
        prompts._resolved_stack_skills = _sp14_real
    check("SP14 worked_draft_example prints the domain's slug: every record's `project` "
          "is the real slug at brief-build time, the fake exemplar slug never reaches a "
          "session, and the example still parses as the two-unit owner+consumer pair",
      '"project": "spexample"' in _sp14_out and '"project": "telemetry"' not in _sp14_out
      and _sp14_out.count('"n": 21') == 1 and _sp14_out.count('"n": 22') == 1,
      _sp14_out[:160])


    # SP15 (2026-11-25 robustness primitives R1/R2/R3/R4): the four behaviors that
    # make a fresh launch unable to die from LAST launch's damage, from clock luck,
    # from whole-domain repair churn, or from hand-typed boilerplate.
    _SP15_SLUG = "spq"
    _sp15_dir = settings.COMPLETE_DIR
    _sp15_strategy = _sp15_dir / f"execution-strategy-{_SP15_SLUG}.json"
    _sp15_good = json.dumps({"slug": _SP15_SLUG, "bounded_contexts": ["Alpha"],
                             "surfaces": [{"name": "in", "kind": "http",
                                            "context": "Alpha", "method": "POST",
                                            "path": "/q", "operations": ["accept"]}],
                             "observability": {"correlation_key": "c",
                                               "step_logs": ["s"], "audit_trail": ["a"],
                                               "metrics": [], "export": "file"},
                             "rules": [], "contexts_without_inbound": []})
    _sp15_strategy.write_text(_sp15_good, encoding="utf-8")
    task_queue.snapshot_plan_inputs(_SP15_SLUG)
    _bad = json.loads(_sp15_good)
    _bad["surfaces"][0]["invented_key"] = "session restructured phase 1"
    _sp15_strategy.write_text(json.dumps(_bad), encoding="utf-8")
    _sp15_restored, _ = task_queue.verify_plan_inputs(_SP15_SLUG)
    _sp15_is_good = json.loads(_sp15_strategy.read_text()) == json.loads(_sp15_good)
    _lawful = json.loads(_sp15_good)
    _lawful["surfaces"][0]["operations"] = ["accept, consumed out-of-process by analytics"]
    _sp15_strategy.write_text(json.dumps(_lawful), encoding="utf-8")
    _, _sp15_amended = task_queue.verify_plan_inputs(_SP15_SLUG)
    _sp15_text_kept = "out-of-process" in _sp15_strategy.read_text()
    _sp15_strategy.write_text(_sp15_good, encoding="utf-8")

    # R3 routing
    _sp15_a = task_queue.draft_path(_SP15_SLUG, "Alpha")
    _sp15_b = task_queue.draft_path(_SP15_SLUG, "Beta")
    _sp15_a.write_text(json.dumps([{"id": "T2-901", "project": _SP15_SLUG, "stage": 2}]),
                       encoding="utf-8")
    _sp15_b.write_text(json.dumps([{"id": "T2-902", "project": _SP15_SLUG, "stage": 2}]),
                       encoding="utf-8")
    _sp15_routed = task_queue.route_refusals(
        "\n".join(["ERR [T2-901]: bad thing one", "   detail belongs to Alpha",
                    "ERR [T2-902]: bad thing two",
                    "ERR [spq]: domain-wide step log 'z' claimed by NO stage-2 unit",
                    "ERR [T2-999]: unknown id is nobody's draft blame"]),
        _SP15_SLUG, ["Alpha", "Beta"])

    # R4 completion at claim: T1 without a table, no T3 at all
    _sp15c = task_queue.draft_path(_SP15_SLUG, "Alpha")
    _sp15c.write_text(json.dumps([
        {"id": "T1-903", "project": _SP15_SLUG, "stage": 1,
         "targetAgent": settings.STAGE_AGENTS[1], "dependsOn": [],
         "path": "src/test/java/m/DoneTest.java", "kind": "test", "layer": "domain",
         "feature": None, "export": "DoneTest", "intent": "tests the tabled contract"},
        {"id": "T2-903", "project": _SP15_SLUG, "stage": 2,
         "targetAgent": settings.STAGE_AGENTS[2], "dependsOn": ["T1-903"],
         "path": "src/main/java/m/Done.java", "kind": "code", "layer": "domain",
         "feature": None, "export": "Done",
         "intent": "Done owns its tabled behavior and nothing else.",
         "ast_hints": {"package": "m", "implements": [], "dependencies": [],
                       "methods": [{"signature": "go()", "returns": "void"}],
                       "meters": [], "routes": [], "config": []}}]), encoding="utf-8")
    _sp15_cp, _ = task_queue.claim_draft(_SP15_SLUG, "Alpha")
    _sp15_claimed = json.loads(_sp15c.read_text())
    _sp15_fams = {t["id"]: t for t in _sp15_claimed}
    check("SP15 the four robustness primitives hold at the unit tier: an UNLAWFUL "
          "input mutation is restored to the snapshot (and the file is phase-1 bytes "
          "again), a LAWFUL text amendment survives verify and is reported as amended; "
          "refusals route to the owning draft file, unknown ids and domain-wide lines "
          "go to the domain bucket; claim COMPLETES a board draft - T1's table mirrored "
          "from T2, the missing T3 issued with the code path - and STAMPS the hash "
          "sidecar that makes freshness a content property, not a clock race",
      _sp15_restored == [f"execution-strategy-{_SP15_SLUG}.json"] and _sp15_is_good
      and _sp15_amended and _sp15_text_kept
      and _sp15_routed.get("Alpha") and _sp15_routed.get("Beta")
      and len(_sp15_routed.get("domain", [])) == 2
      and _sp15_cp == []
      and "T3-903" in _sp15_fams
      and _sp15_fams["T1-903"].get("ast_hints") == _sp15_fams["T2-903"]["ast_hints"]
      and _sp15_fams["T3-903"]["kind"] == "refactor"
      and task_queue.draft_meta_path(_SP15_SLUG, "Alpha").is_file()
      and task_queue.draft_is_fresh(_SP15_SLUG, "Alpha"),
      f"restored={_sp15_restored} good={_sp15_is_good} amended={_sp15_amended} "
      f"routed={_sp15_routed} claim={_sp15_cp} ids={sorted(_sp15_fams)}")
    _sp15_strategy.unlink(missing_ok=True)
    task_queue.clear_drafts(_SP15_SLUG)
    (settings.BLACKBOARD / "snapshots" / f"{_SP15_SLUG}-plan-inputs.json").unlink(missing_ok=True)
    # SP16 (2026-11-25 verdict-contract redesign O1-O5): the orchestrator stopped
    # being a semantic recovery layer. The law: every decision that can bill a token
    # binds ONLY to typed verdict fields, registry lookups, or filesystem facts.
    # Prose survives for display (_blame_lines, coder feedback digest) - never blame.
    _sp16_tdd = (SEC_REPO / "orchestrators/tdd_engine.py").read_text()
    _sp16_gate = (SEC_REPO / "orchestrators/test_gate.py").read_text()
    _sp16_ver = (SEC_REPO / "orchestrators/verification.py").read_text()
    _sp16_tool = (SEC_REPO / ".opencode/skills/tester-framework/run-test-tool.py").read_text()

    # O1: the tool stamps the schema; the engine's phrase tables are DEAD TEXT.
    # Behavior doors (fixtures A19/A23/A25/C1-C3 already prove the typed read):
    # a pre-schema memo and a pre-schema wave are refused, never re-decided.
    _sp16_task = task(tid="T2-960", export="Door", project="sp16")
    test_gate._write_memo(_sp16_task, "red", {"status": "compile_error", "exit_code": 1,
                                              "failures": [], "counts": {}})
    _sp16_unversioned_dropped = test_gate._read_memo(_sp16_task) is None
    test_gate._write_memo(_sp16_task, "red", {"verdict_version": 2, "status": "compile_error",
                                              "exit_code": 1, "failures": [], "counts": {}})
    _sp16_versioned_kept = test_gate._read_memo(_sp16_task) is not None

    # O2: an ambiguous selector->class join (unit_match without a class_key) falls to
    # the scoped build - the engine may NOT fuzzy-match a stem to force an answer.
    _sp16_calls = []
    _sp16_real = test_gate._tool_result
    def _sp16_fake(root, command, timeout):
        _sp16_calls.append(command)
        return {"verdict_version": 2, "status": "compile_error", "exit_code": 1,
                "classes": {"a.AmbTest": "failed", "b.AmbTest2": "failed"},
                "unit_match": {"selector": "Amb", "class_key": None, "candidates": 2},
                "missing_symbols": [], "failures": [], "counts": {}, "excerpt": []}
    test_gate._tool_result = _sp16_fake
    try:
        _sp16_ambiguous = test_gate.wave_gate_verdict(
            task(tid="T2-961", project="sp16b"), "./mvnw -Dtest=Amb test")
    finally:
        test_gate._tool_result = _sp16_real

    check("SP16 the verdict-contract redesign holds at the law tier: the engine's "
          "phrase tables (SUPERTYPE_CONFLICT_PHRASES, CASCADE_PHRASES, is_cascade, "
          "error_locations, _SYMBOL_SHAPE_RE, _excerpt_package_locations, "
          "_declared_supertypes_of_source, _norm_stem/_matches_class/_selector_of) are "
          "DELETED from engine sources while the tool owns every grammar; pre-schema "
          "memos are refused and v2 memos replay; an ambiguous typed selector falls to "
          "the scoped build instead of a stem guess; verification routes the build "
          "output through the tool's own parser; the canonicalization boundary is the "
          "single place the engine admits to touching the tree, and every fingerprint "
          "site takes it first",
          not any(name in _sp16_tdd for name in ("SUPERTYPE_CONFLICT_PHRASES",
                                                 "_SYMBOL_SHAPE_RE", "_LOCATION_PACKAGE_RE",
                                                 "_excerpt_package_locations",
                                                 "_declared_supertypes_of_source"))
          and "CASCADE_PHRASES" not in _sp16_gate and "def is_cascade" not in _sp16_gate
          and "def error_locations" not in _sp16_gate and "_norm_stem" not in _sp16_gate
          and "_matches_class" not in _sp16_gate and "_selector_of" not in _sp16_gate
          and "VERDICT_VERSION" in _sp16_tool and "verdict_version" in _sp16_tool
          and "blamed_files" in _sp16_tool and "stack_files" in _sp16_tool
          and "package_symbol_demands" in _sp16_tool and "unit_match" in _sp16_tool
          and _sp16_unversioned_dropped and _sp16_versioned_kept
          and _sp16_ambiguous is None
          and "parse_verdict_text" in _sp16_ver and "verify_verdict" in _sp16_ver
          and "def canonicalize_tree" in _sp16_gate
          and "canonicalize_tree" in _sp16_ver and "canonicalize_tree" in _sp16_tdd
          and "repair_test_imports(workspace" not in _sp16_tdd
          # O2 terminal tier: the delivered-suite class->owner join keys on the
          # declared export first, and the mock-victim join reads the typed class
          and "declared EXPORT is the join key" in _sp16_tdd
          and 'str(fl.get("class") or "")' in _sp16_tdd,
          f"unversioned={_sp16_unversioned_dropped} versioned={_sp16_versioned_kept} "
          f"ambiguous={_sp16_ambiguous} calls={len(_sp16_calls)}")

    # SP17 (2026-11-25 cold6 audit, DC closure): the security gate must PROVE that a
    # PII data class whose masking posture promises work is discharged by a duty.
    # The live board was lawful but UNCHECKED - duties closed every DC row through
    # `covers` by convention; one spec regeneration that drops a covers list loses
    # a redaction obligation silently. Convention is not a contract.
    _sp17_orig = SEC_FILE.read_text(encoding="utf-8")
    try:
        _sp17_spec = json.loads(_sp17_orig)
        _sp17_spec["data_classification"] = list(_sp17_spec.get("data_classification") or [])
        _sp17_spec["data_classification"].append({
            "id": "DC-90", "concept": "Device Credential", "pii": True, "class": "confidential",
            "fields": ["credential"], "at_rest": "encrypted", "in_transit": "TLS",
            "retention": "operator-defined", "deletion": "operator-defined",
            "masking": "partial", "log_visibility": "masked", "export_visibility": "masked",
            "error_visibility": "code-only", "reason": "pin"})
        SEC_FILE.write_text(json.dumps(_sp17_spec), encoding="utf-8")
        _sp17_unclaimed = str(ddd.validate_security_spec(SEC_SLUG) or "")
        # claim it the lawful way: an existing duty adds the class to its `covers`
        for d in _sp17_spec["duties"]:
            if str(d.get("spec_ref")) == "AZ-01":
                d["covers"] = list(d.get("covers") or []) + ["DC-90"]
                break
        SEC_FILE.write_text(json.dumps(_sp17_spec), encoding="utf-8")
        _sp17_after = str(ddd.validate_security_spec(SEC_SLUG) or "")
        # masking 'none' is a SELF-DECIDED posture - no duty needed
        for d in _sp17_spec["duties"]:
            if "DC-90" in (d.get("covers") or []):
                d["covers"] = [c for c in d["covers"] if c != "DC-90"]
        _sp17_spec["data_classification"][-1]["masking"] = "none"
        SEC_FILE.write_text(json.dumps(_sp17_spec), encoding="utf-8")
        _sp17_none = str(ddd.validate_security_spec(SEC_SLUG) or "")
    finally:
        SEC_FILE.write_text(_sp17_orig, encoding="utf-8")
    _sp17_clean = ddd.validate_security_spec(SEC_SLUG)
    check("SP17 the PII-masking duty-closure is a MACHINE edge, not convention: a "
          "data_classification row with pii=True and masking 'partial' claimed by no "
          "duty is REFUSED naming the row and the remedy, the identical row claimed "
          "through a duty's `covers` passes, masking 'none' is a self-decided posture "
          "needing no duty, and the fixture is restored pristine afterward",
      "DC-90" in _sp17_unclaimed and "discharged by no duty" in _sp17_unclaimed.lower()
      and "DC-90" not in _sp17_after and _sp17_after != _sp17_unclaimed
      and "DC-90" not in _sp17_none and _sp17_clean is None,
      f"unclaimed={'DC-90' in _sp17_unclaimed} claimed={'DC-90' not in _sp17_after} "
      f"none={'DC-90' not in _sp17_none} restored={_sp17_clean}")
    # SP19 (2026-11-25 cold6 audit, z7 budget-assertion closure): the performance
    # spec's measurement blocks are machine-readable promises - kind + assertion
    # text per budget. Enforcement was joined to stage-2 units; the ASSERTION tier
    # had no law, and the cold6 board proved two limits (PB-05 append batch,
    # PB-06 page size) asserted by no frozen test at all. The join now refuses that
    # at both tiers: inside the drafting session (lint, named by the enforcing unit)
    # and at the batch.
    _sp19_slug = "spn"
    (settings.COMPLETE_DIR / f"performance-spec-{_sp19_slug}.json").write_text(json.dumps({
        "report_type": "performance-spec", "slug": _sp19_slug, "schema_version": 1,
        "workload": [{"surface": "ingress inbound", "expected": "1k/s"}],
        "budgets": [{"id": "PB-01", "target": "batch size", "limit": "at most 100",
                     "capability": "batch-load",
                     "measurement": {"kind": "deterministic-count",
                                     "assertion": "records per write never exceed limit"}}],
        "risks": [], "open_questions": [], "assumptions": [], "invariants": [],
        "duties": [], "metadata": {}}), encoding="utf-8")
    _sp19_unasserted = [
        {"id": "T2-940", "stage": 2, "project": _sp19_slug, "kind": "code", "layer": "domain",
         "export": "BatchWriter", "path": "src/main/java/x/BatchWriter.java",
         "intent": "PB-01 batch writer: writes at most 100 records per call.",
         "dependsOn": ["T1-940"]},
        {"id": "T1-940", "stage": 1, "project": _sp19_slug, "kind": "test", "layer": "domain",
         "export": "BatchWriterTest", "path": "src/test/java/x/BatchWriterTest.java",
         "intent": "writes rows and reads them back", "dependsOn": []}]
    _sp19_err = task_queue._perf_budget_closure_errors(_sp19_slug, _sp19_unasserted, {})
    _sp19_asserted = [dict(r) for r in _sp19_unasserted]
    _sp19_asserted[1]["intent"] = ("BatchWriterTest proves the bound PB-01: records per write "
                                   "never exceed 100 (deterministic count)")
    _sp19_ok = task_queue._perf_budget_closure_errors(_sp19_slug, _sp19_asserted, {})
    check("SP19 z7 budget-assertion closure bites at both tiers: a spec-tabled "
          "measurement enforced by a stage-2 unit but cited by no stage-1 is refused "
          "naming the enforcing id, the measurement kind and assertion, and the twin "
          "test citing the PB id passes; the whole-board (emit) pool extends to every "
          "drafted record, so a budget asserted in ANY context's tests is closed",
      len(_sp19_err) == 1 and "T2-940" in _sp19_err[0] and "PB-01" in _sp19_err[0]
      and "deterministic-count" in _sp19_err[0] and _sp19_ok == [],
      f"err={_sp19_err[:1]} ok={_sp19_ok}")
    (settings.COMPLETE_DIR / f"performance-spec-{_sp19_slug}.json").unlink()


    # SH (2026-11-25 bottleneck pass): the HYDRATE tier - sessions REFERENCE shared
    # facts (uses_meters / uses_routes / uses_config / claims_steps / root_gate) and the
    # engine tables the canonical entries at claim; an unresolvable reference dies at
    # lint naming the closest tabled spelling, never in a billed repair guess.
    _SH_SLUG = "shy"
    task_queue.clear_drafts(_SH_SLUG)
    _sh_strategy = settings.COMPLETE_DIR / f"execution-strategy-{_SH_SLUG}.json"
    _sh_strategy.write_text(json.dumps({
        "slug": _SH_SLUG,
        "surfaces": [
            {"name": "ingress inbound", "context": "Alpha", "kind": "http",
             "method": "POST", "path": "/ing"},
            {"name": "stream inbound", "context": "Beta", "kind": "http",
             "method": "GET", "path": "/stream"}],
        "observability": {"correlation_key": "cid",
                          "step_logs": ["packet received"],
                          "audit_trail": ["actor/outcome"],
                          "metrics": [{"name": "shy.received"}],
                          "export": "file"}}), encoding="utf-8")
    settings.QUEUE_DIR.joinpath("T0-734-shy.json").write_text(json.dumps(
        {"id": "T0-734", "targetAgent": settings.STAGE_AGENTS[0], "stage": 0,
         "dependsOn": [], "path": "pom.xml",
         "kind": settings.STAGE_KINDS[0][0], "layer": "root", "feature": None,
         "export": "scaffold", "project": _SH_SLUG,
         "intent": "Generate the project root"}))

    def _sh_unit(n, export, layer, t_intent, c_intent, hints, refs=None):
        code = {"path": f"src/main/java/m/{export}.java", "export": export,
                "intent": c_intent, "ast_hints": hints}
        code.update(refs or {})
        return {"n": n, "project": _SH_SLUG, "layer": layer, "feature": None,
                "dependsOn": {"test": ["T0-734"], "code": ["T0-734"]},
                "test": {"path": f"src/test/java/m/{export}Test.java",
                         "export": f"{export}Test", "intent": t_intent},
                "code": code}

    def _sh_hints(deps=None, meters=None, routes=None):
        return {"package": "com.m.shy", "implements": [],
                "dependencies": deps or [],
                "methods": [{"signature": "go()", "returns": "void"}],
                "meters": meters or [], "routes": routes or [], "config": []}

    _sh_alpha = task_queue.draft_path(_SH_SLUG, "Alpha")
    _sh_alpha.write_text(json.dumps([
        _sh_unit(735, "Facade", "infrastructure",
                 "FacadeTest proves the tabled contract both ways",
                 "Facade owns its tabled behavior and nothing else.",
                 _sh_hints(meters=[{"name": "shy.received", "duty": "owns"}])),
        _sh_unit(736, "Admission", "infrastructure",
                 "AdmissionTest proves the tabled contract both ways",
                 "Admission owns its tabled behavior and nothing else.",
                 _sh_hints(deps=[{"type": "Facade", "task_id": "T2-735"}]),
                 refs={"uses_meters": ["shy.received"],
                       "uses_routes": ["GET /stream"],
                       "claims_steps": ["packet received"],
                       "root_gate": True})]), encoding="utf-8")
    _sh_beta = task_queue.draft_path(_SH_SLUG, "Beta")
    _sh_beta.write_text(json.dumps([
        _sh_unit(737, "Stream", "interface",
                 "End-to-end request-path slice drives GET /stream and asserts the "
                 "durable effect",
                 "Stream owns its tabled behavior and nothing else.",
                 _sh_hints(deps=[{"type": "Admission", "task_id": "T2-736"}],
                           routes=[{"method": "GET", "path": "/stream",
                                    "duty": "serves"}]))]), encoding="utf-8")
    _sh_alpha2 = json.loads(_sh_alpha.read_text())
    _sh_alpha2.append(_sh_unit(738, "Ingress", "interface",
                               "IngressTest proves the tabled contract both ways",
                               "Ingress owns its tabled behavior and nothing else.",
                               _sh_hints(routes=[{"method": "POST", "path": "/ing",
                                                  "duty": "serves"}])))
    _sh_alpha.write_text(json.dumps(_sh_alpha2), encoding="utf-8")
    _sh_lint = task_queue.lint_draft(str(_sh_alpha))
    _sh_claims = task_queue.claim_draft(_SH_SLUG, "Alpha")
    _sh_beta_claim = task_queue.claim_draft(_SH_SLUG, "Beta")
    _sh_after = json.loads(_sh_alpha.read_text())
    _sh_guard = [t for t in _sh_after if t["id"] == "T2-736"][0]
    _sh_twin = [t for t in _sh_after if t["id"] == "T1-736"][0]
    _sh_emit = task_queue.emit_draft_batch(_SH_SLUG, ["Alpha", "Beta"])

    _SH2_SLUG = "shz"
    task_queue.clear_drafts(_SH2_SLUG)
    (settings.COMPLETE_DIR / f"execution-strategy-{_SH2_SLUG}.json").write_text(
        json.dumps({"slug": _SH2_SLUG, "surfaces": [],
                    "observability": {"correlation_key": "cid",
                                      "step_logs": ["packet received"],
                                      "audit_trail": ["a"],
                                      "metrics": [{"name": "shy.received"}],
                                      "export": "file"}}), encoding="utf-8")
    _sh2_draft = task_queue.draft_path(_SH2_SLUG, "Solo")
    _sh2_draft.write_text(json.dumps([_sh_unit(
        738, "Drifter", "infrastructure",
        "DrifterTest proves the drift refusal",
        "Drifter references two facts nobody owns.",
        {"package": "com.m.shz", "implements": [], "dependencies": [],
         "methods": [{"signature": "go()", "returns": "void"}],
         "meters": [], "routes": [], "config": []},
        refs={"uses_meters": ["shy.rejected"],
              "claims_steps": ["packet recived"]})]), encoding="utf-8")
    _sh2_lint = task_queue.lint_draft(str(_sh2_draft))

    _sh3_path = task_queue.draft_path(_SH_SLUG, "Gamma")
    _sh3_path.write_text(json.dumps([_sh_unit(
        739, "Gate", "infrastructure",
        "GateTest proves the second gate refuses",
        "A second gate collides with the ONE gate law.",
        _sh_hints(), refs={"root_gate": True})]), encoding="utf-8")
    _sh3_problems, _ = task_queue.claim_draft(_SH_SLUG, "Gamma")

    check("SH1 the hydrate tier works end-to-end: references pass LINT-CLEAN; claim "
          "hydrates the canonical entries - the meter from the owner's spelling, the "
          "sibling context's route from the strategy surface table, the step log "
          "VERBATIM from the floor, BOTH root addresses from the composition-root "
          "table - the shorthand keys are gone from the claimed bytes, the T1 twin "
          "carries the identical table (z4 by construction), root_gate STAYS as the "
          "machine marker, and the batch emit of both contexts passes every literal "
          "join",
      _sh_lint.startswith("LINT-CLEAN")
      and _sh_claims[0] == [] and _sh_beta_claim[0] == []
      and all(k not in _sh_guard for k in ("uses_meters", "uses_routes",
                                           "claims_steps"))
      and {"name": "shy.received", "duty": "uses"} in _sh_guard["ast_hints"]["meters"]
      and {"method": "GET", "path": "/stream", "duty": "uses"}
          in _sh_guard["ast_hints"]["routes"]
      and {"method": "POST", "path": "/ing", "duty": "uses"}
          in _sh_guard["ast_hints"]["routes"]
      and _sh_guard["observability"]["step_logs"] == ["packet received"]
      and _sh_guard.get("root_gate") is True
      and _sh_twin["ast_hints"] == _sh_guard["ast_hints"]
      and _sh_emit is None,
      f"lint={_sh_lint[:160]} claims={_sh_claims} beta={_sh_beta_claim} "
      f"emit={str(_sh_emit)[:220]}")
    check("SH2 an unresolvable reference is a deterministic lint refusal naming the "
          "closest tabled spelling - the drift the repair rounds used to pay for is "
          "refused BEFORE any claim",
      _sh2_lint.startswith("ERR") and "shy.rejected" in _sh2_lint
      and "closest" in _sh2_lint.lower() and "packet" in _sh2_lint,
      _sh2_lint[:300])
    check("SH3 ONE GATE PER ROOT is machine-checked by the marker: a second root_gate "
          "unit is refused naming the first, so no session can install two root-wide "
          "admissions (the v4 fatal, closed by the data path rather than by prose)",
      any("root gate" in str(p) and "T2-736" in str(p) for p in _sh3_problems),
      str(_sh3_problems)[:300])

    for _sp_p in (_sp_alpha, _sp_beta, _sp_fwd, _sp_ok, _sp_symbols_path,
                  _sp_eps, _sp_zeta, _sp_twin, _sp_syms2_path,
                  _sp8_strategy, _sp8_draft,
                  task_queue.draft_path(_SP9_SLUG, "Fold"), _sp9_sym,
                  _sh_alpha, _sh_beta, _sh_strategy, _sh2_draft,
                  _sh3_path, settings.QUEUE_DIR / "T0-734-shy.json",
                  settings.COMPLETE_DIR / "execution-strategy-shz.json",
                  Path("/tmp/phase2-digest-sply.json"), Path("/tmp/phase2-digest-splm.json"),
                  Path("/tmp/phase2-digest-spqz.json"),
                  settings.QUEUE_DIR / "T0-730-sply.json"):
        _sp_p.unlink(missing_ok=True)
    for _sp_s in ("sply", "splm", "spqz", _SP11_SLUG, _SP11b_SLUG, _SP11c_SLUG, _SP12_SLUG):
        task_queue.clear_drafts(_sp_s)
        for _sp_q in list(settings.QUEUE_DIR.glob(f"*-{_sp_s}.json")) + \
                      list(settings.COMPLETE_DIR.glob(f"*-{_sp_s}.json")):
            _sp_q.unlink(missing_ok=True)
    for _q in list(settings.QUEUE_DIR.glob("*-splx.json")) + \
              list(settings.COMPLETE_DIR.glob("*-splx.json")):
        _q.unlink()
finally:
    _dg_strategy.unlink(missing_ok=True)
    if SEC_FILE.exists():
        sec_spec()

bad_names = [n for n, c in CHECKS if not c]
print(f"\nENGINE-DECISIONS SUITE: {len(CHECKS) - len(bad_names)}/{len(CHECKS)}")
print("FAILED:", bad_names if bad_names else "none")
sys.exit(1 if bad_names else 0)
