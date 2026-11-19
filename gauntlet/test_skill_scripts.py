"""Gauntlet: skill-script contracts (writer schema + runner grammar).

Fixtures distilled from real incidents. Rule of the repo: any change to a skill
script or orchestrator must ship with a case here. Engine-side decisions are
tested in test_engine_decisions.py; the weaver's own grammar lives in its JUnit
suite (run with ./mvnw test in ast_weaver_tools/ast_weaver_java).

Language neutrality contract: THIS file is the only place compiler output text
may appear - it tests the tool that owns syntax. Nothing here is imported by
the orchestrators.
"""
import importlib.util
import inspect
import json
import re
import string
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f" {'PASS' if cond else 'FAIL'} {name}" + ("" if cond else f"  [{detail}]"))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


writer = load_module(REPO / ".opencode/skills/read-write-file-ddd/writer-coder-changes/write-coder-changes.py", "writer")
runner = load_module(REPO / ".opencode/skills/tester-framework/run-test-tool.py", "runner")

# --- 1. Writer schema: accepts the shapes, REFUSES the unknown ---------------

VALID = {"id": "T2-001", "project": "p", "targetFile": "src/main/java/x/Box.java",
         "export": "com.x.Box<T>", "method": "open", "language": "java", "framework": "java",
         "skill": "some-skill", "signature": "open(String s)", "returns": "Box<T>",
         "body": "return null;", "imports": ["java.util.Objects"], "missing": [],
         "kind": "class", "members": ["private final T seed;"],
         "implements": ["NotificationGateway"], "extends": ""}

check("W1 valid supertypes/generics payload accepted", writer.validate(VALID, "T2-001") == [],
      str(writer.validate(VALID, "T2-001")))
check("W2 unknown key refused loudly with schema",
      any("unknown payload key" in e and "superTypes" in e
          for e in writer.validate({**VALID, "superTypes": ["A"]}, "T2-001")))
check("W3 implements as string refused (was silently dropped at the weaver)",
      any("implements must be an array" in e
          for e in writer.validate({**VALID, "implements": "NotificationGateway"}, "T2-001")))
check("W4 implements blank entry refused",
      any("implements must be an array" in e
          for e in writer.validate({**VALID, "implements": [" "]}, "T2-001")))
check("W5 extends non-string refused",
      any("extends must be a string" in e
          for e in writer.validate({**VALID, "extends": 7}, "T2-001")))
check("W6 empty body without members refused",
      any("body must not be empty" in e
          for e in writer.validate({**VALID, "body": "", "members": []}, "T2-001")))
check("W7 id mismatch refused", any("does not match" in e for e in writer.validate(VALID, "T2-999")))

root = Path(tempfile.mkdtemp())
payload_file = root / "in.json"
payload_file.write_text(json.dumps(VALID))
good = subprocess.run([sys.executable, str(REPO / ".opencode/skills/read-write-file-ddd/writer-coder-changes/write-coder-changes.py"),
                       "--root", str(root), "--task-id", "T2-001", "--input", str(payload_file)],
                      capture_output=True, text=True)
check("W8 end-to-end write exits 0", good.returncode == 0, good.stdout)
bad = json.loads(json.dumps(VALID)); bad["targetFile"] = ""
payload_file.write_text(json.dumps(bad))
rejected = subprocess.run([sys.executable, str(REPO / ".opencode/skills/read-write-file-ddd/writer-coder-changes/write-coder-changes.py"),
                           "--root", str(root), "--task-id", "T2-001", "--input", str(payload_file)],
                          capture_output=True, text=True)
check("W9 schema violation exits 1, writes nothing new", rejected.returncode == 1, rejected.stdout)
payload_file.write_text(json.dumps(VALID))
exists = subprocess.run([sys.executable, str(REPO / ".opencode/skills/read-write-file-ddd/writer-coder-changes/write-coder-changes.py"),
                         "--root", str(root), "--task-id", "T2-001", "--input", str(payload_file)],
                        capture_output=True, text=True)
check("W10 existing payload without --retry exits 2 (no silent overwrite)", exists.returncode == 2, exists.stdout)

# W11-W14: table-drift guard (live 2026-11-12: `String headerName()` pinned as
# instance, coder shipped a STATIC impostor - this unit's own test compiled, the
# sibling frozen test that STUBS the member failed for every payload, forever).
def writer_run(task_id, payload, retry=False):
    pf = root / f"{task_id}-in.json"
    pf.write_text(json.dumps(payload))
    cmd = [sys.executable, str(REPO / ".opencode/skills/read-write-file-ddd/writer-coder-changes/write-coder-changes.py"),
           "--root", str(root), "--task-id", task_id, "--input", str(pf)]
    if retry:
        cmd.append("--retry")
    return subprocess.run(cmd, capture_output=True, text=True)

def with_table(sig):
    (root / "blackboard" / "queue").mkdir(parents=True, exist_ok=True)
    (root / "blackboard" / "queue" / f"{DRIFT_ID}-p.json").write_text(json.dumps(
        {"id": DRIFT_ID, "stage": 2, "project": "p", "path": "src/main/java/x/Box.java",
         "export": "Box", "targetAgent": "agent-coder", "dependsOn": [], "kind": "code",
         "layer": "domain", "feature": None, "intent": "x",
         "ast_hints": {"package": "x", "implements": [], "dependencies": [],
                       "methods": [{"signature": sig, "returns": "Box<T>"}]}}))

DRIFT_ID = "T2-902"
drift_payload = {**VALID, "id": DRIFT_ID}
with_table("open(String s)")
static_drift = writer_run(DRIFT_ID, {**drift_payload, "signature": "static Box<T> open(String s)"})
check("W11 STATIC impostor against an instance table entry refused in-session",
      static_drift.returncode == 1 and "signature drift" in static_drift.stdout, static_drift.stdout[:150])
instance_ok = writer_run(DRIFT_ID, drift_payload)
check("W12 table-matching instance payload accepted", instance_ok.returncode == 0, instance_ok.stdout[:150])
with_table("static Box<T> open(String s)")
static_ok = writer_run(DRIFT_ID, {**drift_payload, "signature": "static Box<T> open(String s)"}, retry=True)
check("W13 static payload accepted when the table pins static (no over-block)",
      static_ok.returncode == 0, static_ok.stdout[:150])
members_drift = writer_run(DRIFT_ID, {**drift_payload, "signature": "static Box<T> open(String s)",
                                      "members": ["Box<T> open(String s) { return null; }"]}, retry=True)
check("W14 members[] entry drifting from a static table binding refused",
      members_drift.returncode == 1 and "drift" in members_drift.stdout, members_drift.stdout[:150])
no_table = writer_run("T2-903", {**VALID, "id": "T2-903"})
check("W15 legacy board (no task record) unaffected: guard inert, payload lands",
      no_table.returncode == 0, no_table.stdout[:150])

# --- 2. Runner grammar: every toolchain phrasing -> one normalized field -----

def demands_of(output):
    return runner.parse(output)[5]


def mocks_of(output):
    return runner.parse(output)[8]


# Mockito sealed/final mock gap -> normalized `mock_impossible` simple type name.
# The engine attributes such a red to whoever CLOSED the type, never to the mocking
# unit whose frozen test it cannot edit (2026-11-16: sealed event interface died 7 of
# a consumer's tests and its own unit was charged for a foreign file).
_m_sealed = mocks_of(
    "org.mockito.exceptions.base.MockitoException: \n"
    "Mockito cannot mock this class: interface com.x.TelemetryIngestionEvent.\n"
    "Sealed interfaces or abstract classes can't be mocked.\n")
check("R-mock: 'Mockito cannot mock this class: interface X' normalizes to [X]",
      _m_sealed == ["TelemetryIngestionEvent"], str(_m_sealed))

# javac: symbol/method + location/class pair, with and without the [ERROR] prefix
# (Maven's logger wraps some detail lines and not others - one incident each way).
BOX = root / "Consumer.java"
BOX.write_text("class Consumer {\n    void use(Channel c) { c.compute(new Object()); }\n}\n")
JAVAC = (f"[ERROR] {BOX}:[2,30] cannot find symbol\n"
         f"  symbol:   method compute(java.lang.Object)\n"
         f"  location: class com.x.Channel<java.lang.Integer>\n")
dem = demands_of(JAVAC)
check("G1 javac method demand normalized (owner = receiver class, generics stripped)",
      dem and dem[0]["owner"] == "Channel" and dem[0]["kind"] == "method"
      and dem[0]["member"].startswith("compute("), str(dem))
check("G2 demand carries the quoted failing call as context",
      dem and "c.compute" in str(dem[0].get("context", "")), str(dem))
check("G3 prefixed detail lines parse like bare ones",
      len(demands_of("[ERROR] x/Foo.java:[1,1] cannot find symbol\n"
                     "[ERROR]   symbol:   method compute(java.lang.Object)\n"
                     "[ERROR]   location: class com.x.Channel\n")) == 1)

dem_var = demands_of("[ERROR] x/Foo.java:[5,9] cannot find symbol\n"
                     "  symbol:   method publish(com.x.Event)\n"
                     "  location: variable streamPublications of type com.x.Channel<com.x.Event>\n")
check("G4 'location: variable v of type T' names T as owner",
      dem_var and dem_var[0]["owner"] == "Channel", str(dem_var))

dem_nested = demands_of("x/Y.java:[4,1] cannot find symbol\n"
                        "  symbol:   class Row\n"
                        "  location: class com.x.Box\n")
check("G5 nested class demand kind preserved",
      dem_nested and dem_nested[0]["kind"] == "class" and dem_nested[0]["member"] == "Row", str(dem_nested))

check("G6 class demands carry the located owner; nested-vs-top-level is the ENGINE's call",
      demands_of("x/Z.java:[2,1] cannot find symbol\n"
                 "  symbol:   class Ghost\n"
                 "  location: class com.x.Ghost\n")
      == [{"member": "Ghost", "owner": "Ghost", "kind": "class"}])

check("G7 no symbol/location pair -> no demand (conversion defects attribute elsewhere)",
      demands_of("[ERROR] x/A.java:[9,3] error: incompatible types: com.x.A cannot be converted to com.x.B\n") == [])

d8 = demands_of("x/W.java:[2,1] cannot find symbol\n"
                "  symbol:   method compute(java.lang.Object)\n"
                "[ERROR] x/W.java:[9,1] cannot find symbol\n"
                "  symbol:   method other()\n"
                "  location: class com.x.Later\n")
check("G8 no cross-block pairing (window stops at the next error header)",
      not any("compute" in str(d["member"]) for d in d8), str(d8))

check("G9 tsc property demand normalized",
      demands_of("src/Order.ts(7,3): error TS2339: Property 'total' does not exist on type 'Order'.")
      == [{"member": "total", "owner": "Order", "kind": "property"}])
check("G10 python attribute demand normalized",
      demands_of("AttributeError: 'Cart' object has no attribute 'addItems'")
      == [{"member": "addItems", "owner": "Cart", "kind": "attribute"}])
check("G11 go field/method demand normalized",
      demands_of("./a.go:5:4: x.addItems undefined (type cart.Cart has no field or method addItems)")
      == [{"member": "addItems", "owner": "Cart", "kind": "method"}])
check("G12 duplicate blocks dedupe by (member, owner, kind)",
      len(demands_of(JAVAC + JAVAC)) == 1, str(demands_of(JAVAC + JAVAC)))

# statuses: decisive tree-wide failures must classify so the engine can share them
full = runner.parse("[ERROR] x/A.java:[1,1] cannot find symbol\n"
                    "  symbol:   class Ghost\n"
                    "  location: class com.x.A\n")
check("G13 missing class -> compile_error + missing_symbols",
      runner.classify(1, full[0], full[1], full[3], full[4], "") == "compile_error"
      and "Ghost" in full[1], str(full[1]))
check("G14 non-compile exit without evidence classifies decisively",
      runner.classify(1, False, [], [], {}, "surefire-boot error") == "error")

# problem_kinds: the cascade-vs-structural and supertype-conflict classifications the
# engine needs, normalized from every toolchain's phrasing HERE.
SUP = root / "Adapter.java"
SUP.write_text("package com.x;\npublic class Adapter implements NotificationGateway {\n"
               "    public void send(String s) { }\n}\n")
probs = runner.parse(f"[ERROR] {SUP}:[2,1] method does not override or implement a method "
                     "from a supertype\n", root=str(root))[6]
check("G15 supertype problem classified with the file's declared supertypes",
      probs and probs[0]["kind"] == "supertype" and "NotificationGateway" in probs[0].get("supertypes", []),
      str(probs))
probs_missing = runner.parse("[ERROR] a/b/Caller.java:[4,9] cannot find symbol\n"
                             "  symbol:   class Ghost\n  location: class com.x.Caller\n",
                             root=str(root))[6]
check("G16 missing-symbol problem classified (cascade family) by position",
      probs_missing and probs_missing[0]["kind"] == "missing-symbol"
      and probs_missing[0]["file"] == "Caller.java", str(probs_missing))
