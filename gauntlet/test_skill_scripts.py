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
import json
import subprocess
import sys
import tempfile
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

# --- 2. Runner grammar: every toolchain phrasing -> one normalized field -----

def demands_of(output):
    return runner.parse(output)[5]

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
              [*ddd_writer.SLICE_KEYS, *ddd_writer.SUBDOMAIN_KEYS,
               "term", "definition", "item", "impact_on_boundaries"],
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

# --- summary -----------------------------------------------------------------
bad_names = [n for n, c in CHECKS if not c]
print(f"\nSKILL-SCRIPTS SUITE: {len(CHECKS) - len(bad_names)}/{len(CHECKS)}")
print("FAILED:", bad_names if bad_names else "none")
sys.exit(1 if bad_names else 0)
