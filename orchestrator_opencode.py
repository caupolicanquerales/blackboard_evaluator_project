#!/usr/bin/env python3
"""Blackboard orchestrator (opencode backend) for the evaluator pipeline.

The pipeline runs in four phases over one business description from ``seed/``:

1. ``domain-boundary-discovery-specialist`` writes
   ``blackboard/domain-boundary-draft.json``.
2. ``domain-context-mapping-specialist`` writes
   ``blackboard/domain-boundary-analysis.json``.
3. ``agent-architect`` reads the validated reports, writes the architecture plan
   and queues dependency-ordered tasks.
4. The blackboard workers drain the queue in stage order:

   stage 0 -> agent-container  (generate the project root / scaffold)
   stage 1 -> agent-tester     (read the task and create the test)
   stage 2 -> agent-coder      (read the task and create the implementation)
   stage 3 -> agent-evaluator  (inspect the implementation and refactor it)

Agents never talk to each other: every hand-off is a validated file on disk.
"""
import argparse
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import telemetry

ROOT = Path(__file__).resolve().parent
BLACKBOARD = ROOT / "blackboard"
QUEUE_DIR = BLACKBOARD / "queue"
COMPLETE_DIR = BLACKBOARD / "complete"
ERROR_DIR = BLACKBOARD / "error"
PROJECTS_DIR = ROOT / "projects"
SEED_DIR = ROOT / "seed"
DRAFT_REPORT = BLACKBOARD / "domain-boundary-draft.json"
ANALYSIS_REPORT = BLACKBOARD / "domain-boundary-analysis.json"
PLAN_FILE = COMPLETE_DIR / "architecture-plan.md"
READER_SCRIPT = (
    ROOT
    / ".opencode"
    / "skills"
    / "read-write-file-ddd"
    / "reader-file"
    / "scripts"
    / "reader_file.py"
)
PROJECT_ROOT = ROOT

DISCOVERY_AGENT = "domain-boundary-discovery-specialist"
MAPPING_AGENT = "domain-context-mapping-specialist"
ARCHITECT_AGENT = "agent-architect"
RUNNER_SCRIPT = "orchestrator_opencode.py"

STAGE_AGENTS = {
    0: "agent-container",
    1: "agent-tester",
    2: "agent-coder",
    3: "agent-evaluator",
}
STAGE_KINDS = {
    0: ("bootstrap",),
    1: ("test",),
    2: ("code",),
    3: ("refactor",),
}
STAGE_INSTRUCTIONS = {
    0: "Generate the project root and scaffold described by this task.",
    1: "Read this task and create the test at `path`.",
    2: "Read this task and create the implementation at `path`.",
    3: "Read this task, inspect the implementation at `path`, and refactor it.",
}
ALLOWED_AGENTS = tuple(STAGE_AGENTS.values())
REQUIRES = {0: (), 1: (0,), 2: (1,), 3: (2,)}
REQUIRED_KEYS = (
    "id",
    "targetAgent",
    "stage",
    "dependsOn",
    "path",
    "kind",
    "layer",
    "feature",
    "export",
    "intent",
)
PROMPT_KEYS = ("id", "path", "kind", "layer", "feature", "export", "intent", "dependsOn")
LAYERS = ("root", "domain", "application", "infrastructure", "interface", "shared", "features")
ID_PATTERN = re.compile(r"^T([0-3])-(\d{3})$")

VERIFY_MODES = ("none", "typecheck", "build")

DISCOVERY_PROMPT = """You are the domain boundary discovery specialist for this repository.
Read the business description at {description} and follow your agent instructions.
Write the validated boundary draft to {draft} using the writer script.
Do not write application code.
Finish by confirming the report path.

Business description:
{content}
"""

MAPPING_PROMPT = """You are the domain context mapping specialist for this repository.
Read the validated boundary draft at {draft} with the reader script, build and validate
the DDD context map, and write the final Domain Boundary Analysis to {analysis} using the
writer script with --check-source.
Do not write application code.
Finish by confirming the report path.
"""