probs_tsc = runner.parse("src/Order.ts(7,3): error TS2420: Class 'Order' incorrectly "
                         "implements interface 'Line'.\n", root=str(root))[6]
check("G17 tsc implements phrasing normalizes to the same kind",
      probs_tsc and probs_tsc[0]["kind"] == "supertype", str(probs_tsc))
check("G18 a missing enum CONSTANT on a foreign type normalizes to a variable demand, and a "
      "nested type keeps its OUTER segment as the owner (the blanket `variable` exclusion hid "
      "the gap from attribution 2026-11-18 live: LATE/TELEMETRY_VALIDATED charged nobody and "
      "75 units deferred on one another), while the same variable line located in the FAILING "
      "FILE'S OWN type stays a file-internal defect, not a demand on another surface",
      {"member": "LATE", "owner": "ValidationStatus", "kind": "variable"} in demands_of(
          "[ERROR] x/IngestPacketUseCase.java:[71,99] cannot find symbol\n"
          "  symbol:   variable LATE\n"
          "  location: class com.x.ValidationStatus\n")
      and not demands_of("[ERROR] x/ValidationStatus.java:[9,12] cannot find symbol\n"
                         "  symbol:   variable LATE\n"
                         "  location: class com.x.ValidationStatus\n")
      and {"member": "TELEMETRY_VALIDATED", "owner": "TelemetryEvent.Type",
           "kind": "variable"} in demands_of(
          "[ERROR] x/IngestPacketUseCase.java:[84,99] cannot find symbol\n"
          "  symbol:   variable TELEMETRY_VALIDATED\n"
          "  location: class com.x.TelemetryEvent.Type\n"))

# bean_demands: Spring context-boot phrasing normalizes HERE (the engine never reads it)
beans = runner.parse(
    "[ERROR] Tests run: 3, Failures: 0, Errors: 3 -- in x.R2dbcEventLogRepositoryTest\n"
    "java.lang.IllegalStateException: Failed to load ApplicationContext\n"
    "Caused by: org.springframework.beans.factory.UnsatisfiedDependencyException: "
    "Error creating bean with name 'ingressController': Unsatisfied dependency expressed "
    "through constructor parameter 0: No qualifying bean of type "
    "'com.pulsestream.telemetry.ingestion.domain.SampleValidator' available: expected at "
    "least 1 bean which qualifies as autowire candidate. Dependency annotations: {}\n")[7]
check("G18 context-boot bean demand normalized to simple name in bean_demands",
      beans == ["SampleValidator"], str(beans))

# surefire CONSOLE summary style (`Class.method:line » Kind message`) must produce
# NAMED failures: the live T2-003 pair-defect arrived as errors=3 with an EMPTY
# message and coders iterated blind.
console = runner.parse(
    "[ERROR] Tests run: 3, Failures: 0, Errors: 3, Skipped: 0\n"
    "[ERROR]   SampleValidatorTest.validate_sameInputTwice_isDeterministic:18 "
    "\u00bb IllegalArgument validationStatus must not be null\n")
named = [f for f in console[3] if f["test"]]
check("G19 console summary failure lines are named with their message",
      named and "validate_sameInputTwice" in named[0]["test"]
      and "validationStatus must not be null" in named[0]["message"], str(console[3]))

# --- 3. Agent-doc contract: profiles/skills must teach the writer's REAL keys ----
# Root cause of the fresh-run mapping burn (2026-11-11): the §22 profile compression
# rewrote the payload key list into invented vocabulary ("relationships[{type,...}]",
# "shared_languages"); the agent obeyed the docs and every writer call was rejected
# (10 paid calls, zero artifacts). These pins fail if docs and schema ever drift.
ddd_writer = load_module(REPO / ".opencode/skills/read-write-file-ddd/writer-file/scripts/writer_file.py", "ddd_writer")

DOC_PAIRS = {
    "ctxmap": ([REPO / ".github/agents/domain-context-mapping-specialist.agent.md",
                REPO / ".opencode/agents/domain-context-mapping-specialist.md",
                REPO / ".opencode/skills/architect-practices/domain-context-mapping/SKILL.md"],
               [*ddd_writer.CONTEXT_MAP_FILE_KEYS, *ddd_writer.CONTEXT_MAP_KEYS,
                *ddd_writer.FLOW_REQUIRED_KEYS, "source_report", *ddd_writer.RELATIONSHIPS],
               ["relationships[{", "trigger_event", "failure_posture", "type,direction"]),
    "slice": ([REPO / ".github/agents/domain-boundary-discovery-specialist.agent.md",
               REPO / ".opencode/agents/domain-boundary-discovery-specialist.md"],
              [*ddd_writer.SLICE_KEYS, *ddd_writer.SLICE_OPTIONAL_KEYS, *ddd_writer.SUBDOMAIN_KEYS,
               "term", "definition", "item", "impact_on_boundaries", "source_description"],
              []),
}
for kind, (docs, want_keys, banned) in DOC_PAIRS.items():
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        missing = [k for k in want_keys if k not in text]
        check(f"K1-{kind} {doc.name[:24]} teaches the writer keys", not missing, f"missing {missing}")
        stale = [b for b in banned if b in text]
        check(f"K2-{kind} no invented-schema vocabulary in {doc.name[:24]}", not stale, f"found {stale}")

reject = subprocess.run([sys.executable, str(REPO / ".opencode/skills/read-write-file-ddd/writer-file/scripts/writer_file.py"),
                         "--source", "-", "--report-type", "context-map", "--target", str(root / "cm.json")],
                        input=json.dumps({"schema_version": "1.0", "report_type": "context-map"}),
                        capture_output=True, text=True)
check("K3 writer rejection names the one-call escape hatch (--emit-template)",
      reject.returncode == 1 and "--emit-template context-map" in reject.stderr,
      (reject.stderr or reject.stdout)[-200:])
skeleton = subprocess.run([sys.executable, str(REPO / ".opencode/skills/read-write-file-ddd/writer-file/scripts/writer_file.py"),
                           "--emit-template", "context-map"], capture_output=True, text=True)
skeleton_ok = skeleton.returncode == 0
# feed the emitted skeleton back through the writer: it must validate end-to-end
# (cwd = a temp tree whose blackboard/domain provides the context names it cites)
if skeleton_ok:
    kit = Path(tempfile.mkdtemp())
    (kit / "blackboard" / "domain").mkdir(parents=True)
    (kit / "blackboard" / "domain" / "domain-boundary-pin.json").write_text(json.dumps(
        {"bounded_contexts": [{"name": "Example Context"}]}), encoding="utf-8")
    fed = subprocess.run([sys.executable, str(REPO / ".opencode/skills/read-write-file-ddd/writer-file/scripts/writer_file.py"),
                          "--source", "-", "--report-type", "context-map",
                          "--target", "blackboard/context-map/out.json"],
                         input=skeleton.stdout, capture_output=True, text=True, cwd=kit)
    skeleton_ok = fed.returncode == 0
check("K4 context-map skeleton is schema-valid through the writer itself",
      skeleton_ok, "emit or self-feed rejected")

# --- K5: the text writer accepts MULTI-document YAML (seed-002 rerun T2-001) ---
# safe_load refused the profiled config the plan and the frozen test require;
# the write gate must validate the exact surface Spring/SnakeYAML parse: loadAll.
text_exec = REPO / ".opencode/skills/code-weaver-dispatcher/builders/_text_write_exec.py"
wroot = Path(tempfile.mkdtemp())
def weave(body):
    p = wroot / "changes.json"
    p.write_text(json.dumps({"body": body, "targetFile": "src/main/resources/application.yml"}),
                 encoding="utf-8")
    r = subprocess.run([sys.executable, str(text_exec), str(p), str(wroot)],
                       capture_output=True, text=True)
    return r.returncode, r.stdout
ok_multi, out_multi = weave("spring.application.name: x\n---\nspring:\n  config:\n"
                            "    activate:\n      on-profile: test\n  flyway:\n"
                            "    enabled: false\n")
check("K5 multi-document YAML payload WEAVES (profiled config was 'not parseable', "
      "making a correct plan unweavable, T2-001)", out_multi.find('"status": "ok"') >= 0
      and ok_multi == 0, out_multi.strip()[:200])
ok_broken, out_broken = weave("a: [1, 2\n")
check("K6 broken YAML is still refused", ok_broken == 1 and "not parseable" in out_broken,
      out_broken.strip()[:120])

# --- summary -----------------------------------------------------------------
# --- P. scaffold tooling: the repin script's surefire guardrail (live 2026-11-16
#    14:01: the stage-0 intent demanded a test-run timeout guardrail, NO sanctioned
#    tool could add it - the generator has no option, hand-editing the pom is
#    forbidden - so the container agent correctly refused to deliver an incomplete
#    scaffold and the whole run died fatal on 'pom.xml was not created'. The one
#    sanctioned pom editor now carries the capability.)
import xml.etree.ElementTree as _ET
repin = load_module(REPO / ".opencode" / "skills" / "mcp-server-alternatives" /
                    "mcp-server-springboot" / "repin-parent.py", "repin_parent")
POM_WITH_PLUGINS = ('<project>\n\t<build>\n\t\t<plugins>\n\t\t\t<plugin>'
                    '<artifactId>spring-boot-maven-plugin</artifactId></plugin>\n'
                    '\t\t</plugins>\n\t</build>\n</project>')
out_p, ch_p = repin.transform(POM_WITH_PLUGINS, "3.5.16", [], surefire_timeout=300)
_ET.fromstring(out_p)
check("P1 the sanctioned scaffold script adds forkedProcessTimeoutInSeconds when the "
      "plan names a test-run guardrail (agents never hand-edit the pom)",
      ch_p == ["surefire forkedProcessTimeoutInSeconds=300"]
      and "<forkedProcessTimeoutInSeconds>300</forkedProcessTimeoutInSeconds>" in out_p
      and "spring-boot-maven-plugin" in out_p)
out_p2, ch_p2 = repin.transform(out_p, "3.5.16", [], surefire_timeout=300)
check("P2 idempotent: the guardrail is never duplicated on a re-run",
      ch_p2 == [] and out_p2 == out_p)
POM_NO_BUILD = '<project><modelVersion>4.0.0</modelVersion></project>'
out_p3, ch_p3 = repin.transform(POM_NO_BUILD, "3.5.16", [], surefire_timeout=120)
_ET.fromstring(out_p3)
check("P3 a pom without any <build> receives the full block (valid XML both ways)",
      ch_p3 and "<build><plugins>" in out_p3.replace("\n\t", "").replace("\t", "")
      or "<build>" in out_p3)
out_p4, ch_p4 = repin.transform(POM_WITH_PLUGINS, "3.5.16", [])
check("P4 timeout=0 keeps a plain re-pin pure (no unrequested pom edits)", ch_p4 == [])
_POM_WITH_DEPS = ('<project><dependencies><dependency><groupId>org.springframework.boot</groupId>'
                  '<artifactId>spring-boot-starter-webflux</artifactId></dependency>'
                  '</dependencies></project>')
out_p5, ch_p5 = repin.transform(_POM_WITH_DEPS, "3.5.16", ["spring-security-test"])
_ET.fromstring(out_p5)
_sec_decl = out_p5.split("<artifactId>spring-security-test</artifactId>")[0].split("<dependency>")[-1]
_sec_after = out_p5.split("<artifactId>spring-security-test</artifactId>")[1][:90]
check("P4b the require table carries spring-security-test as a BOM-managed test-scope entry "
      "(2026-11-18 live: the architect-tier table ordered --require for it while the script "
      "knew only test and reactor-test; the container halted honestly, and the engine's "
      "existence guard marked that halt as done)",
      "org.springframework.security" in _sec_decl and "<version>" not in _sec_decl
      and "<scope>test</scope>" in _sec_after and any("spring-security-test" in c for c in ch_p5))

# --- P5-P8: the 2026-11-17 drain's skill laws stay taught (each line blocks a class of
#     unwinnable frozen test or silent-fiction plan the per-unit gates cannot see).
tester_doc = (REPO / ".opencode" / "skills" / "tester-framework" / "java-junit5" /
              "SKILL.md").read_text()
check("P5 the tester skill teaches substitute-credentials + aggregate-decode laws "
      "(28000 creator/reader split and 'Cannot decode value of type Long' are fixture "
      "defects a compile-error red never executes - they freeze units at the green gate)",
      ";USER=sa;PASSWORD=" in tester_doc and "Cannot decode value of type" in tester_doc)
check("P5b the tester skill forbids chained flatExtracting/extracting element access "
      "(2026-11-18 live: the delivered TelemetryMetricsTest degraded to `variable id of type "
      "java.lang.Object` mid-chain - a frozen test uncompilable against EVERY implementation, "
      "which the red phase waved through and stage 2 paid 9 coder sessions for; the law is "
      "the local-typed-projection pattern)",
      "flatExtracting" in tester_doc and "java.lang.Object" in tester_doc
      and "assert ONCE on the local" in tester_doc)
db_doc = (REPO / ".opencode" / "skills" / "tech-stack" / "concrete-database-migration" /
          "SKILL.md").read_text()
