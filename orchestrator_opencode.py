#!/usr/bin/env python3
"""Blackboard orchestrator (opencode backend) for the evaluator pipeline.

The pipeline runs in these phases over one business description from ``seed/``:

1. ``domain-boundary-discovery-specialist`` writes one small file per subdomain
   to ``blackboard/domain/domain-boundary-<slug>.json``.
2. ``domain-context-mapping-specialist`` reads those files and writes one
   context map per slice to ``blackboard/context-map/context-map-<slug>.json``.
3. ``agent-architect`` (strategy phase) writes one execution strategy per domain to
   ``blackboard/complete/execution-strategy-<slug>.json``.
4. ``agent-database-architect`` runs once per strategy and queues stage 0 database
   tasks (``T0-###``) through ``--emit``.
5. ``agent-architect`` (tasks phase) queues the application tasks (stage 1..3) and
   lists the database ids in ``dependsOn`` where a unit uses the store.
6. The blackboard workers drain the queue in stage order:

   stage 0 -> agent-container  (generate the project root / scaffold, database setup)
   stage 1 -> agent-tester     (read the task and create the test)
   stage 2 -> agent-coder      (read the task and create the implementation)
   stage 3 -> agent-evaluator  (inspect the implementation and refactor it)

Agents never talk to each other: every hand-off is a validated file on disk.
"""
import argparse
import heapq
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
DOMAIN_DIR = BLACKBOARD / "domain"
CONTEXT_MAP_DIR = BLACKBOARD / "context-map"
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
DATABASE_AGENT = "agent-database-architect"
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
    "project",
)
PROMPT_KEYS = ("id", "path", "kind", "layer", "feature", "export", "intent", "dependsOn", "project")
PROJECTS_SUBDIR = "services"
LAYERS = ("root", "domain", "application", "infrastructure", "interface", "shared", "features")
ID_PATTERN = re.compile(r"^T([0-3])-(\d{3})$")

VERIFY_MODES = ("none", "typecheck", "build")
MAX_TDD_RETRIES = 3
TDD_STAGE = 2

FEEDBACK_TEMPLATE = """
Previous attempt FAILED verification. Fix the implementation at `{path}` so the build and tests pass.
Do not change unrelated files. Verification output:
```
{log}
```
"""

DISCOVERY_PROMPT = """You are the domain boundary discovery specialist for this repository.
Read the business description at {description} and follow your agent instructions.
Write one domain boundary file per subdomain into {domain_dir}.
Do not write application code.
Finish by confirming the report path.

Business description:
{content}
"""

MAPPING_PROMPT = """You are the domain context mapping specialist for this repository.
Read every domain boundary file matching {domain_dir}/domain-boundary-*.json. For each one,
build and validate its context map and write it to {context_map_dir}/context-map-<slug>.json
using the writer script. One context map per slice; never copy subdomain definitions.
Do not write application code.
Finish by confirming the report paths.
"""

ARCHITECT_STRATEGY_PROMPT = """You are the blackboard architect for this repository. Phase 1 of 2: strategy only.
The generated project root is {project_root}.

For every slice `{domain_dir}/domain-boundary-<slug>.json`, read it together with its context map
`{context_map_dir}/context-map-<slug>.json`.

Once per domain:
1. Write the execution strategy to {strategy_dir}/execution-strategy-<slug>.json with the edit tool.
   Include the bounded contexts, module/package layout, build order, risks, and a `persistence`
   object when the context owns data. Use only the slice and its own context map.

2. Emit exactly one separate project scaffold task for THIS domain. Each domain is its own project,
   rooted at {project_root}/services/<slug>/. Fields:
   id (the next free T0 id), targetAgent "agent-container", stage 0, dependsOn [],
   kind "bootstrap", layer "root", feature null, export "project_scaffold",
   project "<slug>", path "<build marker>" relative to the domain root ("pom.xml" or "package.json"
   chosen from the stack), intent "Generate the <slug> project root and build scaffold using the matching
   mcp-server-alternatives skill". Write it to /tmp/tasks/T0-<slug>.json and queue it with:
   python3 {runner} --emit /tmp/tasks/T0-<slug>.json

Do not create other task files and do not write application code in this phase.
Finish by listing the strategy file paths and the scaffold task id of each domain.
"""