ARCHITECT_PROMPT = """You are the blackboard architect for this repository.
The generated project root is {project_root}: every task `path` resolves relative to it.

Read the final Domain Boundary Analysis at {analysis} and the boundary draft at {draft}.
Derive the bounded contexts, modules, and build order from those reports.

Follow these steps exactly:

1. Write the Architecture Plan to {plan}.
   Include the bounded contexts, module/package layout, build order, and the mapping
   from bounded context to units of work.

2. Decompose the plan into blackboard tasks. Every task is a JSON object with exactly
   these keys and no others:
   id, targetAgent, stage, dependsOn, path, kind, layer, feature, export, intent.

   Fixed stage/agent/kind mapping:
   - stage 0 -> agent-container, kind "bootstrap": generate the project root/scaffold.
   - stage 1 -> agent-tester, kind "test": read the task and create the test.
   - stage 2 -> agent-coder, kind "code": read the task and create the implementation.
   - stage 3 -> agent-evaluator, kind "refactor": inspect the implementation and refactor it.

   Field rules:
   - id: "T<stage>-<3 digits>" (for example T0-001, T1-001); the suffix must match stage.
   - dependsOn: ids of earlier tasks. Stage 1 depends on the stage 0 task; stage 2 depends
     on the matching stage 1 task; stage 3 depends on the matching stage 2 task.
   - path: path relative to the project root; the file the agent must create or modify.
   - layer: one of root, domain, application, infrastructure, interface, shared, features.
   - feature: required only when layer is "features"; otherwise null.
   - export: the primary type, class, or symbol name.
   - intent: precise and implementation-ready. State the bounded context, the invariants
     it must protect, and the expected behavior. The tester, coder, and evaluator tasks
     for the same unit must describe the same unit and stay consistent.

   Emit one stage 0 task unless the project root already contains the build scaffold.
   For every unit of work emit a stage 1 test task, a stage 2 code task, and a stage 3
   evaluator task.

3. Write the task JSON files under /tmp/tasks/ and queue the whole batch with one command:
   python3 {runner} --emit /tmp/tasks/T0-001.json /tmp/tasks/T1-001.json ...
   Fix any validation error and re-emit. Never write into blackboard/queue/ directly.

4. Do not create or modify application source files.

5. Finish by listing the queued task ids, stages, and target agents.
"""


def build_discovery_prompt(description_path):
    try:
        content = Path(description_path).read_text(encoding="utf-8")
    except OSError:
        content = ""
    return (
        DISCOVERY_PROMPT.replace("{description}", str(description_path))
        .replace("{draft}", str(DRAFT_REPORT.relative_to(ROOT)))
        .replace("{content}", content)
    )


def build_mapping_prompt():
    return MAPPING_PROMPT.replace(
        "{draft}", str(DRAFT_REPORT.relative_to(ROOT))
    ).replace("{analysis}", str(ANALYSIS_REPORT.relative_to(ROOT)))


def build_architect_prompt(project_root, runner=None):
    return (
        ARCHITECT_PROMPT.replace("{project_root}", str(project_root))
        .replace("{analysis}", str(ANALYSIS_REPORT.relative_to(ROOT)))
        .replace("{draft}", str(DRAFT_REPORT.relative_to(ROOT)))
        .replace("{plan}", str(PLAN_FILE.relative_to(ROOT)))
        .replace("{runner}", runner or RUNNER_SCRIPT)
    )