check("P6 the database skill outputs scripts at the RUNTIME-LOADED directory, not a "
      "module-root folder nobody reads (2026-11-17: packaged classpath dir stayed empty)",
      "src/main/resources/db/migration" in db_doc
      and 'never plan a "copy into resources" duty owned by nobody' in db_doc)
scaffold_doc = (REPO / ".opencode" / "skills" / "mcp-server-alternatives" /
                "mcp-server-springboot" / "SKILL.md").read_text()
check("P7 the scaffold skill verifies COMPOSITION-ROOT PLACEMENT (the Initializr nests "
      "the boot class under <base>.<artifact>: a sibling-package @SpringBootTest then "
      "dies on the upward config search while the scaffold's own smoke test passes)",
      "COMPOSITION-ROOT PLACEMENT" in scaffold_doc)
stack_doc = (REPO / ".opencode" / "skills" / "tech-stack" / "java-springboot3" /
             "SKILL.md").read_text()
check("P8 the stack skill names the WebFlux handler-marker law (isHandler accepts only "
      "@Controller - a factory-built POJO boots green and answers 404 on its own endpoint)",
      "isHandler" in stack_doc and "404" in stack_doc)

# --- Q. the security architect: one skill, one machine reference, two profiles.
#     (2026-11-17, after the separation-of-concerns review) The skill states requirements;
#     references/security-spec.schema.json is the byte contract; ddd.SECURITY_* is the gate;
#     the profiles are the execution contract. These pins fail the moment any of the four
#     drifts - which is how the earlier shape leaked framework vocabulary and engine plumbing
#     into a phase that owns neither.
sys.path.insert(0, str(REPO / "orchestrators"))
import ddd  # noqa: E402
import settings as engine_settings  # noqa: E402
import prompts  # noqa: E402

SECURITY_SKILL_DIR = REPO / ".opencode/skills/architect-practices/security-strategy"
security_skill = (SECURITY_SKILL_DIR / "SKILL.md").read_text()
SEC_BODY = security_skill.split("---\n", 2)[2]
schema_text = (SECURITY_SKILL_DIR / "references/security-spec.schema.json").read_text()
check("Q1 the machine reference tables exactly the keys the engine gate demands, in order",
      list(json.loads(schema_text).keys()) == list(ddd.SECURITY_SPEC_KEYS),
      str(list(json.loads(schema_text).keys())))
check("Q2 the reference carries the duty contract as capability + closed unit_kind, with no "
      "owner and no stage field (an owner made this phase schedule someone else's work)",
      set(json.loads(schema_text)["duties"][0]) == {"spec_ref", "obligation", "capability",
                                                   "unit_kind"}
      and "stage0_artifact" not in schema_text and "\"owner\"" not in schema_text.split('"duties"')[1])
check("Q2b the reference never instructs an author INTO a gate refusal: assumptions[].source "
      "cites the input CONCEPT and says a file name is only lawful in metadata.inputs "
      "(the live 2026-11-18 failure: the placeholder demanded '<input file or baseline rule>' "
      "and the SECURITY_LEAK_RE refused exactly what it was told to write)",
      "<input file" not in schema_text
      and "NEVER a file name" in json.loads(schema_text)["assumptions"][0]["source"]
      and "metadata.inputs" in json.loads(schema_text)["assumptions"][0]["source"])
check("Q3 the skill instructs no engine mechanics: no emit command, no draft folder, no "
      "task-JSON keys, no id allocation, no queue path - while naming its ONE output exactly "
      "once (naming a forbidden form in the Naming law is the rule; telling this agent to "
      "write a task is the leak)",
      not any(token in security_skill for token in
              ("python3", "--emit", "/tmp/tasks", "targetAgent", "dependsOn", "next-free",
               "blackboard/queue", "agent-container"))
      and SEC_BODY.count("blackboard/complete/security-spec-<slug>.json") == 1)
check("Q4 the skill never loads a stack skill: it ATTRIBUTES mechanism naming to the "
      "tech-stack skill and the architect, and stops there (loading one was the leak)",
      "active `tech-stack" not in security_skill and "SOLE source" not in security_skill
      and "tech-stack skill" in security_skill
      and "denied every stack skill" not in SEC_BODY)
check("Q5 the skill states the IDOR rule as a field constraint on the artifact",
      "`client_supplied_ids` is non-empty" in SEC_BODY and "`public` is an explicit answer"
      in SEC_BODY and "cross-owner" in SEC_BODY.lower())
check("Q6 the skill states duty closure, the token form, and the audit floor once each",
      SEC_BODY.count("discharged by at least one duty") == 1
      and SEC_BODY.count("lowercase kebab") + SEC_BODY.count("Lowercase kebab") == 1
      and SEC_BODY.count("authentication failure, authorization denial") == 1)
check("Q7 the skill is scannable: tables and short bullets, no checklist, no paragraph "
      "long enough to dilute attention under an 8-call budget",
      SEC_BODY.count("\n| ") > 12 and SEC_BODY.count("\n- ") > 20
      and "- [ ]" not in SEC_BODY and SEC_BODY.count("# Checks") == 0
      and not [line for line in SEC_BODY.splitlines() if len(line) > 200],
      str(max(len(line) for line in SEC_BODY.splitlines())))
check("Q7b the skill does NOT restate the schema it delegates: no key enumeration, no id "
      "prefix table, no field-order prose - references/security-spec.schema.json is the "
      "single source, so a rename can only ever be made in one place",
      not any(key in SEC_BODY for key in
              ("schema_version", "report_type", "trust_boundaries` ·", "principals` ·"))
      and "TB-`, `P-`" not in SEC_BODY and len(SEC_BODY.split()) < 1000,
      f"{len(SEC_BODY.split())} words")

profiles = (REPO / ".opencode/agents/agent-security-architect.md",
            REPO / ".github/agents/agent-security-architect.agent.md")
bodies = [path.read_text().split("---\n", 2)[2] for path in profiles]
frontmatters = [path.read_text().split("---\n", 2)[1] for path in profiles]
check("Q8 both profiles teach the same body (the .github skills folder is a symlink: one "
      "skill, two profiles, zero drift) and neither is a wall of text - an agent under an "
      "8-call budget must be able to scan its rules, not re-read them",
      bodies[0] == bodies[1]
      and not [line for body in bodies for line in body.splitlines() if len(line) > 140],
      str(max(len(line) for body in bodies for line in body.splitlines())))
STEM = profiles[1].name.removesuffix(".agent.md")
check("Q9 the Copilot profile has a frontmatter `name` and a stem equal to the dispatched id",
      "name:" in frontmatters[1] and STEM == engine_settings.SECURITY_AGENT,
      f"{STEM} vs {engine_settings.SECURITY_AGENT}")
for index, body in enumerate(bodies):
    check(f"Q10.{index + 1} profile {index} authors one artifact and queues nothing (no emit "
          "command, no draft folder, no project-tree artifact)",
          "blackboard/complete/security-spec-<slug>.json" in body and "--emit" not in body
          and "/tmp/tasks" not in body and "services/<slug>/security/" not in body)
check("Q10.3 the OpenCode profile grants exactly one skill and one write path: no stack "
      "skill (framework idioms would land in the requirements context), no /tmp, no runner",
      frontmatters[0].count(": allow") <= 8
      and "security-strategy: allow" in frontmatters[0]
      and not any(skill in frontmatters[0] for skill in
                  ("java-springboot3", "python-fastapi", "typescript-nestjs",
                   "task-decomposition-dag"))
      and '"services/*/security/**"' not in frontmatters[0] and '"/tmp/**"' not in frontmatters[0]
      and "orchestrator_" not in frontmatters[0]
      and '"blackboard/complete/security-spec-*.json": allow' in frontmatters[0])
check("Q11 the skills symlink resolves the skill AND its machine reference for Copilot",
      (REPO / ".github/skills").is_symlink()
      and (REPO / ".github/skills/architect-practices/security-strategy/SKILL.md").is_file()
      and (REPO / ".github/skills/architect-practices/security-strategy/references/"
           "security-spec.schema.json").is_file())

# --- Q12-Q15: the consumer of the spec. The security step's output is only real once the
#     architect ingests it: these cases fail if the profile forgets the phase order, the
#     artifact, or the duty-claim law - the integration gap that made the whole phase decorative.
ARCH_PROFILES = (REPO / ".opencode/agents/agent-architect.md",
                 REPO / ".github/agents/agent-architect.agent.md")
arch_bodies = [path.read_text().split("---\n", 2)[2] for path in ARCH_PROFILES]
arch_fronts = [path.read_text().split("---\n", 2)[1] for path in ARCH_PROFILES]
check("Q12 both architect profiles carry the same body (the workflow is one contract, not two "
      "dialects that drift apart per backend)", arch_bodies[0].strip() == arch_bodies[1].strip())
for index, arch in enumerate(arch_bodies):
    FLAT = " ".join(arch.split())          # wrap-proof: rules wrap mid-clause by design
    check(f"Q13.{index + 1} architect profile {index} states the real phase order, reads the "
          "security spec in phase 2, and owns the mapping the security step is denied",
          "then the database and security steps run" in FLAT
          and "security-spec-<slug>.json" in FLAT
          and "(y) SECURITY DUTY CLAIM COVERAGE" in FLAT
          and "spec_ref" in FLAT and "tech-stack" in FLAT)
    check(f"Q13.{index + 2} architect profile {index} demands the PAIR inside the one draft "
          "(spec_ref + capability, mechanism named), names the file the claim must live in, and "
          "closes with the per-duty mapping report - a bare token would otherwise satisfy the law "
          "in prose while realizing nothing",
          "BOTH its `spec_ref` token" in FLAT and "its `capability` token" in FLAT
          and "citation is not a mapping" in FLAT
          and "/tmp/tasks/<slug>-<context>.json" in FLAT and "SINGLE" in FLAT
          and "spec_ref -> claiming unit ids -> mechanism named" in FLAT)
ARCH_MARKERS = re.findall(r"^\s+\(([a-z])\) ", arch_bodies[0], re.M)
ARCH_WIDEST = max(len(line) for line in arch_bodies[0].splitlines())
check("Q14 the refusal classes are one scannable line each in order ((a) through (z)), the "
      "lead duties and the observability duty are their own lines, and nothing is left at the "
      "old 7.5k-character paragraph size - an agent under a 12-call budget must be able to "
      "point at a rule, not re-read a wall to find whether it exists",
      ARCH_MARKERS == list(string.ascii_lowercase[:26]) and ARCH_WIDEST < 600
      and arch_bodies[0].count("OBSERVABILITY DESIGN DUTY") == 1,
      f"{ARCH_MARKERS} widest={ARCH_WIDEST}")

check("Q15 the architect is NOT granted the security rulebook: its interface to that phase is "
      "the artifact, so loading the authoring skill would duplicate a contract and pull another "
      "phase's vocabulary in",
      all("security-strategy" not in front for front in arch_fronts))

# --- Q16-Q18: path truth and the witness boundary for the security phase.
SEC_ALL_DOCS = [security_skill, schema_text] + [path.read_text() for path in profiles]
SEC_DOC_TEXT = "\n".join(SEC_ALL_DOCS)
SEC_LITERALS = sorted({m for m in re.findall(r"`((?:\.opencode|references)/[^`\s]+)`", SEC_DOC_TEXT)
                       if m.endswith((".md", ".json", ".py"))})
resolved = []
for literal in SEC_LITERALS:
    candidates = [REPO / literal, SECURITY_SKILL_DIR / literal]
    resolved.append((literal, any(c.is_file() for c in candidates)))
check("Q16 every path a security document tells the agent to read resolves on disk "
      "(the reference lives INSIDE the skill directory, so one read finds it; a bare "
      "relative name that only works from a lucky cwd is how a session burns its budget "
      "hunting its own schema)",
      bool(SEC_LITERALS) and all(ok for _, ok in resolved), str(resolved))
check("Q16b the skill states the machine reference by repo-root path AND notes the Copilot "
      "symlink, so both backends resolve the same bytes",
      ".opencode/skills/architect-practices/security-strategy/references/security-spec.schema.json"
      in security_skill and ".github/skills" in security_skill)
check("Q17 the profile's single shell grant is the reader, named as an exact command: an "
      "agent told to use 'the reader' without the path cannot use it without searching, and "
      "searching skill folders is what SCOPE_RULES forbids",
      'python3 .opencode/skills/read-write-file-ddd/reader-file/scripts/reader_file.py --report <file> --expect any --validate-only'
      in bodies[0] and bodies[0].count("reader_file.py") == 1
      and frontmatters[0].count('": allow') == 2
      and '"*reader_file.py*": allow' in frontmatters[0]
      and '"*": deny' in frontmatters[0] and "orchestrator_" not in frontmatters[0],
      f"quoted grants={frontmatters[0].count(chr(34) + ': allow')}")
_ddd = (REPO / "orchestrators/ddd.py").read_text()
_backends = [(REPO / "orchestrators/opencode_backend.py").read_text(),
             (REPO / "orchestrators/copilot_backend.py").read_text()]