ARCHITECT_PROMPT = """You are the blackboard architect for this repository. Phase 2 of 2: tasks.
Each domain is a separate project under {project_root}/services/<slug>/. Every task `path` resolves
relative to the root of its own project (the task `project` field).
Database tasks already queued (stage 0; list them in dependsOn when a unit uses the store):
{db_ids}

Process each domain separately. For every slice `{domain_dir}/domain-boundary-<slug>.json`,
read it together with its context map `{context_map_dir}/context-map-<slug>.json`.

Follow these steps exactly, once per domain:

1. The execution strategy for this domain was written in phase 1 at
   {strategy_dir}/execution-strategy-<slug>.json. Read it; do not rewrite it.

2. Decompose the plan into blackboard tasks. Every task is a JSON object with exactly
   these keys and no others:
   id, targetAgent, stage, dependsOn, path, kind, layer, feature, export, intent, project.

   Fixed stage/agent/kind mapping:
   - stage 0 -> agent-container, kind "bootstrap": generate the project root/scaffold.
   - stage 1 -> agent-tester, kind "test": read the task and create the test.
   - stage 2 -> agent-coder, kind "code": read the task and create the implementation.
   - stage 3 -> agent-evaluator, kind "refactor": inspect the implementation and refactor it.

   Field rules:
   - id: "T<stage>-<3 digits>" (for example T0-001, T1-001); the suffix must match stage.
     Numbers are unique across all domains; continue the sequence, never reuse an id.
   - dependsOn: ids of earlier tasks. Stage 1 depends on the stage 0 scaffold of the same project; stage 2 depends
     on the matching stage 1 task; stage 3 depends on the matching stage 2 task.
   - project: the domain slug <slug>; every task of this domain uses the same project.
   - path: path relative to that domain's project root; the file the agent must create or modify.
   - layer: one of root, domain, application, infrastructure, interface, shared, features.
   - feature: required only when layer is "features"; otherwise null.
   - export: the primary type, class, or symbol name.
   - intent: precise and implementation-ready. State the bounded context, the invariants
     it must protect, and the expected behavior. The tester, coder, and evaluator tasks
     for the same unit must describe the same unit and stay consistent.

   Do not emit stage 0 tasks; the scaffold and database tasks are already queued. Units that use a store
   list the matching database ids from the list above in `dependsOn`.
   For every unit of work emit a stage 1 test task, a stage 2 code task, and a stage 3
   evaluator task.

3. Write the task JSON files under /tmp/tasks/ and queue the whole batch with one command:
   python3 {runner} --emit /tmp/tasks/T0-001.json /tmp/tasks/T1-001.json ...
   Fix any validation error and re-emit. Never write into blackboard/queue/ directly.

4. Do not create or modify application source files.

5. Finish by listing the queued task ids, stages, and target agents.
"""


DATABASE_PROMPT = """You are the blackboard database architect for this repository.
Run your workflow for the bounded context slug `{slug}` only. Its project root is {project_root}/services/{slug}/.

1. Read the strategy file {strategy_path} with the read tool and use only its `persistence` object.
2. Select the storage technology from the tech-stack skill. Write migration scripts only under
   {project_root}/services/{slug}/db/migrations/ (absolute path). Task `path` values are relative to the
   project root of this domain and must be written as db/migrations/<file>.
3. Write one draft per database concern (store setup, schema migration, configuration, backup) to
   /tmp/tasks/{slug}-<n>.json with exactly these keys and no others:
   id, targetAgent, stage, dependsOn, path, kind, layer, feature, export, intent, project.
   Fixed values: targetAgent "agent-container", stage 0, kind "bootstrap", layer "root", feature null,
   project "{slug}".
   dependsOn: ["{scaffold_id}"] (the scaffold task of this domain; every database task waits for it).
   id: start at {next_id} and increase the number by one per draft.
   path: the migration or config file under db/migrations/. export: the artifact name.
   intent: store, technology and version, script path, and the bounded context {slug}.
4. Queue the batch with one command: python3 {runner} --emit <each draft path>
   Fix any validation error and re-emit. Never write into blackboard/queue/ directly.

Do not write application code. Finish by reporting the technology, script paths, and queued task ids.
"""


def database_slugs():
    """Slugs of every execution strategy the architect wrote, in stable order."""
    return sorted(
        file.stem.removeprefix("execution-strategy-")
        for file in COMPLETE_DIR.glob("execution-strategy-*.json")
    )


