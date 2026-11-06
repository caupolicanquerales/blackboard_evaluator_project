"""Stage 4: application assembly (stack-agnostic engine, stack rules in skills).

Every scoped gate in the pipeline proves ONE unit; none of them boots the
application. Unit tests build collaborators directly with `new`/mocks, so a
production class the framework container cannot supply (an unregistered service, a
port without an adapter, a driver without configuration) passes every unit gate and
still cannot start. The scaffold's own smoke test is the only contract that boots the
whole application, and it exists in every stack this factory scaffolds.

The engine only DETECTS that smoke test per stack (the detection rules below) and
re-runs it as a deterministic gate after every assembly session. All framework
vocabulary - failure reading, the ordered fix menu, the editable roots - lives in
one skill per stack: `.opencode/skills/assembly-framework/<language>-<framework>/`.
`assembly.ensure_tasks()` queues ONE stage-4 task per domain (structurally drained
last: the engine walks stages in ascending order). No blackboard artifact:
completion is the green boot itself, evaluated by the orchestrator, never reported
by the agent.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import settings
import task_queue
import tasks
import test_gate
import workspace

SKILL_FAMILY = "assembly-framework"

_STACK_HINTS = {
    "java-springboot": SKILL_FAMILY + "/java-springboot/SKILL.md",
    "typescript-nestjs": SKILL_FAMILY + "/typescript-nestjs/SKILL.md",
    "python-fastapi": SKILL_FAMILY + "/python-fastapi/SKILL.md",
}


def _detect_java(service_root: Path):
    """Spring Boot: @SpringBootTest smoke class + @SpringBootApplication entry."""
    test_root = service_root / "src" / "test" / "java"
    main_root = service_root / "src" / "main" / "java"
    if not (main_root.is_dir() and test_root.is_dir()):
        return None
    smoke = next((f for f in sorted(test_root.rglob("*Test*.java"))
                  if "@SpringBootTest" in f.read_text(encoding="utf-8", errors="ignore")), None)
    entry = next((f for f in sorted(main_root.rglob("*Application.java"))
                  if "@SpringBootApplication" in f.read_text(encoding="utf-8", errors="ignore")),
                 None) if main_root.is_dir() else None
    if smoke is None or entry is None:
        return None
    runner = "./mvnw" if (service_root / "mvnw").is_file() else "mvn"
    return {"stack": "java-springboot", "class": smoke.name[:-5],
            "command": f"{runner} -Dtest={smoke.name[:-5]} test", "entry": entry,
            "test_file": smoke}


def _detect_nestjs(service_root: Path):
    """NestJS: e2e spec compiled by the package's own test:e2e script."""
    manifest = service_root / "package.json"
    entry = service_root / "src" / "main.ts"
    if not manifest.is_file() or not entry.is_file():
        return None
    try:
        package = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    script = next((name for name in (package.get("scripts") or {})
                   if name.startswith("test:e2e") or name == "test-e2e"), None)
    if script is None:
        return None
    test_root = service_root / "test"
    smoke = next((f for f in sorted(test_root.rglob("*.e2e-spec.ts"))), None) \
        if test_root.is_dir() else None
    if smoke is None:
        return None
    return {"stack": "typescript-nestjs", "class": smoke.name,
            "command": f"npm run {script}", "entry": entry, "test_file": smoke}


def _detect_fastapi(service_root: Path):
    """FastAPI: the scaffold smoke test that builds the app object with TestClient."""
    build = (service_root / "pyproject.toml").is_file() or (service_root / "requirements.txt").is_file()
    if not build:
        return None
    entry = next((service_root / c / "main.py" for c in ("app", "src", "backend")
                  if (service_root / c / "main.py").is_file()), None)
    if entry is None:
        return None
    if "FastAPI" not in entry.read_text(encoding="utf-8", errors="ignore"):
        return None
    tests = service_root / "tests"
    smoke = next((f for f in sorted(tests.rglob("test_*.py"))
                  if "TestClient" in f.read_text(encoding="utf-8", errors="ignore")),
                 None) if tests.is_dir() else None
    if smoke is None:
        return None
    rel = smoke.relative_to(service_root).as_posix()
    return {"stack": "python-fastapi", "class": smoke.name,
            "command": f"python3 -m pytest {rel}", "entry": entry, "test_file": smoke}