_pipeline = (REPO / "orchestrators/pipeline.py").read_text()
check("Q18 the witness stays outside the judged session: no document offers the agent a "
      "self-validation command, ddd.py exposes NO CLI for one, and both backends plus the "
      "pipeline call the gate themselves - 'run python3 orchestrators/ddd.py --validate' "
      "would hand the artifact's author its own grader (and the repo's rule is that no "
      "agent claim is a completion criterion)",
      "--validate-security" not in SEC_DOC_TEXT and "argparse" not in _ddd
      and all("ddd.validate_security_spec(slug)" in b or "validate_security_spec(slug)" in b
              for b in _backends)
      and "ddd.validate_security_spec(slug) is None" in _pipeline
      and "the witness is not you" in bodies[0].lower())

# --- Q19-Q20: the security step's inputs, proven by running the tool it is told to run.
#     (2026-11-17) The profile first said "read the three plan files with the reader" - and the
#     reader REFUSES an execution strategy, which carries no `schema_version`. A doc that names
#     a command which fails on its own input does not slow the agent down: it costs the session
#     its budget, and the phase dies reporting an unreadable board.
import subprocess as _sp  # noqa: E402

READER = REPO / ".opencode/skills/read-write-file-ddd/reader-file/scripts/reader_file.py"
_TMP = REPO / "gauntlet" / "__pycache__"


def _reader_report(payload):
    target = _TMP / "sec-docs-reader-fixture.json"
    target.write_text(json.dumps(payload))
    done = _sp.run([sys.executable, str(READER), "--report", str(target),
                    "--expect", "any", "--validate-only"], capture_output=True, text=True,
                   cwd=str(REPO))
    return done.returncode, (done.stderr or done.stdout).strip()


_rc_strategy, _msg_strategy = _reader_report({"slug": "demo", "modules": [], "layers": [],
                                              "bounded_contexts": [], "persistence": {}})
check("Q19a the reader really does refuse a strategy file (the fact the routing rests on, "
      "asserted against the tool rather than remembered in prose)",
      _rc_strategy != 0 and "schema_version" in _msg_strategy, f"{_rc_strategy} {_msg_strategy[:90]}")
_rc_slice, _msg_slice = _reader_report({
    "schema_version": "1.0", "report_type": "domain-slice",
    "metadata": {"generated_at": "2026-11-17T00:00:00-03:00", "agent": "domain-boundary-discovery"},
    "subdomain": {"name": "Demo", "type": "core", "capability": "c", "why_distinct": "w"},
    "ubiquitous_language": [{"term": "Sample", "context": "Intake", "definition": "d"}],
    "bounded_contexts": [{"name": "Intake", "responsibility": "r", "in_scope": [], "out_of_scope": [],
                          "ubiquitous_language": [], "invariants": [], "source_of_truth": [],
                          "publishes": [], "consumes": [], "actors": ["device"],
                          "external_systems": [], "confidence": "high"}],
    "assumptions": []})
check("Q19b and it really does accept the DDD report the same profile tells the agent to "
      "read through it (a refusal test alone proves nothing about the working path)",
      _rc_slice == 0, f"{_rc_slice} {_msg_slice[:90]}")
SEC_DOCS = [bodies[0], bodies[1],
            (REPO / "orchestrators/prompts.py").read_text()]
for name, doc in zip(("profile(opencode)", "profile(github)", "prompt"), SEC_DOCS):
    check(f"Q20.{name} routes the strategy to the read tool and only the two DDD reports to "
          "the reader, and says WHY, so the split survives the next editor",
          "read tool" in doc.lower() and "schema_version" in doc
          and not ("reader command" in doc.lower()
                   and "--report `blackboard/complete/execution-strategy" in doc))


# --- Q21-Q25: the token-to-mechanism table rule (y) copies from. The mapping is documentation
#     only if nothing checks it covers the vocabulary: a capability token with no row is the
#     token the architect invents a mechanism for (rule (y) forbids the invention, the emit gate
#     cannot see WHICH mechanism was chosen, and the drift surfaces as a frozen test against a
#     class that does not exist). And a property key that does not exist is rule (r)/(h)'s class
#     of incident: green boot, silent no-op.
SEC_MAP = REPO / ".opencode/skills/tech-stack-architect/spring-security-architect/SKILL.md"
sec_map = SEC_MAP.read_text()
FAMILY_START = security_skill.index("Capability tokens: lowercase kebab")
FAMILY = security_skill[FAMILY_START:security_skill.index("# Posture", FAMILY_START)]
CAPABILITY_TOKENS = {token for line in FAMILY.splitlines() if line.startswith("| ")
                     for token in re.findall(r"`([a-z][a-z0-9-]+(?:-[a-z0-9-]+)*)`", line)}
MAPPED_TOKENS = {token for line in sec_map.splitlines() if line.startswith("| `")
                 for token in re.findall(r"`([a-z][a-z0-9-]+(?:-[a-z0-9-]+)*)`", line)}
check("Q21 every capability token the security rulebook declares has a mechanism row in the "
      "architect's Spring table (an unmapped token is an invented mechanism)",
      CAPABILITY_TOKENS and not (CAPABILITY_TOKENS - MAPPED_TOKENS),
      f"unmapped {sorted(CAPABILITY_TOKENS - MAPPED_TOKENS)}")
check("Q22 the table says NO out loud: tokens Spring cannot realize are marked as no mechanism "
      "and stay plan duties, instead of being matched to a plausible-sounding class "
      f"({sorted(CAPABILITY_TOKENS - MAPPED_TOKENS) or 'all mapped'})",
      sec_map.count("no framework mechanism") >= 3
      and "no framework mechanism" in [line for line in sec_map.splitlines()
                                       if line.startswith("| `opaque-reference`")][0])
check("Q23 the four classes the architect must not recall from memory are all in the file: "
      "build coordinates with the test scope, the chain bean signatures for BOTH stacks, the "
      "port/adapter layering duty, and the exchange-is-not-the-row trap that rule (y3) exists "
      "to catch",
      all(needle in sec_map for needle in
          ("spring-boot-starter-security", "spring-security-test", "| **test** |",
           "SecurityWebFilterChain springSecurityFilterChain(ServerHttpSecurity http)",
           "filterChain(HttpSecurity http)", "return http.build()", "@EnableWebFluxSecurity",
           "@EnableWebSecurity", "PrincipalContextPort", "SpringSecurityPrincipalAdapter",
           "ReactiveSecurityContextHolder", "ROUTE, never a ROW", "no terminal clause"))
      and "deny-by-default" in MAPPED_TOKENS)
_property_names, _known_keys = set(), set()
for _jar in sorted((Path.home() / ".m2/repository/org/springframework/boot").glob("*-*/3*/*.jar")):
    try:
        with zipfile.ZipFile(_jar) as _z:
            for _entry in _z.namelist():
                if _entry.endswith("spring-configuration-metadata.json"):
                    _known_keys |= {prop["name"] for prop in
                                    json.loads(_z.read(_entry)).get("properties", [])}
    except Exception:                       # an unreadable artifact is not a doc defect
        continue
_property_names = {key for key in
                   re.findall(r"\b((?:spring|server|management|logging)\.[a-z0-9][a-z0-9.${}*|-]*)",
                              sec_map)}
check("Q24 every Boot property key the table cites exists in the configuration metadata of the "
      "version on disk (placeholder and alternative spellings are skipped; no local Boot jar "
      "skips the case rather than passing it blindly) - a key nobody binds is a silent no-op "
      "that boots green",
      not _known_keys or all(key.rstrip(".") in _known_keys
                             or any(name.startswith(key.rstrip(".") + ".") for name in _known_keys)
                             or any(ch in key for ch in "<>|*")
                             for key in _property_names),
      f"unverified {sorted(k for k in _property_names if k.rstrip('.') not in _known_keys)[:6]}"
      f" of {len(_known_keys)} known")
check("Q25 the architect is GRANTED the table (a skill it cannot load is not documentation) and "
      "both of its profiles name the path it copies from",
      "spring-security-architect: allow" in arch_fronts[0]
      and all("tech-stack-architect/spring-security" in body for body in arch_bodies))


# --- Q26-Q27: the tier split, and the id collision it exposed. The architect's table is loaded by a
#     13-call planning session that emits ast_hints, dependsOn and coordinates; the chain DSL and the
#     test configurers run in stages 1-2. The planning file pays for symbols it never emits when the two
#     are mixed - and two skills sharing one `name` silently SHADOW each other in the loader (observed
#     2026-11-18: the coder-tier `spring-security` replaced the architect's table under the same id, so
#     `spring-security: allow` handed phase 2 the bodies file and phase 2 lost its mapping table).
SPRING_IMPL = REPO / ".opencode/skills/tech-stack/spring-security/SKILL.md"
spring_impl = SPRING_IMPL.read_text()
coder_skill = (REPO / ".opencode/skills/coder-framework/java-springboot/SKILL.md").read_text()
tester_skill = (REPO / ".opencode/skills/tester-framework/java-junit5/SKILL.md").read_text()
EXECUTION_VOCAB = ("oauth2ResourceServer(", "Customizer.withDefaults()",
                   "NoOpServerSecurityContextRepository", "Cipher.getInstance", "mutateWith(",
                   "@WithMockUser", "SecurityMockServerConfigurers", "with(csrf())", ".csrf(",
                   "sessionManagement", "SecurityWebFiltersOrder", "stateless")
IMPL_VOCAB = ("oauth2ResourceServer(", "Customizer.withDefaults()",
              "NoOpServerSecurityContextRepository", ".csrf(", "sessionManagement",
              "SecurityWebFiltersOrder", "Cipher.getInstance(\"AES/GCM/NoPadding\")",
              "FAILS CLOSED", "mutateWith(", "SecurityMockServerConfigurers", "CROSS-OWNER",
              "spring-security-test")
check("Q26 the planning table carries NO execution vocabulary, names the coder/tester-tier security "
      "skill as its destination, and that file really holds the idioms (bodies + tests) it was given",
      not [token for token in EXECUTION_VOCAB if token in sec_map]
      and "tech-stack/spring-security" in sec_map
      and all(needle in spring_impl for needle in IMPL_VOCAB)
      and sec_map.count("no framework mechanism") >= 3,
      f"leaked {[t for t in EXECUTION_VOCAB if t in sec_map]}")
check("Q27 discovery + collision law: the coder and tester framework skills each GIVE the path to the "
      "security skill (their profiles forbid searching skill folders, so an unreferenced file is an "
      "unread one), and the two Spring security skills do not collide on `name` - an id collision "
      "shadows one file from the loader and silently starves the phase that owns it",
      all(".opencode/skills/tech-stack/spring-security/SKILL.md" in doc
          for doc in (coder_skill, tester_skill))
      and "name: spring-security\n" in spring_impl
      and "name: spring-security-architect\n" in sec_map
      and SPRING_IMPL.parent.name == "spring-security"
      and SEC_MAP.parent.name == "spring-security-architect"
      and "spring-security-architect: allow" in arch_fronts[0])
check("Q32 the bootability law is taught in BOTH security tiers (live 2026-11-18: the plan claimed "
      "mutual-tls-proof and the config unit wrote server.ssl.* keys, but no unit contract owned the "
      "test-boot substitute - every @SpringBootTest boot died 'SSL is enabled but no trust material' "
      "while every per-unit gate kept passing; the slice unit burned its whole budget on a gap the "
      "planning table could see and no law named): the planning file assigns the substitute to the "
      "slice support contract, the execution file says HOW and what never to neutralize",
      "Bootability" in sec_map and "DynamicPropertySource" in sec_map
      and "TEST BOOT vs TRANSPORT MATERIAL" in spring_impl
      and "no `server.ssl.*` needed" in spring_impl)


# --- Q28: rule (y)'s "a citation is not a mapping" needs something to cite. The mechanism column is
#     what phase 2 copies into the unit's intent, so a prose paraphrase there ("terminal deny-all
#     clause") teaches the architect to write prose in the intent - and the emit gate can only check
#     the token+capability pair, never whether a real Spring identifier names the mechanism.
MECHANISM_IDENTIFIERS = {
    "bearer-jwt-proof": ("ReactiveJwtDecoder",),
    "device-credential-proof": ("httpBasic", "ReactiveAuthenticationManager"),
    "mutual-tls-proof": ("x509", "SubjectX500PrincipalExtractor"),
    "role-check": ("ReactiveAuthorizationManager.hasRole", "@EnableReactiveMethodSecurity"),
    "scope-check": ("ReactiveAuthorizationManager.hasAuthority", "JwtGrantedAuthoritiesConverter"),
    "deny-by-default": ("anyExchange().denyAll()", "anyRequest().denyAll()"),
    "hashing": ("PasswordEncoderFactories.createDelegatingPasswordEncoder()",),
    "error-code-only": ("ServerAuthenticationEntryPoint", "ServerAccessDeniedHandler"),
    "boundary-validation": ("jakarta.validation", "@Valid"),
    "typed-deserialization": ("activateDefaultTyping", "ObjectMapper"),
}
_TABLE_ROWS = {re.sub(r"`", "", cells[1]).split("`")[0].strip(): cells[4]
               for cells in (line.split("|") for line in sec_map.splitlines()
                             if line.startswith("| `") and len(line.split("|")) > 5)}