def next_task_id(stage):
    """Next free id for a stage, from queue and complete (ids are never reused)."""
    numbers = []
    for task_id in load_index():
        match = ID_PATTERN.match(task_id)
        if match and int(match.group(1)) == stage:
            numbers.append(int(match.group(2)))
    return f"T{stage}-{(max(numbers) + 1 if numbers else 1):03d}"


def scaffold_task_id(slug):
    """Id of the stage 0 scaffold task of one domain project (agent-container, kind bootstrap, no dependencies).

    Database tasks of the domain depend on it, so they cannot run before the domain project exists.
    """
    for task_id, task in sorted(load_index().items()):
        if ID_PATTERN.match(task_id) and task_id.startswith("T0-") and task.get("kind") == "bootstrap" and not task.get("dependsOn") and task.get("project") == slug and "migrations" not in Path(str(task.get("path", ""))).parts:
            return task_id
    return "T0-000"


def stage_task_summary(stage):
    lines = []
    for task_id, task in sorted(load_index().items()):
        match = ID_PATTERN.match(task_id)
        if match and int(match.group(1)) == stage:
            lines.append(f"- {task_id}: {task.get('path')} ({task.get('intent')})")
    return "\n".join(lines) or "- none"


def build_database_prompt(slug, runner=None):
    return (
        DATABASE_PROMPT.replace("{slug}", slug)
        .replace("{strategy_path}", f"{COMPLETE_DIR.relative_to(ROOT)}/execution-strategy-{slug}.json")
        .replace("{project_root}", str(get_project_root()))
        .replace("{next_id}", next_task_id(0))
        .replace("{scaffold_id}", scaffold_task_id(slug))
        .replace("{runner}", runner or RUNNER_SCRIPT)
    )


def build_discovery_prompt(description_path):
    try:
        content = Path(description_path).read_text(encoding="utf-8")
    except OSError:
        content = ""
    return (
        DISCOVERY_PROMPT.replace("{description}", str(description_path))
        .replace("{domain_dir}", str(DOMAIN_DIR.relative_to(ROOT)))
        .replace("{content}", content)
    )


def build_mapping_prompt():
    return MAPPING_PROMPT.replace(
        "{domain_dir}", str(DOMAIN_DIR.relative_to(ROOT))
    ).replace("{context_map_dir}", str(CONTEXT_MAP_DIR.relative_to(ROOT)))