DETECTORS = (_detect_java, _detect_nestjs, _detect_fastapi)


def detect(service_root: Path):
    """Assembly contract for one domain service, or None when no scaffold smoke test is found."""
    for detect_stack in DETECTORS:
        found = detect_stack(service_root)
        if found:
            found["skill"] = _STACK_HINTS[found["stack"]]
            return found
    return None


def ensure_tasks(report=print):
    """Queue one stage-4 assembly task per domain that has a smoke test. Idempotent."""
    root = workspace.get_project_root()
    services = sorted((root / settings.PROJECTS_SUBDIR).glob("*")) \
        if (root / settings.PROJECTS_SUBDIR).is_dir() else []
    for service in services:
        slug = service.name
        index = task_queue.load_index()
        if any(t.get("project") == slug and t.get("stage") == settings.ASSEMBLY_STAGE
               for t in index.values()):
            continue  # already queued or completed: ids are never re-emitted
        contract = detect(service)
        if contract is None:
            report(f"[asm  ] {slug}: no scaffold smoke test detected; assembly not scheduled")
            continue
        task = {
            "id": task_queue.next_task_id(settings.ASSEMBLY_STAGE),
            "targetAgent": settings.STAGE_AGENTS[settings.ASSEMBLY_STAGE],
            "stage": settings.ASSEMBLY_STAGE,
            # No dependsOn: the engine drains stages in ascending order, so stage 4
            # structurally runs after every stage-3 task of the pass. Empty deps also
            # survive the quarantining of a failed T3, which would dangle a dependency.
            "dependsOn": [],
            "path": str(contract["entry"].relative_to(service)).replace("\\", "/"),
            "kind": settings.STAGE_KINDS[settings.ASSEMBLY_STAGE][0],
            "layer": "root",
            "feature": None,
            "export": contract["entry"].stem,
            "intent": (f"Bounded context {slug}: boot the generated application. The scaffold "
                       f"smoke test {contract['class']} proves the full application wiring "
                       f"resolves: every collaborator the framework must construct at startup "
                       f"(services, adapters for ports, drivers, configuration) exists. Detect "
                       f"the stack and load your assembly skill ({contract['skill']}); its fix "
                       f"menu and editable roots govern everything you change. Assembly gate "
                       f"command (argv-only, run it through run-test-tool, never invent "
                       f"another): {contract['command']}. Edit production sources only; never "
                       f"touch tests, build manifests, migrations, or another domain."),
            "project": slug,
        }
        tmp = Path(tempfile.mkdtemp(prefix="assembly-"))
        p = tmp / tasks.task_file_name(task)
        p.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
        reason = task_queue.emit_tasks([str(p)])
        report(f"[asm  ] {slug}: {'queued ' + task['id'] if not reason else reason}")


def gate(task):
    """(ok, reason): the deterministic stage-4 verification - boot the application, no LLM."""
    service = workspace.project_root_for(task["project"])
    contract = detect(service)
    if contract is None:
        return False, "assembly smoke test vanished from the tree"
    tool_command = [
        sys.executable, str(settings.RUN_TEST_TOOL),
        "--cwd", str(service),
        "--cmd", contract["command"],
        "--timeout", str(settings.TEST_GATE_TIMEOUT),
    ]
    print(f"[asm  ] {task['id']} booting the application ({contract['stack']}): "
          f"{contract['command']}")
    try:
        completed = subprocess.run(
            tool_command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=settings.TEST_GATE_TIMEOUT + 30,
            cwd=str(settings.ROOT),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"assembly gate could not run: {exc}"
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return False, f"assembly gate produced unparseable output: {completed.stdout.strip()[:400]}"
    if not isinstance(result, dict):
        return False, f"assembly gate produced unexpected output: {str(result)[:400]}"
    if result.get("status") == "passed":
        counts = result.get("counts") or {}
        print(f"[asm  ] {task['id']} green ({counts.get('run', '?')} tests passed): "
              "the application boots")
        return True, ""
    detail = test_gate._failure_detail(result) if hasattr(test_gate, "_failure_detail") \
        else json.dumps(result)[:400]
    return False, f"assembly gate: {detail[:900]}"