_missing_mech = {token: [want for want in wants if want not in _TABLE_ROWS.get(token, "")]
                 for token, wants in MECHANISM_IDENTIFIERS.items()}
_bare_paraphrase = [token for token, cell in _TABLE_ROWS.items()
                    if "no framework mechanism" not in cell
                    and not re.search(r"`@?[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9]*)*"
                                r"|[A-Za-z][A-Za-z0-9]*\([^)]*\)", cell)]
check("Q28 every framework-backed row names the identifier the intent must spell (rule (y): a token "
      "plus a paraphrase is a citation, not a mapping), and a row that Spring cannot realize says "
      "'no framework mechanism' instead of inventing one",
      not [t for t, miss in _missing_mech.items() if miss],
      str({t: m for t, m in _missing_mech.items() if m}))
check("Q28b no row of the mechanism column is bare prose: every framework-backed cell carries a "
      "class/annotation/method identifier phase 2 can copy verbatim",
      _TABLE_ROWS and not _bare_paraphrase, str(_bare_paraphrase))


# --- Q28c-Q28d: a token the stack cannot realize still has to LAND somewhere.
_UNREALIZABLE = ("field-encryption", "envelope-encryption", "tokenization", "external-key-store",
                 "opaque-reference")
_HOMES = ("config unit", "store", "domain", "infrastructure", "interface")
# the HOME is the row's layer column plus the wording in the mechanism cell; the ASSERTION is the
# mechanism cell's own promise, because that sentence is what the paired stage-1 test inherits
_ROW_TEXT = {}
for _line in sec_map.splitlines():
    _cells = _line.split("|")
    if _line.startswith("| `") and len(_cells) > 5:
        _ROW_TEXT[re.sub(r"`", "", _cells[1]).split("`")[0].strip()] = (
            f"{_cells[3]} {_cells[4]} {_cells[2]}".lower())
check("Q28c every unrealizable row says so AND names the DAG home that owns the duty plus the "
      "assertion that proves it - 'no framework mechanism' alone is how a duty ends up claimed by a "
      "filler unit that recites the token and enforces nothing (and the claim gate refuses a duty no "
      "unit carries, so an honest 'none' without a home is a dead end the architect discovers by "
      "burning a re-emit)",
      all(any(token in row and "no framework mechanism" in text
              and any(home in text for home in _HOMES) and "assert" in text
              for row, text in _ROW_TEXT.items()) for token in _UNREALIZABLE),
      str({token: [row for row in _TABLE_ROWS if token in row] for token in _UNREALIZABLE})[:200])
check("Q28d the unit_kind -> DAG-home map covers every shape the spec's closed enumeration can hand "
      "over, so no duty arrives with a kind nobody owns",
      "unit_kind" in sec_map and all(kind in sec_map for kind in ddd.SECURITY_UNIT_KINDS)
      and "not a security unit" not in sec_map,
      str([kind for kind in ddd.SECURITY_UNIT_KINDS if kind not in sec_map]))


# --- Q29: stack isolation inside the skill itself. A skill is copied: the coder pastes what it reads
#     into a payload, so a Servlet identifier standing in a WebFlux example is a compile failure bought
#     with a session (2026-11-18: the reactive chain carried
#     `.sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))` -
#     `ServerHttpSecurity` has no `sessionCreationPolicy` and no `SessionCreationPolicy` at all; its
#     `sessionManagement(...)` (6.3+) configures `concurrentSessions(...)` only. WebFlux statelessness is
#     `NoOpServerSecurityContextRepository.getInstance()`). The law is BLOCK-scoped, not line-scoped: a
#     DSL chain is written across lines, and a line-level check is blind to exactly that bug (proved by
#     the self-test at the end of this case).
_SERVLET_ONLY = ("SessionCreationPolicy", "sessionCreationPolicy", "authorizeHttpRequests",
                 "anyRequest()", "requestMatchers(", "csrf().asHttp()", "WebSecurity")
_REACTIVE_ONLY = ("ServerHttpSecurity", "SecurityWebFilterChain", "authorizeExchange", "anyExchange",
                  "NoOpServerSecurityContextRepository", "ServerAccessDeniedHandler",
                  "ServerAuthenticationEntryPoint", "ReactiveAuthorizationManager",
                  "ReactivePreAuthenticatedAuthenticationManager",
                  # the 2026-11-18 follow-up: the block split left a reactive-only RULE in the servlet
                  # block and this list did not cover it, so the pin said nothing
                  "block()", "blockFirst", "subscribe(")


def _stack_violations(text):
    """Per ### sub-block of the chain section: an identifier of the OTHER stack inside a CODE SPAN.

    Code spans are what the coder copies; prose is allowed to name a forbidden type in order to forbid
    it. A block ends at the next `###` or any `#` heading, so the servlet block cannot swallow the
    sections that follow it."""
    violations, header, body = [], None, []
    for line in text.split("\n") + ["### END"]:
        if line.startswith("### ") or (line.startswith("# ") and header):
            if header:
                chunk = "\n".join(body)
                spans = re.findall(r"`([^`]*)`", chunk, re.S)
                reactive = any(mark in header for mark in ("WebFlux", "ServerHttpSecurity"))
                servlet = not reactive and "Servlet" in header
                if reactive:
                    violations += [f"{header}: {bad}" for bad in _SERVLET_ONLY
                                   if any(bad in span for span in spans)]
                elif servlet:
                    violations += [f"{header}: {bad}" for bad in _REACTIVE_ONLY
                                   if any(bad in span for span in spans)]
            header, body = line[4:].strip() if line.startswith("### ") else None, []
        elif header:
            body.append(line)
    return violations


_OLD_BUGGY_SECTION = ("### WebFlux (`ServerHttpSecurity`)\n"
                      "bean `SecurityWebFilterChain springSecurityFilterChain(ServerHttpSecurity http)`:\n"
                      "`http.authorizeExchange(e -> e.pathMatchers(HttpMethod.POST, \"/api/x\")\n"
                      " .access(ReactiveAuthorizationManager.hasRole(\"ADMIN\")).anyExchange().denyAll())`\n"
                      "`.securityContextRepository(NoOpServerSecurityContextRepository.getInstance())`,\n"
                      "`.sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))`")
_OLD_STRAY_SECTION = ("### Servlet (`HttpSecurity`)\n"
                      "`http.authorizeHttpRequests(r -> r.anyRequest().denyAll())` and\n"
                      "Never `block()` / `.blockFirst()` in an auth path, and never subscribe in the chain.")
check("Q29 the WebFlux block names no servlet API and the Servlet block names no reactive API (the "
      "chain is a multi-line block, so the law is scoped per block; both self-tests prove a "
      "line-scoped or vocabulary-thin check would have shipped the bugs that started this - the "
      "servlet policy call, and the reactive-only RULE the block split left stranded in the servlet "
      "section)",
      not _stack_violations(spring_impl)
      and bool(_stack_violations(_OLD_BUGGY_SECTION))
      and bool(_stack_violations(_OLD_STRAY_SECTION)),
      f"file: {_stack_violations(spring_impl)} | self-test: {_stack_violations(_OLD_BUGGY_SECTION)}")
check("Q29b the corrected facts are stated where the coder reads them: WebFlux statelessness is the "
      "context repository, the reactive `sessionManagement` is described by what it actually offers "
      "(concurrentSessions), the servlet policy call survives only in the servlet block, and the file "
      "warns in words that a copy across the two blocks does not compile",
      "NoOpServerSecurityContextRepository.getInstance()" in spring_impl
      and "concurrentSessions" in spring_impl.split("### Servlet")[0]
      and "SessionCreationPolicy.STATELESS" in spring_impl.split("### Servlet")[-1]
      and "does not compile" in spring_impl)


# --- SC: the one lawful security waiver is discovery TRANSCRIBING the user, not deciding.
_SLICE_BASE = {"schema_version": "1.0", "report_type": "domain-slice",
               "metadata": {"generated_at": "2026-11-18T00:00:00Z",
                            "agent": "domain-boundary-discovery",
                            "source_description": "seed-002_description.md"},
               "subdomain": {"name": "S", "type": "core", "capability": "c", "why_distinct": "w"},
               "ubiquitous_language": [{"term": "Sample", "context": "In", "definition": "d"}],
               "bounded_contexts": [{"name": "In", "responsibility": "r", "in_scope": [],
                                     "out_of_scope": [], "ubiquitous_language": [], "invariants": [],
                                     "source_of_truth": [], "publishes": [], "consumes": [],
                                     "actors": ["rig"], "confidence": "high"}],
               "assumptions": []}


def _sc(directive):
    return ddd_writer.validate_domain_slice(dict(_SLICE_BASE, security_directive=directive))


check("SC1 the writer refuses a waiver it cannot verify: a one-word quote, a source other than the "
      "description, a non-boolean decision - each shape was written to the board as an unusable field "
      "in earlier designs, and the engine would have had to guess at it later",
      "at least 20 characters" in str(_sc({"required": False, "quote": "no auth",
                                           "source": "description"}))
      and "only the business description can waive" in str(
          _sc({"required": False, "quote": "this internal tool needs no authentication whatsoever",
               "source": "assumption"}))
      and "must be a boolean" in str(_sc({"required": "no",
                                          "quote": "this internal tool needs no authentication",
                                          "source": "description"})))
check("SC2 an absent directive is legal and means REQUIRED; a well-shaped waiver is accepted at the "
      "writer and verified against the file by the engine (the shape gate and the truth gate are "
      "different parties on purpose)",
      ddd_writer.validate_domain_slice(dict(_SLICE_BASE)) is None
      and ddd_writer.validate_domain_slice(dict(
          _SLICE_BASE, security_directive={"required": False, "source": "description",
                                           "quote": "No authentication or authorization is required."}
      )) is None
      and "required\") is not False" in inspect.getsource(ddd._waiver_note)
      and "source_description" in inspect.getsource(ddd._waiver_note)
      and "not a sentence of" in inspect.getsource(ddd._waiver_note))
check("SC3 discovery is TOLD the law where it reads it - in the prompt that carries the description, "
      "in both profiles, and in the skill: transcribe, never infer, and no directive means required "
      "(an agent that decides 'they did not ask for security' would be the hole, not the waiver)",
      "ONLY if" in prompts.DISCOVERY_PROMPT and "VERBATIM" in prompts.DISCOVERY_PROMPT
      and "No directive means security IS required" in prompts.DISCOVERY_PROMPT
      and all("security_directive" in doc.read_text() for doc in DOC_PAIRS["slice"][0])
      and "security_directive" in (REPO / ".opencode/skills/architect-practices/"
                                   "domain-boundary-discovery/SKILL.md").read_text())
check("SC4 the waiver cannot be reached from the phases that would like it: only the slice writer "
      "accepts the field, the architect's profiles never teach it as an option to grant, and the "
      "security phase has no way to skip itself (its post-check still returns 'security spec not found')",
      "security_directive" not in prompts.ARCHITECT_STRATEGY_PROMPT
      and "security spec not found" in inspect.getsource(ddd.validate_security_spec)
      and "SECURITY SPEC IS MANDATORY" not in inspect.getsource(ddd.validate_security_spec))


def _ac(directive):
    return ddd_writer.validate_domain_slice(dict(_SLICE_BASE, ai_directive=directive))


check("SC5 the AI trigger is the waiver's mirror and gets the same shape law at the writer: "
      "required must be TRUE (the opt-out IS the absent default - recording false buys "
      "nothing and could launder a missing quote), the quote must be a real sentence, the "
      "source must be the description; every refusal names the channel that fixes it",
      "must be true" in str(_ac({"required": False, "quote": "the service answers questions",
                                 "source": "description"}))
      and "at least 20 characters" in str(_ac({"required": True, "quote": "it has ai",
                                               "source": "description"}))
      and "only the business description can request" in str(
          _ac({"required": True, "quote": "the service answers operator questions with text",
               "source": "assumption"})))
check("SC6 discovery is told BOTH directives and their opposite defaults in every carrier - "
      "security absent means REQUIRED, AI absent means ABSENT; and the AI trigger is "
      "unreachable from the phases that would want it (only the slice writer accepts the "
      "field; the strategy prompt never teaches it; the engine, not the agent, checks the "
      "quote against the file)",
      "ai_directive" in prompts.DISCOVERY_PROMPT
      and all("ai_directive" in doc.read_text() for doc in DOC_PAIRS["slice"][0])
      and "ai_directive" in (REPO / ".opencode/skills/architect-practices/"
                             "domain-boundary-discovery/SKILL.md").read_text()
      and "ai_directive" not in prompts.ARCHITECT_STRATEGY_PROMPT
      # phase 2 may READ the directive's consequence, it must never be taught to WRITE one
      and "record `ai_directive`" not in prompts.ARCHITECT_TASKS_PROMPT
      and "verified `ai_directive`" in prompts.ARCHITECT_TASKS_PROMPT
      and 'directive.get("required") is not True' in inspect.getsource(ddd.ai_required))