def get_framework_verification_commands(project_root, mode):
    """Detect the project stack from its config files and return the verification command.

    Returns None when mode is 'none', when no known stack is detected, or when the
    detected stack has no applicable check for the requested mode.
    """
    if mode == "none":
        return None

    if (project_root / "pom.xml").exists():
        return (
            ("mvn", "-q", "-DskipTests", "compile")
            if mode == "typecheck"
            else ("mvn", "-q", "-DskipTests", "package")
        )

    if (project_root / "build.gradle").exists() or (project_root / "build.gradle.kts").exists():
        wrapper = project_root / "gradlew"
        gradle = str(wrapper) if wrapper.exists() else "gradle"
        return (
            (gradle, "compileJava", "-q")
            if mode == "typecheck"
            else (gradle, "build", "-q")
        )

    if (project_root / "pubspec.yaml").exists():
        return ("flutter", "analyze") if mode == "typecheck" else ("flutter", "build", "bundle")

    if (project_root / "angular.json").exists():
        return ("npx", "tsc", "--noEmit") if mode == "typecheck" else ("npx", "ng", "build", "--configuration", "development")

    if (project_root / "package.json").exists():
        if mode == "typecheck":
            if (project_root / "tsconfig.json").exists() or (project_root / "tsconfig.app.json").exists():
                return ("npx", "tsc", "--noEmit")
            return None
        return ("npm", "run", "build")

    if (project_root / "go.mod").exists():
        return ("go", "vet", "./...") if mode == "typecheck" else ("go", "build", "./...")

    if (project_root / "Cargo.toml").exists():
        return ("cargo", "check") if mode == "typecheck" else ("cargo", "build")

    if any((project_root / name).exists() for name in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")):
        return (sys.executable, "-m", "compileall", "-q", ".")

    return None


def resolve_seed(seed_arg):
    if seed_arg:
        path = Path(seed_arg).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        return path.resolve()
    if not SEED_DIR.is_dir():
        return None
    candidates = sorted(SEED_DIR.glob("*_description.md"))
    if not candidates:
        candidates = sorted(SEED_DIR.glob("*.md"))
    return candidates[0].resolve() if candidates else None


def slugify(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-").lower()


def project_name_from_description(description_path):
    try:
        text = Path(description_path).read_text(encoding="utf-8")
    except OSError:
        text = ""
    for line in text.splitlines():
        if line.startswith("# "):
            slug = slugify(line[2:].strip())
            if slug:
                return slug
    stem = Path(description_path).stem
    if stem.endswith("_description"):
        stem = stem[: -len("_description")]
    return slugify(stem) or "app"


def resolve_output_path(output, description_path):
    if output:
        candidate = Path(output).expanduser()
        return candidate if candidate.is_absolute() else (ROOT / candidate)
    return PROJECTS_DIR / project_name_from_description(description_path)


def set_project_root(path):
    global PROJECT_ROOT
    PROJECT_ROOT = Path(path).expanduser().resolve()
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    return PROJECT_ROOT


def get_project_root():
    return PROJECT_ROOT


def task_sort_key(task):
    return (task["stage"], task["path"])


def read_queue():
    entries = []
    for file in QUEUE_DIR.glob("*.json"):
        try:
            task = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            entries.append(((999, file.name), file, None, f"unreadable JSON: {exc}"))
            continue
        if not isinstance(task, dict):
            entries.append(((998, file.name), file, None, "task must be a JSON object"))
            continue
        stage = task.get("stage")
        path = task.get("path")
        if isinstance(stage, int) and isinstance(path, str):
            entries.append((task_sort_key(task), file, task, None))
        else:
            entries.append(((997, file.name), file, task, None))
    entries.sort(key=lambda entry: entry[0])
    return entries


def load_index():
    index = {}
    for folder in (QUEUE_DIR, COMPLETE_DIR):
        for file in folder.glob("*.json"):
            try:
                task = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(task, dict) and isinstance(task.get("id"), str):
                index[task["id"]] = task
    return index


def validate(task, index):
    """Validate one blackboard task against the evaluator pipeline schema."""
    if set(task) != set(REQUIRED_KEYS):
        missing = sorted(set(REQUIRED_KEYS) - set(task))
        extra = sorted(set(task) - set(REQUIRED_KEYS))
        return f"schema mismatch, missing={missing} extra={extra}"
    stage = task["stage"]
    if not isinstance(stage, int) or stage not in STAGE_AGENTS:
        return "stage must be an integer 0-3"
    match = ID_PATTERN.match(str(task["id"]))
    if not match:
        return "id must match ^T[0-3]-\\d{3}$"
    if int(match.group(1)) != stage:
        return "id stage suffix differs from stage"
    if task["targetAgent"] != STAGE_AGENTS[stage]:
        return f"targetAgent must be {STAGE_AGENTS[stage]!r} for stage {stage}"
    if task["kind"] not in STAGE_KINDS[stage]:
        return f"kind must be one of {list(STAGE_KINDS[stage])} for stage {stage}"
    if not isinstance(task["path"], str) or not task["path"].strip():
        return "path must be a non-empty string"
    if not isinstance(task["export"], str) or not task["export"].strip():
        return "export must be a non-empty string"
    if not isinstance(task["intent"], str) or not task["intent"].strip():
        return "intent must be a non-empty string"

    if stage == 0:
        if task["layer"] != "root":
            return "stage 0 layer must be root"
        if task["feature"] is not None:
            return "stage 0 feature must be null"
        if task["dependsOn"]:
            return "stage 0 dependsOn must be empty"
        return None

    if task["layer"] not in LAYERS:
        return f"layer must be one of {list(LAYERS)}"
    has_feature = isinstance(task["feature"], str) and bool(task["feature"])
    if task["layer"] == "features" and not has_feature:
        return "feature required when layer is features"
    if task["layer"] != "features" and has_feature:
        return "feature must be null unless layer is features"
    if not isinstance(task["dependsOn"], list):
        return "dependsOn must be a list"

    for dep in task["dependsOn"]:
        if not isinstance(dep, str) or not ID_PATTERN.match(dep):
            return f"dependsOn id invalid: {dep!r}"
        dep_task = index.get(dep)
        if dep_task is None or not isinstance(dep_task.get("stage"), int) or not isinstance(dep_task.get("path"), str):
            return f"dependsOn {dep} not resolvable in queue or complete"
        if dep_task["stage"] > stage:
            return f"dependsOn {dep} is in a later stage than this task"
        if depends_transitively(dep, task["id"], index):
            return f"dependsOn {dep} creates a dependency cycle"
    return None


def depends_transitively(start, target, index, seen=None):
    """True if `start` (directly or indirectly) depends on `target`."""
    seen = set() if seen is None else seen
    if start == target:
        return True
    if start in seen:
        return False
    seen.add(start)
    node = index.get(start)
    if not node or not isinstance(node.get("dependsOn"), list):
        return False
    return any(depends_transitively(dep, target, index, seen) for dep in node["dependsOn"])


def claimable(task, queued, complete_ids):
    if any(dep not in complete_ids for dep in task["dependsOn"]):
        return False
    queued_stages = {item["stage"] for item in queued}
    return all(stage not in queued_stages for stage in REQUIRES[task["stage"]])


def send_to_error(file, reason, task):
    if task is None:
        try:
            task = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            task = {"raw": file.read_text(encoding="utf-8", errors="replace")}
    payload = dict(task) if isinstance(task, dict) else {"raw": str(task)}
    payload["error"] = reason
    with telemetry.span("blackboard.error", {"file": file.name, "reason": reason, **telemetry.task_attributes(payload)}) as current:
        telemetry.mark_error(current, reason)
        (ERROR_DIR / file.name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        file.unlink()


def _agent_name(command):
    try:
        return command[command.index("--agent") + 1]
    except (ValueError, IndexError):
        return None


def run_agent(command, timeout, cwd):
    with telemetry.span("blackboard.agent", {"agent": _agent_name(command), "timeout": timeout}) as current:
        ok, reason = _run_agent(command, timeout, cwd)
        if not ok:
            telemetry.mark_error(current, reason)
        return ok, reason


def _run_agent(command, timeout, cwd):
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(cwd),
        )
    except OSError as exc:
        return False, f"cannot launch {command[0]}: {exc}"
    timed_out = {"flag": False}

    def kill_on_timeout():
        timed_out["flag"] = True
        process.kill()

    watchdog = threading.Timer(timeout, kill_on_timeout)
    watchdog.start()
    lines = []
    try:
        for line in process.stdout:
            print(f"    | {line.rstrip()}")
            lines.append(line)
        process.wait()
    finally:
        watchdog.cancel()
    if timed_out["flag"]:
        return False, f"agent timed out after {timeout}s"
    if process.returncode != 0:
        tail = "".join(lines).strip()[-1000:]
        return False, f"agent exited {process.returncode}: {tail}"
    return True, ""


def _verify_tail(text, limit=1200):
    return text.strip()[-limit:]


def _run_verification(command, project_root, timeout):
    try:
        process = subprocess.run(
            command,
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"verification could not run: {exc}"
    return process.returncode, process.stdout or ""


def run_verification(project_root, mode, scope, task, timeout):
    command = get_framework_verification_commands(project_root, mode)
    if command is None:
        return True, ""
    with telemetry.span("blackboard.verify", {"file": f"{task['id']}.json", "mode": mode}) as current:
        code, output = _run_verification(command, project_root, timeout)
        if code is None:
            telemetry.mark_error(current, output)
            return False, output
        if code == 0:
            return True, ""
        reason = f"verification failed: {_verify_tail(output)}"
        telemetry.mark_error(current, reason)
        return False, reason


def verify_project(project_root, mode, timeout):
    command = get_framework_verification_commands(project_root, mode)
    if command is None:
        return True, ""
    with telemetry.span("blackboard.verify", {"scope": "project", "mode": mode}) as current:
        code, output = _run_verification(command, project_root, timeout)
        if code is None:
            telemetry.mark_error(current, output)
            return False, output
        if code == 0:
            return True, ""
        reason = f"verification failed: {_verify_tail(output)}"
        telemetry.mark_error(current, reason)
        return False, reason


def validate_report(path, expect):
    """Validate a DDD report with the shared reader script."""
    path = Path(path)
    if not path.is_file():
        return f"report not found: {path}"
    command = [
        sys.executable,
        str(READER_SCRIPT),
        "--report",
        str(path),
        "--expect",
        expect,
        "--validate-only",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        return f"cannot run report validator: {exc}"
    if result.returncode != 0:
        return (result.stdout or "").strip() or f"report validator exited {result.returncode}"
    return None


def invoke_agent(task, auto_approve, timeout):
    instruction = STAGE_INSTRUCTIONS.get(task["stage"], "Complete this blackboard task.")
    message = (
        f"Project root: {get_project_root()}\n"
        f"{instruction}\n"
        "Resolve `path` against the project root above. Task JSON:\n"
    )
    message += json.dumps({key: task[key] for key in PROMPT_KEYS}, indent=2)
    command = ["opencode", "run", "--agent", task["targetAgent"], "--dir", str(ROOT)]
    if auto_approve:
        command.append("--auto")
    command.append(message)
    print(f"[cmd ] opencode run --agent {task['targetAgent']} --dir {ROOT}")
    return run_agent(command, timeout, ROOT)


def run_discovery(args, description_path):
    with telemetry.span("blackboard.discovery", {"description": str(description_path)}) as current:
        message = build_discovery_prompt(description_path)
        command = ["opencode", "run", "--agent", DISCOVERY_AGENT, "--dir", str(ROOT)]
        if not args.no_auto:
            command.append("--auto")
        command.append(message)
        print(f"[cmd ] opencode run --agent {DISCOVERY_AGENT} --dir {ROOT}")
        ok, reason = run_agent(command, args.timeout, ROOT)
        if ok:
            reason = validate_report(DRAFT_REPORT, "discovery")
            ok = reason is None
        if not ok:
            telemetry.mark_error(current, reason)
            return False, reason
        return True, ""


def run_mapping(args):
    with telemetry.span("blackboard.mapping", {"draft": str(DRAFT_REPORT)}) as current:
        message = build_mapping_prompt()
        command = ["opencode", "run", "--agent", MAPPING_AGENT, "--dir", str(ROOT)]
        if not args.no_auto:
            command.append("--auto")
        command.append(message)
        print(f"[cmd ] opencode run --agent {MAPPING_AGENT} --dir {ROOT}")
        ok, reason = run_agent(command, args.timeout, ROOT)
        if ok:
            reason = validate_report(ANALYSIS_REPORT, "final")
            ok = reason is None
        if not ok:
            telemetry.mark_error(current, reason)
            return False, reason
        return True, ""


def run_architect(args):
    with telemetry.span("blackboard.architect", {"analysis": str(ANALYSIS_REPORT)}) as current:
        message = build_architect_prompt(get_project_root())
        command = ["opencode", "run", "--agent", ARCHITECT_AGENT, "--dir", str(ROOT)]
        if not args.no_auto:
            command.append("--auto")
        command.append(message)
        print(f"[cmd ] opencode run --agent {ARCHITECT_AGENT} --dir {ROOT}")
        ok, reason = run_agent(command, args.timeout, ROOT)
        if not ok:
            telemetry.mark_error(current, reason)
        return ok, reason


def emit_tasks(paths):
    index = load_index()
    staged = []
    with telemetry.span("blackboard.emit", {"tasks.requested": len(paths)}) as current:
        for raw in paths:
            source = Path(raw)
            try:
                task = json.loads(source.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                reason = f"{source}: unreadable JSON: {exc}"
                telemetry.mark_error(current, reason)
                return reason
            if not isinstance(task, dict):
                reason = f"{source}: task must be a JSON object"
                telemetry.mark_error(current, reason)
                return reason
            reason = validate(task, index)
            if reason:
                reason = f"{source}: {reason}"
                telemetry.mark_error(current, reason)
                return reason
            if task["id"] in index:
                reason = f"{task['id']}: id already exists in queue or complete"
                telemetry.mark_error(current, reason)
                return reason
            index[task["id"]] = task
            staged.append(task)
        for task in staged:
            destination = QUEUE_DIR / f"{task['id']}.json"
            with telemetry.span("blackboard.queue", {"file": destination.name, **telemetry.task_attributes(task)}):
                destination.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
            print(f"[emit] {task['id']} -> queue/{destination.name}")
        if current is not None:
            current.set_attribute("tasks.emitted", len(staged))
    return None


def run_pass(args):
    processed = 0
    while True:
        entries = read_queue()
        if not entries:
            return processed, []
        dirty = False
        tasks = []
        for _, file, task, reason in entries:
            if reason:
                send_to_error(file, reason, task)
                print(f"[error] {file.name}: {reason}")
                dirty = True
            else:
                tasks.append((file, task))
        if dirty:
            continue
        index = load_index()
        kept = []
        for file, task in tasks:
            reason = validate(task, index)
            if reason:
                send_to_error(file, reason, task)
                print(f"[error] {file.name}: {reason}")
                dirty = True
            else:
                kept.append((file, task))
        if dirty:
            continue
        complete_ids = {file.stem for file in COMPLETE_DIR.glob("*.json")}
        queued = [task for _, task in kept]
        ready = [(file, task) for file, task in kept if claimable(task, queued, complete_ids)]
        if not ready:
            return processed, [task["id"] for _, task in kept]
        file, task = ready[0]
        print(f"[run ] {task['id']} -> {task['targetAgent']} ({task['path']})")
        ok, reason = invoke_agent(task, not args.no_auto, args.timeout)
        if ok and task["stage"] != 0 and not (get_project_root() / task["path"]).exists():
            ok, reason = False, f"agent finished but {task['path']} was not created"
        if ok:
            ok, reason = run_verification(get_project_root(), args.verify, args.verify_scope, task, args.verify_timeout)
        if ok:
            with telemetry.span("blackboard.complete", {"file": file.name, **telemetry.task_attributes(task)}):
                file.replace(COMPLETE_DIR / file.name)
            print(f"[done] {task['id']}")
        else:
            send_to_error(file, reason, task)
            print(f"[fail] {task['id']}: {reason}")
        processed += 1
        if args.limit and processed >= args.limit:
            return processed, []


def main():
    parser = argparse.ArgumentParser(
        description="Blackboard orchestrator (opencode): DDD discovery -> context mapping -> architect -> container/tester/coder/evaluator."
    )
    parser.add_argument("--seed", metavar="FILE", help="business description to analyze (default: first seed/*_description.md)")
    parser.add_argument("--output", metavar="DIR", help="directory where the project is generated (default: projects/<seed title>)")
    parser.add_argument("--force", action="store_true", help="regenerate existing DDD reports")
    parser.add_argument("--watch", action="store_true", help="poll the queue continuously")
    parser.add_argument("--interval", type=int, default=5, help="seconds between polls in watch mode")
    parser.add_argument("--timeout", type=int, default=900, help="seconds before an agent run is aborted")
    parser.add_argument("--verify", choices=VERIFY_MODES, default="typecheck", help="post-task compile/check gate run in the project root")
    parser.add_argument("--verify-scope", choices=("task", "global"), default="task", help="verification scope")
    parser.add_argument("--verify-timeout", type=int, default=300, help="seconds before verification times out")
    parser.add_argument("--limit", type=int, default=0, help="stop after N tasks (0 = no limit)")
    parser.add_argument("--no-auto", action="store_true", help="do not pass --auto to opencode")
    parser.add_argument("--emit", nargs="+", metavar="FILE", help="validate and emit task JSON files to queue, then exit")
    args = parser.parse_args()
    telemetry.init_telemetry()
    for folder in (QUEUE_DIR, COMPLETE_DIR, ERROR_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    if args.emit:
        reason = emit_tasks(args.emit)
        if reason:
            print(f"[emit-error] {reason}")
            return 1
        return 0
    description = resolve_seed(args.seed)
    if description is None or not description.is_file():
        print(f"[fatal] no seed description found in {SEED_DIR} (use --seed FILE)")
        return 2
    print(f"[seed ] {description}")
    project_root = set_project_root(resolve_output_path(args.output, description))
    print(f"[root] generated project: {project_root}")

    if args.force:
        for report in (DRAFT_REPORT, ANALYSIS_REPORT):
            report.unlink(missing_ok=True)

    if validate_report(DRAFT_REPORT, "discovery") is None and not args.force:
        print(f"[skip] discovery report already valid: {DRAFT_REPORT.relative_to(ROOT)}")
    else:
        DRAFT_REPORT.unlink(missing_ok=True)
        ok, reason = run_discovery(args, description)
        if not ok:
            print(f"[fatal] discovery: {reason}")
            return 1
        print("[ddd ] discovery report ready")

    if validate_report(ANALYSIS_REPORT, "final") is None and not args.force:
        print(f"[skip] mapping report already valid: {ANALYSIS_REPORT.relative_to(ROOT)}")
    else:
        ANALYSIS_REPORT.unlink(missing_ok=True)
        ok, reason = run_mapping(args)
        if not ok:
            print(f"[fatal] mapping: {reason}")
            return 1
        print("[ddd ] analysis report ready")

    print("[plan] architect reading the validated reports")
    ok, reason = run_architect(args)
    if not ok:
        print(f"[fatal] architect: {reason}")
        return 1
    print("[plan] architect finished; processing queue")

    try:
        if args.watch:
            while True:
                run_pass(args)
                time.sleep(args.interval)
        processed, blocked = run_pass(args)
    except KeyboardInterrupt:
        return 130
    if blocked:
        print(f"[blocked] {', '.join(blocked)}")
        return 1
    if args.verify != "none":
        ok, reason = verify_project(get_project_root(), args.verify, args.verify_timeout)
        if not ok:
            print(f"[fatal] {reason}")
            return 1
        print(f"[verify] project passes {args.verify}")
    print(f"[ok] processed {processed} task(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