def build_architect_prompt(project_root, runner=None, phase="tasks"):
    template = ARCHITECT_STRATEGY_PROMPT if phase == "strategy" else ARCHITECT_PROMPT
    return (
        template.replace("{project_root}", str(project_root))
        .replace("{db_ids}", stage_task_summary(0))
        .replace("{domain_dir}", str(DOMAIN_DIR.relative_to(ROOT)))
        .replace("{context_map_dir}", str(CONTEXT_MAP_DIR.relative_to(ROOT)))
        .replace("{strategy_dir}", str(COMPLETE_DIR.relative_to(ROOT)))
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
    # Only records the path; the folder is created when a task actually runs.
    global PROJECT_ROOT
    PROJECT_ROOT = Path(path).expanduser().resolve()
    return PROJECT_ROOT


def get_project_root():
    return PROJECT_ROOT


def project_root_for(project):
    """Root folder of one domain project: <generated root>/services/<project>."""
    return get_project_root() / PROJECTS_SUBDIR / project


def task_sort_key(task):
    return (task["stage"], task["project"], task["path"])


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


def complete_task_ids():
    """IDs read from the content of completed files (names are T-###-<domain>.json)."""
    ids = set()
    for file in COMPLETE_DIR.glob("*.json"):
        try:
            task = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(task, dict) and isinstance(task.get("id"), str):
            ids.add(task["id"])
    return ids


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
    if not isinstance(task["project"], str) or not task["project"].strip() or task["project"] != slugify(task["project"]):
        return "project must be a domain slug"

    if stage == 0:
        if task["layer"] != "root":
            return "stage 0 layer must be root"
        if task["feature"] is not None:
            return "stage 0 feature must be null"
        if task["dependsOn"] and "migrations" not in Path(str(task["path"])).parts:
            return "stage 0 dependsOn must be empty except for database tasks"
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


def append_feedback(message, task, feedback):
    if not feedback:
        return message
    return message + FEEDBACK_TEMPLATE.format(path=task["path"], log=feedback)


def invoke_agent(task, auto_approve, timeout, feedback=None):
    instruction = STAGE_INSTRUCTIONS.get(task["stage"], "Complete this blackboard task.")
    message = (
        f"Repository root: {ROOT}\n"
        f"Project root: {project_root_for(task['project'])}\n"
        f"{instruction}\n"
        "Resolve `path` against the project root above. Task JSON:\n"
    )
    message += json.dumps({key: task[key] for key in PROMPT_KEYS}, indent=2)
    message = append_feedback(message, task, feedback)
    command = ["opencode", "run", "--agent", task["targetAgent"], "--dir", str(ROOT)]
    if auto_approve:
        command.append("--auto")
    command.append(message)
    print(f"[cmd ] opencode run --agent {task['targetAgent']} --dir {ROOT}")
    return run_agent(command, timeout, ROOT)


def validate_domain_files():
    """Gate for the per-domain discovery files in blackboard/domain/.

    Returns None when at least one file exists and every file parses as a JSON object.
    Otherwise returns the reason string.
    """
    if not DOMAIN_DIR.is_dir():
        return f"discovery did not create {DOMAIN_DIR.relative_to(ROOT)}/"
    files = sorted(DOMAIN_DIR.glob("domain-boundary-*.json"))
    if not files:
        return f"no domain-boundary-*.json files in {DOMAIN_DIR.relative_to(ROOT)}/"
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return f"{path.name} is not valid JSON: {exc}"
        if not isinstance(payload, dict):
            return f"{path.name} must be a JSON object"
    return None


def validate_context_maps():
    """Gate for the per-domain context maps in blackboard/context-map/.

    Every slice in blackboard/domain/ needs a valid context-map-<slug>.json.
    Returns None when all are valid, otherwise the reason string.
    """
    reason = validate_domain_files()
    if reason:
        return reason
    for domain_file in sorted(DOMAIN_DIR.glob("domain-boundary-*.json")):
        slug = domain_file.stem.removeprefix("domain-boundary-")
        map_file = CONTEXT_MAP_DIR / f"context-map-{slug}.json"
        reason = validate_report(map_file, "any")
        if reason:
            return f"{map_file.relative_to(ROOT)}: {reason}"
    return None


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
            reason = validate_domain_files()
            ok = reason is None
        if not ok:
            telemetry.mark_error(current, reason)
            return False, reason
        return True, ""


def run_mapping(args):
    with telemetry.span("blackboard.mapping", {"domain_dir": str(DOMAIN_DIR)}) as current:
        message = build_mapping_prompt()
        command = ["opencode", "run", "--agent", MAPPING_AGENT, "--dir", str(ROOT)]
        if not args.no_auto:
            command.append("--auto")
        command.append(message)
        print(f"[cmd ] opencode run --agent {MAPPING_AGENT} --dir {ROOT}")
        ok, reason = run_agent(command, args.timeout, ROOT)
        if ok:
            reason = validate_context_maps()
            ok = reason is None
        if not ok:
            telemetry.mark_error(current, reason)
            return False, reason
        return True, ""


def run_architect(args, phase="tasks"):
    """Run the architect in phase 'strategy' (writes execution strategies) or 'tasks' (queues tasks)."""
    with telemetry.span("blackboard.architect", {"context_maps": str(CONTEXT_MAP_DIR), "phase": phase}) as current:
        message = build_architect_prompt(get_project_root(), phase=phase)
        command = ["opencode", "run", "--agent", ARCHITECT_AGENT, "--dir", str(ROOT)]
        if not args.no_auto:
            command.append("--auto")
        command.append(message)
        print(f"[cmd ] opencode run --agent {ARCHITECT_AGENT} --dir {ROOT} ({phase})")
        ok, reason = run_agent(command, args.timeout, ROOT)
        if ok and phase == "strategy" and not database_slugs():
            ok, reason = False, "no execution strategy was written"
        if ok and phase == "tasks" and not any(
            (match := ID_PATTERN.match(task_id)) and int(match.group(1)) >= 1 for task_id in load_index()
        ):
            ok, reason = False, "architect queued no application tasks"
        if not ok:
            telemetry.mark_error(current, reason)
        return ok, reason


def run_database(args, slug):
    """Run the database architect for one context. Returns (ok, reason).

    A stop reported by the agent (for example, application tasks already queued)
    exits cleanly and is reported to the caller as a normal result.
    """
    with telemetry.span("blackboard.database", {"slug": slug}) as current:
        message = build_database_prompt(slug)
        command = ["opencode", "run", "--agent", DATABASE_AGENT, "--dir", str(ROOT)]
        if not args.no_auto:
            command.append("--auto")
        command.append(message)
        print(f"[cmd ] opencode run --agent {DATABASE_AGENT} --dir {ROOT}")
        ok, reason = run_agent(command, args.timeout, ROOT)
        if not ok:
            telemetry.mark_error(current, reason)
        return ok, reason


def task_file_name(task):
    """File name for a queued task: <id>-<domain>.json."""
    return f"{task['id']}-{task['project']}.json"


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
            destination = QUEUE_DIR / task_file_name(task)
            with telemetry.span("blackboard.queue", {"file": destination.name, **telemetry.task_attributes(task)}):
                destination.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
            print(f"[emit] {task['id']} -> queue/{destination.name}")
        if current is not None:
            current.set_attribute("tasks.emitted", len(staged))
    return None


def execute_with_tdd(task, invoke, verify):
    """Run one task. Stage 2 retries the coder with the verification log, up to MAX_TDD_RETRIES.

    invoke(feedback) -> (ok, reason): runs the agent and checks its output exists.
    verify() -> (ok, reason): runs the build/test gate.
    Agent failures are not retried; only verification failures are.
    """
    attempts = MAX_TDD_RETRIES if task["stage"] == TDD_STAGE else 1
    feedback = None
    reason = ""
    for attempt in range(1, attempts + 1):
        ok, reason = invoke(feedback)
        if not ok:
            return False, reason
        ok, reason = verify()
        if ok:
            return True, ""
        if attempt < attempts:
            print(f"[tdd ] {task['id']} verification failed (attempt {attempt}/{attempts}); retrying coder with log")
        feedback = reason
    if attempts > 1:
        reason = f"TDD failed after {attempts} attempts: {reason}"
    return False, reason


def load_valid_tasks():
    """Read the queue and quarantine bad files until the remaining set is stable."""
    while True:
        entries = read_queue()
        if not entries:
            return [], complete_task_ids()
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
        return kept, complete_task_ids()


def quarantine_dependents(failed_id, tasks, files, dependents, remaining):
    """Send every transitive dependent of a failed task to the error queue."""
    pending = [failed_id]
    while pending:
        source = pending.pop()
        for dependent_id in dependents.get(source, []):
            if dependent_id not in remaining:
                continue
            dependent_task = tasks[dependent_id]
            if dependent_task["stage"] == 0:
                continue
            file = files[dependent_id]
            reason = f"dependsOn {source} not resolvable in queue or complete"
            send_to_error(file, reason, dependent_task)
            print(f"[error] {file.name}: {reason}")
            remaining.discard(dependent_id)
            pending.append(dependent_id)


def drain_queue(args, invoke_for_task):
    """Drain the queue once using an in-memory dependency graph and ready heap.

    The queue and completion folders are scanned once per pass. Tasks that become
    ready after a completion are pushed onto a heap ordered by (stage, project, path),
    keeping work grouped by domain within each stage.

    ``invoke_for_task(task, feedback)`` runs the backend-specific agent call.
    """
    kept, complete_ids = load_valid_tasks()
    if not kept:
        return 0, []

    tasks = {task["id"]: task for _, task in kept}
    files = {task["id"]: file for file, task in kept}
    by_stage = {}
    for _, task in kept:
        by_stage.setdefault(task["stage"], []).append(task["id"])

    pending_deps = {}
    dependents = {}
    for task_id, task in tasks.items():
        unmet = [dep for dep in task["dependsOn"] if dep not in complete_ids]
        pending_deps[task_id] = len(unmet)
        for dep in unmet:
            dependents.setdefault(dep, []).append(task_id)

    processed = 0
    remaining = set(tasks)
    for stage in sorted(by_stage):
        ready = []
        for task_id in by_stage[stage]:
            if task_id in remaining and pending_deps[task_id] == 0:
                heapq.heappush(ready, (task_sort_key(tasks[task_id]), task_id))
        while ready:
            _, task_id = heapq.heappop(ready)
            if task_id not in remaining or pending_deps[task_id] != 0:
                continue
            file = files[task_id]
            task = tasks[task_id]
            print(f"[run ] {task['id']} -> {task['targetAgent']} ({task['path']})")

            def invoke(feedback):
                ok, reason = invoke_for_task(task, feedback)
                if ok and not (project_root_for(task["project"]) / task["path"]).exists():
                    return False, f"agent finished but {task['path']} was not created"
                return ok, reason

            def verify():
                return run_verification(project_root_for(task["project"]), args.verify, args.verify_scope, task, args.verify_timeout)

            ok, reason = execute_with_tdd(task, invoke, verify)
            if ok:
                with telemetry.span("blackboard.complete", {"file": file.name, **telemetry.task_attributes(task)}):
                    file.replace(COMPLETE_DIR / file.name)
                print(f"[done] {task['id']}")
                complete_ids.add(task_id)
                remaining.discard(task_id)
                for dependent_id in dependents.get(task_id, []):
                    if dependent_id not in remaining:
                        continue
                    pending_deps[dependent_id] -= 1
                    if pending_deps[dependent_id] == 0 and tasks[dependent_id]["stage"] == stage:
                        heapq.heappush(ready, (task_sort_key(tasks[dependent_id]), dependent_id))
            else:
                send_to_error(file, reason, task)
                print(f"[fail] {task['id']}: {reason}")
                remaining.discard(task_id)
                quarantine_dependents(task_id, tasks, files, dependents, remaining)
            processed += 1
            if args.limit and processed >= args.limit:
                return processed, []
        if any(task_id in remaining for task_id in by_stage[stage]):
            blocked = sorted(remaining, key=lambda item: task_sort_key(tasks[item]))
            return processed, blocked
    if remaining:
        blocked = sorted(remaining, key=lambda item: task_sort_key(tasks[item]))
        return processed, blocked
    return processed, []


def run_pass(args):
    def invoke_for_task(task, feedback):
        return invoke_agent(task, not args.no_auto, args.timeout, feedback)
    return drain_queue(args, invoke_for_task)


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
        for map_file in CONTEXT_MAP_DIR.glob("context-map-*.json"):
            map_file.unlink(missing_ok=True)
        for domain_file in DOMAIN_DIR.glob("domain-boundary-*.json"):
            domain_file.unlink(missing_ok=True)

    if validate_domain_files() is None and not args.force:
        print(f"[skip] discovery files already valid: {DOMAIN_DIR.relative_to(ROOT)}/")
    else:
        for domain_file in DOMAIN_DIR.glob("domain-boundary-*.json"):
            domain_file.unlink(missing_ok=True)
        ok, reason = run_discovery(args, description)
        if not ok:
            print(f"[fatal] discovery: {reason}")
            return 1
        print("[ddd ] discovery files ready")

    if validate_context_maps() is None and not args.force:
        print(f"[skip] context maps already valid: {CONTEXT_MAP_DIR.relative_to(ROOT)}/")
    else:
        for map_file in CONTEXT_MAP_DIR.glob("context-map-*.json"):
            map_file.unlink(missing_ok=True)
        ok, reason = run_mapping(args)
        if not ok:
            print(f"[fatal] mapping: {reason}")
            return 1
        print("[ddd ] context maps ready")

    print("[plan] architect writing execution strategies")
    ok, reason = run_architect(args, "strategy")
    if not ok:
        print(f"[fatal] architect strategy: {reason}")
        return 1
    for slug in database_slugs():
        if scaffold_task_id(slug) == "T0-000":
            print(f"[fatal] architect strategy: no scaffold task for domain {slug}")
            return 1
    for slug in database_slugs():
        ok, reason = run_database(args, slug)
        print(f"[db  ] {slug}: {'done' if ok else 'failed: ' + reason}")
        if not ok:
            print(f"[fatal] database {slug}: {reason}")
            return 1
    print("[plan] architect writing application tasks")
    ok, reason = run_architect(args, "tasks")
    if not ok:
        print(f"[fatal] architect tasks: {reason}")
        return 1
    print("[plan] strategy, database, and task phases finished; processing queue")

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
        for slug in database_slugs():
            ok, reason = verify_project(project_root_for(slug), args.verify, args.verify_timeout)
            if not ok:
                print(f"[fatal] {slug}: {reason}")
                return 1
            print(f"[verify] {slug} passes {args.verify}")
    print(f"[ok] processed {processed} task(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