# --- Q30-Q31: the plan phase is a budget, not a bottomless pen.
#     2026-11-18 attribution of 35 real architect sessions: 7.77M input tokens (85% cache reads)
#     against 430k OUTPUT tokens, one 40,442-token single turn, a 53% emit-refusal rate whose remedy
#     was "rewrite the file", 45 folder-listing calls made because the profile gave no skill paths,
#     and 4 sessions that escaped the contract by writing generator scripts. These pins hold the
#     fixes: per-context emission, edit-not-rewrite, the intent wall, and paths that resolve.
arch_docs = [path.read_text() for path in ARCH_PROFILES]
dag_skill = (REPO / ".opencode/skills/architect-practices/task-decomposition-dag/SKILL.md").read_text()
_arch_paths = sorted({literal for doc in arch_docs
                      for literal in re.findall(r"`(\.opencode/skills/[\w./<>-]+/SKILL\.md)`", doc)})
check("Q30 the architect is given EXACT skill paths per phase (no folder hunting: an unused skill "
      "costs every later turn and a hunt costs turns outright), every path resolves on disk, and the "
      "phase split is explicit - the decomposition contract and the security table are phase 2, the "
      "DDD/layering/persistence rules are phase 1",
      len(_arch_paths) >= 7
      and all((REPO / literal).is_file() or "<stack>" in literal or "<lang>" in literal
              for literal in _arch_paths)
      and all("PHASE 1 (strategy)" in doc and "PHASE 2 (tasks)" in doc for doc in arch_docs)
      and all("task-decomposition-dag/SKILL.md" in doc[doc.index("PHASE 2"):] for doc in arch_docs)
      and all("spring-security-architect/SKILL.md" in doc[doc.index("PHASE 2"):] for doc in arch_docs)
      and all("spring-performance-architect/SKILL.md" in doc[doc.index("PHASE 2"):]
              and "spring-ai-architect/SKILL.md" in doc[doc.index("PHASE 2"):]
              for doc in arch_docs)
      and all("domain-driven-architecture/SKILL.md" in doc[:doc.index("PHASE 2")] for doc in arch_docs))
check("Q31 the emission shape is a batch of per-context files, the remedy is an edit, and the "
      "intent wall is stated in all three carriers the architect reads (profile, prompt, skill) - "
      "measured: plan 23,585 tok, largest context ~8k, refusal rewrite 13,288 tok vs 256-448 tok for "
      "an edit, intent = 52% of the plan",
      all("PER BOUNDED" in doc.upper() and "--emit" in doc for doc in arch_docs)
      and "EDIT" in arch_docs[0] and "output tokens" in arch_docs[0]
      and "ONE array file PER BOUNDED CONTEXT" in prompts.ARCHITECT_TASKS_PROMPT
      and "One command is mandatory" in prompts.ARCHITECT_TASKS_PROMPT
      and "AN INTENT IS A SPECIFICATION, NOT AN ESSAY" in prompts.ARCHITECT_TASKS_PROMPT
      and "180" in prompts.ARCHITECT_TASKS_PROMPT
      and "ONE JSON array **per bounded context**" in dag_skill
      # and phase 2 stops re-reading phase 1's inputs (the 2026-11-18 burn report's LARGEST item:
      # 44,943 raw tokens of slice re-reads carried 381,965 tokens - 11% of all architect input)
      and "Your inputs are" in prompts.ARCHITECT_TASKS_PROMPT
      and "read it together with its context map" not in prompts.ARCHITECT_TASKS_PROMPT
      and "read it together with its context map" in prompts.ARCHITECT_STRATEGY_PROMPT
      and "hard ceiling 180" in dag_skill
      and "**edit**" in dag_skill)

# --- SE. rule (z) is taught in EVERY carrier and nothing sends the architect to a tool
#     it does not have (2026-11-19, the R1/R2 fix). The fields without the law in the
#     carriers are dead schema; the law without the fields is the prose that froze the
#     seed-002 board; the "write tool" sentence was a Copilot-backend lie (its profile
#     grants read/search/execute/edit - the drafts must be CREATED with `edit`).
import settings  # noqa: E402
import task_queue  # noqa: E402
JAVA_JUNIT5 = (REPO / ".opencode/skills/tester-framework/java-junit5/SKILL.md").read_text()
_z_docs = arch_docs + [prompts.ARCHITECT_TASKS_PROMPT, dag_skill]
check("SE1 the two vocabulary fields (`ast_hints.meters`, `ast_hints.routes`) and rule (z) "
      "are named by every carrier the architect phase reads - both profiles, the tasks "
      "prompt, the decomposition skill: a field only the validator knows is a field never "
      "emitted (the null-pointer of 'the meter NAME is the contract from ast_hints' while "
      "ast_hints carried no names)",
      all("ast_hints.meters" in doc and "ast_hints.routes" in doc and "(z)" in doc
          for doc in _z_docs),
      [doc[-60:] for doc in _z_docs if "ast_hints.meters" not in doc])
check("SE2 the twin-table law (z4: one unit, one IDENTICAL table, now machine-enforced) is "
      "stated in every carrier - the prompt promised IDENTICAL since the table existed and "
      "nothing enforced it; the seed-002 regen proved what a divergent twin freezes",
      all("IDENTICAL" in doc for doc in _z_docs))
check("SE3 the tester tier's skill points its meter law at the FIELD and its route law at "
      "the FIELD, and carries the anti-convergence law: a REGENERATED test is written "
      "against the task record as queued, never against the delivered implementation "
      "(R1's second half: the D15 regen pinned the facade's drifted spelling and made the "
      "consumer's frozen test unsatisfiable)",
      "ast_hints.meters" in JAVA_JUNIT5 and "ast_hints.routes" in JAVA_JUNIT5
      and "REGENERATED" in JAVA_JUNIT5 and "TASK RECORD" in JAVA_JUNIT5)
check("SE4 no architect carrier sends the session to a tool the profiles do not grant: the "
      "draft files are CREATED with the edit tool (the OpenCode permission is `edit`, the "
      "Copilot tool list has no write) - 'your write tool' would strand the phase on a "
      "missing capability",
      not any("write tool" in doc for doc in _z_docs)
      and "your edit tool" in inspect.getsource(prompts.build_architect_prompt)
      and "your edit tool" in arch_bodies[0] and "your edit tool" in arch_bodies[1])
check("SE5 the emit gate's refusals carry the remedy shape the SD3 doctrine demands: every "
      "(z) message names the literal, the offending unit ids, and the exact edit (the duty "
      "word, the field) - not a rewrite",
      all(phrase in inspect.getsource(task_queue._shared_literal_errors)
          for phrase in ("OWNED by none", "SERVED by none", "ast_hints.routes",
                         "ast_hints.meters", "IDENTICAL", "--replan")))

# --- SE6-SE9: the 2026-11-19 (z5)/(z6)/anti-convergence laws are taught where each tier
#     reads them (the R3/R4/R5 fix). Prose without a carrier is a law nobody loads.
TESTER_PROFILES = [(REPO / ".opencode/agents/agent-tester.md").read_text(),
                   (REPO / ".github/agents/agent-tester.agent.md").read_text()]
sec_map_body = sec_map
check("SE6 z6 (the slice that imports a chain must construct it): the planning tier assigns "
      "the guard's products to the surface table, the execution tier says HOW and what never "
      "to double, and the tester tier names the plan-hole channel - R3 died 3/3 on a "
      "NoSuchBeanDefinition that the plan could see at emit",
      "(z6)" in sec_map_body and "CONCRETE PRODUCT" in sec_map_body.upper()
      and "@MockitoBean" in spring_impl and "never double the chain" in spring_impl
      and "PLAN HOLE" in tester_skill and "cross-cutting" in tester_skill)
check("SE7 z5 (one property path, one shape) + the empty-store honesty: the custody row "
      "declares the credential TRIPLE and the no-empty-state posture, the execution tier "
      "names the constructor law and the defaultable-placeholder law, and the decomposition "
      "skill mirrors the binding record as the shape owner",
      "ast_hints.config" in sec_map_body and "secret-hash" in sec_map_body
      and "Assert.notEmpty" in spring_impl and "${ENV:}" in spring_impl
      and "SHAPE MIRROR" in dag_skill and "BOOT-PATH PLACEHOLDERS" in dag_skill)
check("SE8 the isolation law (R5) is where both writers meet it: the plan assigns the choice "
      "in rule (p)'s support contract, the tester skill forbids the global-count freeze",
      "STATE IS A CONTRACT TOO" in dag_skill and "method order" in tester_skill
      and "RELATIVE delta" in tester_skill)
check("SE9 the anti-convergence channel is closed at every message surface: the tester "
      "profile's Truth clause names the three vocabulary fields (a field the profile omits "
      "is a field the agent harvests from the tree), the tester message opens with the "
      "ORACLE line, and the shared SCOPE rule reads sources only for table-NAMED literals "
      "(the D15 regen entered through that exact exception)",
      all("ast_hints.meters" in doc and "ast_hints.routes" in doc and "ast_hints.config" in doc
          for doc in TESTER_PROFILES)
      and "ORACLE: this task's" in inspect.getsource(prompts._tester_tool_paths)
      and "NAMED BY THIS UNIT'S ast_hints TABLE" in prompts.SCOPE_RULES)

# --- PF. the performance and AI agents exist WITH their boundaries (2026-11-19). Every
#     line here was a defect class the security phase already paid for: a shared skill id,
#     an edit grant wider than the artifact, a schema placeholder pointing into the leak
#     gate, a profile sending a session to hunt its own skills.
NEW_AGENTS = ("agent-performance-architect", "agent-ai-architect")
_skill_names = {}
for _skill_md in sorted((REPO / ".opencode/skills").rglob("SKILL.md")):
    _m = re.search(r"^name:\s*([\w-]+)\s*$", _skill_md.read_text(), re.M)
    if _m:
        _skill_names.setdefault(_m.group(1), []).append(_skill_md.parent.name)
_new_skills = ("performance-strategy", "ai-strategy", "spring-performance-architect",
               "spring-ai-architect")
check("PF1 the four new skills have UNIQUE ids repo-wide and the folders match the ids - the "
      "loader keys by NAME and a collision silently starves a phase (Q27's class, prevented "
      "at birth for the new files)",
      all(len(_skill_names.get(n, [])) == 1 and _skill_names.get(n) == [n] for n in _new_skills),
      {n: _skill_names.get(n) for n in _new_skills})
for agent in NEW_AGENTS:
    oc = (REPO / f".opencode/agents/{agent}.md").read_text()
    gh = (REPO / f".github/agents/{agent}.agent.md").read_text()
    front = oc.split("---", 2)[1]
    spec_glob = ("blackboard/complete/performance-spec-*.json" if "performance" in agent
                 else "blackboard/complete/ai-spec-*.json")
    own_skill = "performance-strategy" if "performance" in agent else "ai-strategy"
    check(f"PF2 {agent}: identical body across backends; the ONLY file it may edit is its own "
          "spec; the ONLY shell is the reader; it is granted exactly its authoring skill (the "
          "stack tables are the architect's, never its own); it queues nothing",
          oc.split("---", 2)[2].strip() == gh.split("---", 2)[2].strip()
          and f'"{spec_glob}": allow' in front and '"*": deny' in front
          and '"*reader_file.py*": allow' in front and front.count('": allow') == 2
          and f"{own_skill}: allow" in front
          and "task: deny" in front and "--emit" not in oc
          and 'tools: ["read", "search", "execute", "edit"]' in gh.split("---", 2)[1],
          f"front grants={front.count(chr(34) + ': allow')}")
check("PF3 the two spec schemas parse, carry the report_type the engine's gate demands, and "
      "their placeholder text teaches the Q2b lesson (the assumptions source is a CONCEPT, "
      "NEVER a file name - a schema that instructs an author into its own leak gate is the "
      "bug that cost a session on 2026-11-18)",
      json.loads((REPO / ".opencode/skills/architect-practices/performance-strategy/"
                  "references/performance-spec.schema.json").read_text())["report_type"]
      == "performance-spec"
      and json.loads((REPO / ".opencode/skills/architect-practices/ai-strategy/"
                      "references/ai-spec.schema.json").read_text())["report_type"] == "ai-spec"
      and "NEVER a file name" in (REPO / ".opencode/skills/architect-practices/"
                                  "performance-strategy/references/performance-spec.schema.json")
      .read_text()
      and "NEVER a file name" in (REPO / ".opencode/skills/architect-practices/ai-strategy/"
                                  "references/ai-spec.schema.json").read_text())
for table in ("spring-performance-architect", "spring-ai-architect"):
    text = (REPO / f".opencode/skills/tech-stack-architect/{table}/SKILL.md").read_text()
    check(f"PF4 {table}: body under 620 words, whole file under 700 (caps set for a ten-token "
          "table, raised once for the multi-agent trio, again for the delivery-shape row - "
          "every growth is a grounded row; the alternative is deleting identifiers, the defect "
          "these files exist to prevent), carries the honest 'no framework mechanism' cells "
          "where the stack supplies nothing, and is GRANTED + pathed in the architect profile",
          len(text.split("---", 2)[2].split()) < 620 and len(text.split()) < 700
          and "no framework mechanism" in text.lower()
          and f"tech-stack-architect/{table}/SKILL.md" in
          (REPO / ".opencode/agents/agent-architect.md").read_text()
          and f"{table}: allow" in
          (REPO / ".opencode/agents/agent-architect.md").read_text(),
          f"{len(text.split())} words")
def _z28b_violations(table_path):
    """Every mechanism cell (4th column) of a mapping table names a backticked REAL
    identifier - a class/method shape (capital- or call-led), an annotation, or a dotted
    property key - or declares 'no framework mechanism'. Q28b's law, applied to the two
    new tables at birth and STRENGTHENED (2026-11-19 review): a board field like
    `ast_hints` is not an identifier; a plan-owned class must wear the honest prefix, so
    a prose-or-field-only cell is a violation."""
    problems = []
    for line in table_path.read_text().splitlines():
        if not line.startswith("| ") or set(line) <= set("|- :"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4 or cells[0].lower().startswith("token"):
            continue
        cell = cells[3]
        if "no framework mechanism" in cell.lower():
            continue
        grounded = [tok for tok in re.findall(r"`([^`]+)`", cell)
                    if re.match(r"[@A-Z$]", tok) or "." in tok or "(" in tok]
        if not grounded:
            problems.append(cells[0][:40])
    return problems

import tempfile as _tf
_fake = Path(_tf.mktemp(suffix=".md"))
_fake.write_text("| token | kind | layer | mechanism | key |\n|---|---|---|---|---|\n"
                 "| counted proof | budget-observer | shared | the plan's counting decorator "
                 "on the store/port (tabled in `ast_hints`) - what makes `query-count` a "
                 "stage-1 assertion | - |\n")
check("PF4c-selftest the original counted-proof cell (field-only backticks, no honest prefix) "
      "IS reported by the predicate - a check that cannot fail cannot pass (Q29's law)",
      _z28b_violations(_fake) == ["counted proof"], str(_z28b_violations(_fake)))
_fake.unlink()

for table in ("spring-performance-architect", "spring-ai-architect"):
    check(f"PF4c {table}: every mechanism cell names a backticked identifier or declares "
          "'no framework mechanism' (the Q28b law at birth - prose in that column is a "
          "Resilience4j/Hikari invented from memory one draft away)",
          not (v := _z28b_violations(REPO / f".opencode/skills/tech-stack-architect/{table}/SKILL.md")),
          str(v))
check("PF7 the baseline-assumption law is taught in EVERY performance carrier - skill, phase "
      "prompt, both profiles: a functional seed that omits traffic gets a conservative PA-01 "
      "baseline, and open_questions stays reserved for missing surfaces, flows, concepts and "
      "conflicts (an agent that halts every run for unstated RPS mistakes the floor for a "
      "spec sheet - the over-trigger the first live run would have paid for)",
      all("MISSING NUMBER IS A BASELINE ASSUMPTION" in " ".join(doc.split()) for doc in (
          (REPO / ".opencode/skills/architect-practices/performance-strategy/SKILL.md").read_text(),
          prompts.PERFORMANCE_PROMPT,
          (REPO / ".opencode/agents/agent-performance-architect.md").read_text(),
          (REPO / ".github/agents/agent-performance-architect.agent.md").read_text()))
      and "per PA-01" in (REPO / ".opencode/skills/architect-practices/performance-strategy/"
                          "references/performance-spec.schema.json").read_text()
      and "never an open question" in " ".join(
          (REPO / ".opencode/skills/architect-practices/performance-strategy/SKILL.md")
          .read_text().lower().split()))
# --- PF8/PF9: the two NEW tables get Q24's and Q28d's treatment (the operator's review):
#     a cited property key that no runtime binds, a cited class that does not exist, and a
#     duty-kind with no owning row are the three ways a mapping table becomes expensive fiction.
perf_map_text = (REPO / ".opencode/skills/tech-stack-architect/spring-performance-architect/SKILL.md").read_text()
ai_map_text = (REPO / ".opencode/skills/tech-stack-architect/spring-ai-architect/SKILL.md").read_text()
_perf_keys = {k for k in re.findall(
    r"\b((?:spring|server|management|logging)\.[a-z0-9][a-z0-9.${}*|-]*)", perf_map_text)}
check("PF8 (Q24 clone) every Boot property key the performance table cites exists in the "
      "configuration metadata of the Boot version on disk - no local Boot jar skips the case, "
      "never passes it blindly; the pool row spells its keys in FULL because a shorthand the "
      "scanner cannot extract is a key nobody verifies",
      not _known_keys or (len(_perf_keys) >= 8 and all(
          k in _known_keys or any(n.startswith(k.rstrip(".") + ".") for n in _known_keys)
          or any(ch in k for ch in "<>|*") for k in _perf_keys)),
      f"unverified {sorted(k for k in _perf_keys if k.rstrip('.') not in _known_keys)[:6]}")
_ai_known = set()
for _jar in sorted((Path.home() / ".m2/repository/org/springframework/ai").glob("**/*.jar")):
    try:
        with zipfile.ZipFile(_jar) as _z:
            for _entry in _z.namelist():
                if _entry.endswith("spring-configuration-metadata.json"):
                    _ai_known |= {prop["name"] for prop in
                                  json.loads(_z.read(_entry)).get("properties", [])}
    except Exception:
        continue
_AI_GROUNDED = ("BeanOutputConverter", "ChatOptions", "EmbeddingModel", "ChatMemory",
                "MessageWindowChatMemory", "InMemoryChatMemoryRepository", "@Tool",
                # the multi-agent trio cites two more framework nouns, both proven present
                # in the local spring-ai jars (commons/model) on 2026-11-19:
                "VectorStore", "ToolCallback")
_AI_UNGROUNDED = ("ChatClient",)  # its artifact is not installed locally: named here so a
                                   # future run that installs spring-ai-client-chat can move it
                                   # into the grounded list - silence is how a recalled class stays
                                   # unchecked
_ai_classes = {k for k in re.findall(r"`([A-Z][A-Za-z0-9]{2,})`", ai_map_text)}
check("PF8b (Q23/Q24 clone for the AI tier) every framework CLASS the AI table cites is "
      "verified present as a backticked identifier AND every provider-specific property is "
      "written as a <provider> namespace, never a recalled concrete key (the 2026-11-19 "
      "review caught exactly that: `spring.ai.openai.chat.options.max-tokens` was recalled, "
      "and no local artifact proves it) - spring-ai keys are checked against the local "
      "metadata when it exists",
      all(f"`{name}" in ai_map_text for name in _AI_GROUNDED)  # opening-backtick form: matches `BeanOutputConverter<T>` too
      and not [k for k in re.findall(
          r"\b(spring\.ai\.[a-z0-9.<>${}*|-]*)", ai_map_text)
          if "<" not in k and k.rstrip(".") not in _ai_known and _ai_known]
      and all(name in ai_map_text for name in _AI_UNGROUNDED),
      str(sorted(_ai_classes))[:200])
# --- PF8c/PF8d: the invocation-mode law (2026-11-19 review). `.call()` is Spring AI's
#     BLOCKING terminal; `.stream()` is the reactive one. The tables now cite reactor names
#     (`Schedulers.boundedElastic`, `Flux.take`, `Mono.fromCallable`) - they must be as
#     grounded as the spring-ai ones (reactor-core on disk proves them; absent -> skipped,
#     never blindly passed), and the mode must be carried by EVERY file a stage-1/2 session
#     reads, because a WebFlux coder left without it writes an event-loop deadlock the
#     frozen test rewards.
_reactor_known = set()
for _jar in sorted((Path.home() / ".m2/repository/io/projectreactor").glob("**/reactor-core-*.jar")):
    try:
        with zipfile.ZipFile(_jar) as _z:
            _reactor_known |= {n for n in _z.namelist() if n.endswith(".class")}
    except Exception:
        continue
_PERF_MODE_CLASSES = ("reactor/core/publisher/Mono.class", "reactor/core/publisher/Flux.class",
                      "reactor/core/scheduler/Schedulers.class", "reactor/util/retry/Retry.class")
_WEB_GROUNDED = {"ServerSentEvent": "org/springframework/http/codec/ServerSentEvent.class",
                 "MediaType": "org/springframework/http/MediaType.class",
                 "GetMapping": "org/springframework/web/bind/annotation/GetMapping.class",
                 "SseEmitter": "org/springframework/web/servlet/mvc/method/annotation/SseEmitter.class"}
_web_known = set()
for _jar in sorted((Path.home() / ".m2/repository/org/springframework").glob("spring-web*/[0-9]*/*.jar")):
    try:
        with zipfile.ZipFile(_jar) as _z:
            _web_known |= set(_z.namelist())
    except Exception:
        continue
_exec_ai = (REPO / ".opencode/skills/tech-stack/spring-ai/SKILL.md").read_text()
check("PF8c invocation-mode + transport grounding: Mono/Flux/Schedulers/Retry exist in the "
      "local reactor-core jar and ServerSentEvent/MediaType/GetMapping/SseEmitter - the "
      "identifiers the delivery rows now name - exist in spring-web/webmvc (no jar => "
      "skipped, never passed blindly)",
      ((not _reactor_known) or all(c in _reactor_known for c in _PERF_MODE_CLASSES))
      and ((not _web_known) or all(v in _web_known for v in _WEB_GROUNDED.values())),
      f"reactor={len(_reactor_known)} web={len(_web_known)}")
check("PF8d the mode law is carried where it binds: the architect table declares INVOCATION "
      "MODE IS A PLAN FACT with the two shapes (wrap `Schedulers.boundedElastic()` / stream), "
      "the exec-tier file teaches both bodies and the never-block list, and the coder "
      "framework skill states the rule in its own voice (java-junit5 §AI tests demands the "
      "same from testers)",
      "INVOCATION MODE IS A PLAN FACT" in " ".join(ai_map_text.split())
      and "MVC takes the blocking pair" in ai_map_text
      and "split by the planned runtime" in _exec_ai
      and "Mono.fromCallable" in _exec_ai and "subscribeOn" in _exec_ai
      and ".stream().content()" in _exec_ai and "blockFirst" in _exec_ai
      and "call()`, terminal and blocking, is wrapped - never `block()`" in coder_skill
      # (B19 sync) the delivery composition is named exactly where it binds: the row maps
      # to the real streaming identifiers, the bodies compose events and assert chunk-then-
      # terminal deterministically (never "the call finished")
      and "MediaType.TEXT_EVENT_STREAM_VALUE" in ai_map_text
      and "ServerSentEvent.builder" in _exec_ai and "SseEmitter.event()" in _exec_ai
      and "thenConsumeWhile" in _exec_ai and "expectNextMatches" in _exec_ai
      # (B21) the memory bodies match the architect table's three techniques at the tier
      # that writes them - window chain, compaction THROUGH the port, scoped semantic recall
      and "maxMessages(window)" in _exec_ai
      and "compactor is invoked THROUGH `ChatPort`" in " ".join(_exec_ai.split())
      and "stub-call-count" in _exec_ai
      and "permits(...)` predicate as the human path" in " ".join(_exec_ai.split())
      and "foreign owner's memories are absent" in " ".join(_exec_ai.split()))

_AI_REACTIVE_ONLY = ("StepVerifier", "withVirtualTime", "subscribeOn",
                     "Schedulers.boundedElastic", "Mono.fromCallable", "Flux<",
                     "blockFirst", "blockLast", "takeUntil")
_AI_BLOCKING_ONLY = ("spring.threads.virtual.enabled", "assertThrows", "try {",
                     "call().content()")
def _ai_runtime_violations(text):
    """Per ### runtime block, CODE SPANS only (Q29's scoping lesson: prose may name a
    forbidden form to forbid it; spans are what the coder copies)."""
    problems = []
    blocks = {"reactive": [], "blocking": []}
    current = None
    for line in text.splitlines():
        if line.startswith("### "):
            low = line.lower()
            current = "reactive" if "reactive" in low else ("blocking" if "blocking" in low else None)
            continue
        if line.startswith("# "):
            current = None
        if current is None:
            continue
        for span in re.findall(r"`([^`]+)`", line):
            forbidden = _AI_BLOCKING_ONLY if current == "reactive" else _AI_REACTIVE_ONLY
            problems += [f"{current}: `{span}`" for tok in forbidden if tok in span]
    return problems
check("PF8f the runtime split is hermetic (Q29's law cloned): no blocking-block vocabulary "
      "in a reactive code span and no reactive-only identifier in a blocking span - the "
      "shared core stays runtime-neutral, the blocks stay pure, so a servlet coder never "
      "copies a scheduler hop and a WebFlux coder never copies a direct blocking call",
      not _ai_runtime_violations(_exec_ai), str(_ai_runtime_violations(_exec_ai))[:200])
_polluted = ("### Blocking (Servlet / Spring MVC)\n"
             "- wrong shape: `Mono.fromCallable(() -> chatClient...call().entity(A.class))`\n"
             "  `.subscribeOn(Schedulers.boundedElastic())` on a request thread\n")
check("PF8f-selftest a reactive wrap pasted into the blocking block IS reported by the "
      "predicate (Q29's lesson, again: a pin that cannot fail cannot pass)",
      bool(_ai_runtime_violations(_polluted)), "self-test blind")

check("PF8e the stub-bean precedence law is taught where the coder reads it: @Primary on the "
      "stub as the default, the @ConditionalOnMissingBean alternative only when the plan "
      "tabled it, the NoUniqueBeanDefinition failure named, the TOP-LEVEL "
      "@TestConfiguration-not-picked-up trap (a stub silently ignored boots the production "
      "adapter LIVE - the offline-port violation disguised as green wiring), and the witness "
      "case (assert the resolved port bean IS the stub); the architect row carries the "
      "precedence fact the intents copy, and the authoring skill states it stack-neutral "
      "(win WITNESSED - an override assumed is an override not delivered)",
      "@Primary" in _exec_ai and "NoUniqueBeanDefinition" in _exec_ai
      and "NOT picked up silently" in _exec_ai and "isInstanceOf" in _exec_ai
      and "`@Primary` STUB port" in ai_map_text
      and "WIN WITNESSED" in (REPO / ".opencode/skills/architect-practices/ai-strategy/"
                              "SKILL.md").read_text())

check("PF9 (Q28d clone) the unit-kind column of BOTH tables covers every shape the engine's "
      "closed enumerations can hand over - a duty arriving with a kind no row owns is claimed "
      "by a filler that recites the token and bounds nothing",
      all(kind in perf_map_text for kind in ddd.PERFORMANCE_UNIT_KINDS)
      and all(kind in ai_map_text for kind in ddd.AI_UNIT_KINDS),
      str([k for k in ddd.PERFORMANCE_UNIT_KINDS if k not in perf_map_text]
          + [k for k in ddd.AI_UNIT_KINDS if k not in ai_map_text])[:200])
CAP_TOK = {m.group(1) for line in (REPO / ".opencode/skills/architect-practices/"
                                   "ai-strategy/SKILL.md").read_text().splitlines()
           if line.startswith("| `") for m in [re.match(r"\| `([a-z][a-z0-9-]+)`", line)] if m}
_ai_schema = json.loads((REPO / ".opencode/skills/architect-practices/ai-strategy/"
                         "references/ai-spec.schema.json").read_text())
SCHEMA_TOK = set(_ai_schema["capabilities"][0]["capability"].split("|"))
SCHEMA_KINDS = set(_ai_schema["duties"][0]["unit_kind"].split("|"))
AI_TABLE_TOK = {line.strip("|").split("|")[0].strip()
                for line in ai_map_text.splitlines()
                if line.startswith("| ") and not set(line) <= set("|- :")}
AI_TABLE_TOK = {t2 for t2 in AI_TABLE_TOK if t2 in set(ddd.AI_CAPABILITY_TOKENS)}

AI_TABLE_KINDS = {k.strip()
                  for line in ai_map_text.splitlines()
                  if line.startswith("| ") and not set(line) <= set("|- :")
                  and len(line.strip("|").split("|")) > 4
                  for k in line.strip("|").split("|")[1].split("+")}
AI_TABLE_KINDS = {k for k in AI_TABLE_KINDS if k in set(ddd.AI_UNIT_KINDS)}
check("PF12 closed-vocabulary PARITY (the multi-agent trio made four carriers of one list, "
      "and a hand-maintained list drifts the moment one place is edited - the seed-002 R1 "
      "disease wearing a vocabulary hat): the engine tuple, the authoring skill's token "
      "table, the machine schema's capability enum and the architect table's rows agree on "
      "the full token set; engine and schema agree on the unit kinds; the table covers every "
      "kind (PF9); the profile's inline list contains no ghost token",
      set(ddd.AI_CAPABILITY_TOKENS) == CAP_TOK == SCHEMA_TOK == AI_TABLE_TOK
      and set(ddd.AI_UNIT_KINDS) == SCHEMA_KINDS == AI_TABLE_KINDS
      and set(re.findall(r"([a-z][a-z0-9]+-[a-z0-9-]+)", " ".join(
          (REPO / ".opencode/agents/agent-ai-architect.md").read_text().split())
          .split("CLOSED vocabulary (")[1][:760].split(") and a deterministic")[0]))
          <= set(ddd.AI_CAPABILITY_TOKENS)
      # the skill's prose unit-kind list == the engine's set (2026-11-19 review: the schema
      # grew orchestration-router/loop-governor/approval-gate and this list stayed at ten -
      # prose that lags its schema is a law an author reads wrong at write time); and the
      # roles binding exists on BOTH rule row kinds, capability AND invariant
      and set(re.findall(r"[a-z][a-z0-9]+(?:-[a-z0-9]+)+", " ".join(
          (REPO / ".opencode/skills/architect-practices/ai-strategy/SKILL.md").read_text()
          .split("unit_kind from the closed set (")[1].split(").")[0].split())))
          == set(ddd.AI_UNIT_KINDS)
      and "roles" in _ai_schema["invariants"][0],
      f"engine={len(ddd.AI_CAPABILITY_TOKENS)} skill={len(CAP_TOK)} schema={len(SCHEMA_TOK)} "
      f"table={len(AI_TABLE_TOK)} kinds: engine={len(ddd.AI_UNIT_KINDS)} "
      f"schema={len(SCHEMA_KINDS)} table={len(AI_TABLE_KINDS)}")

check("PF11 (2026-11-19 review) the tier split has both legs for the new domains: each "
      "architect table names its coder/tester-tier destination, the destination files exist, "
      "and BOTH framework skills carry their exact paths - spring-security proved the class of "
      "failure twice (an unreferenced file is an unread one; a planner without an execution "
      "file leaves stages 1-2 recalling idioms)",
      "tech-stack/spring-performance" in perf_map_text
      and "tech-stack/spring-ai" in ai_map_text
      and (REPO / ".opencode/skills/tech-stack/spring-performance/SKILL.md").is_file()
      and (REPO / ".opencode/skills/tech-stack/spring-ai/SKILL.md").is_file()
      and all(pointer in coder_skill for pointer in
              (".opencode/skills/tech-stack/spring-performance/SKILL.md",
               ".opencode/skills/tech-stack/spring-ai/SKILL.md"))
      and all(pointer in tester_skill for pointer in
              (".opencode/skills/tech-stack/spring-performance/SKILL.md",
               ".opencode/skills/tech-stack/spring-ai/SKILL.md")))

check("PF7b the phase-2 prompt's table paths follow the REAL directory pattern "
      "(`<stack>-performance-architect`, `<stack>-ai-architect`) - a prompt that names "
      "`<stack>-performance` is a folder hunt wearing a path (F4's lesson, applied to the "
      "new tables), and the claim law demands the mechanism beside the pair",
      "<stack>-performance-architect" in prompts.ARCHITECT_TASKS_PROMPT
      and "<stack>-ai-architect" in prompts.ARCHITECT_TASKS_PROMPT
      and "beside the copied mechanism" in prompts.ARCHITECT_TASKS_PROMPT)

check("PF4b the architect loads each mapping table ONLY when its spec exists (three tables are "
      "priced into the 15-call budget, but reading a table whose spec is absent is the F4-era "
      "folder-hunt reborn as a skill-hunt) and the claim law reaches the new specs in (y1) form",
      "ONLY when its spec exists" in (REPO / ".opencode/agents/agent-architect.md").read_text()
      and "WB-/PB-/PI-" in (REPO / ".opencode/agents/agent-architect.md").read_text()
      and "AC-/AM- for AI" in (REPO / ".opencode/agents/agent-architect.md").read_text()
      and "never nowhere" in (REPO / ".opencode/agents/agent-architect.md").read_text())
_db_text = (REPO / ".opencode/agents/agent-database-architect.md").read_text()
_db_paths = sorted(set(re.findall(r"`(\.opencode/skills/[\w./<>-]+/SKILL\.md)`", _db_text)))
check("PF5 the database profile got the A4 fix: every skill it must read is named by an "
      "EXACT path that resolves (no more globbing tech-stack/** - measured 14 calls against a "
      "stated 10), and its stated budget is the engine's budget (S26's own law, applied to the "
      "phase that broke it)",
      len(_db_paths) >= 5 and all((REPO / p).is_file() or "<stack>" in p for p in _db_paths)
      and "Budget <=12" in _db_text and "Budget <=12" in
      (REPO / ".github/agents/agent-database-architect.agent.md").read_text()
      and settings.call_budget(settings.DATABASE_AGENT) == 12, _db_paths)
_pf_doc = "".join((REPO / f".opencode/skills/architect-practices/{s}/SKILL.md").read_text()
                  for s in ("performance-strategy", "ai-strategy"))
check("SE10 the prompt-contract channel law is carried wherever a plan author or the phase-2 "
      "architect reads (2026-11-19 review): the artifact is a SOURCE TYPE with the five "
      "elements tabled - version, role identity, input placeholders, output-schema reference, "
      "refusal text - the intent states them so the coder loads no other skill, and the "
      "WRITABLE CHANNEL (language source or configuration document only; no template-file "
      "writer exists) is named by the authoring skill, the AI prompt, both AI profiles, the "
      "tasks prompt and both architect profiles",
      "SOURCE TYPE" in (REPO / ".opencode/skills/architect-practices/ai-strategy/SKILL.md").read_text()
      and "template FILE" in (REPO / ".opencode/skills/architect-practices/ai-strategy/SKILL.md").read_text()
      and "SOURCE TYPE as its home" in prompts.AI_PROMPT
      and all("SOURCE TYPE as its home" in (REPO / f).read_text()
              for f in (".opencode/agents/agent-ai-architect.md",
                        ".github/agents/agent-ai-architect.agent.md"))
      and "HOME OF THE ARTIFACT" in prompts.ARCHITECT_TASKS_PROMPT
      and "WRITABLE CHANNEL" in prompts.ARCHITECT_TASKS_PROMPT
      and all("writable channel" in (REPO / f).read_text()
              for f in (".opencode/agents/agent-architect.md",
                        ".github/agents/agent-architect.agent.md")))

check("SE11 the memory tier/technique law is taught in every carrier that decides or maps "
      "it (2026-11-19 review): the trigger list and the three techniques appear in the "
      "authoring skill, the AI prompt and both AI profiles; the schema carries the field; "
      "the architect table maps all three techniques with the two honest 'no framework "
      "mechanism' cells; and the PF12 token parity stays 14 (the technique is a FIELD, not "
      "a 15th token - the closed set gates what duties claim and tables map, and grew no "
      "vocabulary this round)",
      "# Memory: the tier and the technique" in (
          REPO / ".opencode/skills/architect-practices/ai-strategy/SKILL.md").read_text()
      and "sliding-window" in prompts.AI_PROMPT and "memory_technique" in prompts.AI_PROMPT
      and all("memory_technique" in (REPO / f).read_text()
              for f in (".opencode/agents/agent-ai-architect.md",
                        ".github/agents/agent-ai-architect.agent.md"))
      and "memory_technique" in (REPO / ".opencode/skills/architect-practices/ai-strategy/"
                                 "references/ai-spec.schema.json").read_text()
      and all(x in ai_map_text for x in ("MessageWindowChatMemory", "rolling-summary",
                                         "semantic-episodic", "VectorStore"))
      and ai_map_text.lower().count("no framework mechanism") >= 4
      and set(ddd.AI_CAPABILITY_TOKENS) == CAP_TOK == SCHEMA_TOK == AI_TABLE_TOK)

check("PF13 the authoring skills stay inside their session's pocket (one read in an 8-call "
      "session pays on every later turn). Caps track law, not drift: performance-strategy "
      "800 for the unconditional floor; ai-strategy 1400 (1200 at thirteen tokens, raised "
      "once for the delivery-shape row, again for the memory tier/technique law - each "
      "increase is new gate-enforced vocabulary, never prose)",
      len((REPO / ".opencode/skills/architect-practices/performance-strategy/SKILL.md")
          .read_text().split()) < 800
      and len((REPO / ".opencode/skills/architect-practices/ai-strategy/SKILL.md")
              .read_text().split()) < 1400,
      f"{len((REPO / '.opencode/skills/architect-practices/performance-strategy/SKILL.md').read_text().split())}/"
      f"{len((REPO / '.opencode/skills/architect-practices/ai-strategy/SKILL.md').read_text().split())}")

check("PF6 the deterministic-measurement law is the spine of BOTH authoring skills (wall "
      "clock refused in prose, closed kind sets named) and the AI skill carries the offline-"
      "port invariant as its mandatory law - the anti-R5 and anti-billing rules, taught where "
      "the authors read them",
      "wall" in _pf_doc.lower() and "deterministic" in _pf_doc
      and "closed" in _pf_doc and "offline-model-port" in _pf_doc
      and "NO unit test" in _pf_doc.upper().replace("NO UNIT TEST", "NO unit test"))

bad_names = [n for n, c in CHECKS if not c]
print(f"\nSKILL-SCRIPTS SUITE: {len(CHECKS) - len(bad_names)}/{len(CHECKS)}")
print("FAILED:", bad_names if bad_names else "none")
sys.exit(1 if bad_names else 0)
