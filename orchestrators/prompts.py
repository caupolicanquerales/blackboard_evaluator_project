"""All prompt templates and prompt builders for the pipeline agents.

Backend modules render these messages and hand them to their agent CLI.
The `{runner}` placeholder carries the backend-specific emit command.
"""
import json
import re
from pathlib import Path

import settings
import task_queue
import workspace


def build_discovery_prompt(description_path):
    try:
        content = Path(description_path).read_text(encoding="utf-8")
    except OSError:
        content = ""
    return (
        DISCOVERY_PROMPT.replace("{description}", str(description_path))
        .replace("{domain_dir}", str(settings.DOMAIN_DIR.relative_to(settings.ROOT)))
        .replace("{content}", content)
    )


def build_mapping_prompt():
    return MAPPING_PROMPT.replace(
        "{domain_dir}", str(settings.DOMAIN_DIR.relative_to(settings.ROOT))
    ).replace("{context_map_dir}", str(settings.CONTEXT_MAP_DIR.relative_to(settings.ROOT)))


def build_architect_prompt(project_root, runner, phase="tasks"):
    template = ARCHITECT_STRATEGY_PROMPT if phase == "strategy" else ARCHITECT_TASKS_PROMPT
    return (
        template.replace("{project_root}", str(project_root))
        .replace("{db_ids}", task_queue.stage_task_summary(0))
        .replace("{domain_dir}", str(settings.DOMAIN_DIR.relative_to(settings.ROOT)))
        .replace("{context_map_dir}", str(settings.CONTEXT_MAP_DIR.relative_to(settings.ROOT)))
        .replace("{strategy_dir}", str(settings.COMPLETE_DIR.relative_to(settings.ROOT)))
        .replace("{runner}", runner)
    )


def build_database_prompt(slug, runner):
    return (
        DATABASE_PROMPT.replace("{slug}", slug)
        .replace("{strategy_path}",
                 f"{settings.COMPLETE_DIR.relative_to(settings.ROOT)}/execution-strategy-{slug}.json")
        .replace("{project_root}", str(workspace.get_project_root()))
        .replace("{next_id}", task_queue.next_task_id(0))
        .replace("{scaffold_id}", task_queue.scaffold_task_id(slug))
        .replace("{runner}", runner)
    )


def build_task_message(task, feedback=None):
    """Agent-facing task prompt: instruction line plus the task JSON payload.

    The repository root owns blackboard/: every writer/reader script must use it.
    The project root is where the task `path` resolves (domain source files only).
    """
    instruction = STAGE_INSTRUCTIONS.get(task["stage"], "Complete this blackboard task.")
    message = (
        f"Repository root (blackboard root for all writer/reader scripts): {settings.ROOT}\n"
        f"Project root (task `path` resolves here): {workspace.project_root_for(task['project'])}\n"
        f"{instruction}\n"
        "Resolve `path` against the project root above. Task JSON:\n"
    )
    message += json.dumps({key: task[key] for key in settings.PROMPT_KEYS}, indent=2)
    if task["stage"] == settings.TDD_STAGE:
        t1 = next((d for d in task.get("dependsOn", []) if str(d).startswith("T1-")), None)
        if t1:
            message += (f"\nUnit artifacts: mandatory `blackboard/red-phase/{t1}.json`; "
                        f"`blackboard/ast-context/{t1}.json` if present.")
            message += f"\nUnit brief: {_unit_brief(task, t1)}"
    return append_feedback(message, task, feedback)


def _unit_brief(task, t1_id):
    """Compact facts so the coder does not have to re-explore: red verdict, test imports,
    and how many production sources already exist in the domain."""
    parts = []
    try:
        record = json.loads((settings.RED_PHASE_DIR / f"{t1_id}.json").read_text(encoding="utf-8"))
        parts.append(f"red={record.get('status')}")
        missing = (record.get("missing_symbols") or [])[:6]
        if missing:
            parts.append("missing=" + ",".join(str(m).split(":")[-1].strip() for m in missing))
    except (OSError, ValueError, json.JSONDecodeError):
        parts.append("red=unreadable")
    root = workspace.project_root_for(task["project"])
    t1 = task_queue.load_index().get(t1_id) or {}
    test_path = root / str(t1.get("path", ""))
    try:
        text = test_path.read_text(encoding="utf-8", errors="ignore")
        own_pkg = ".".join(re.search(r"package ([\w.]+);", text).group(1).split(".")[:4])
        imps = sorted({m.split(".")[-1] for m in re.findall(
            r"import (?:static )?([" + re.escape(own_pkg) + r"\w.]*\.[A-Z][\w]*[\w.]*);", text)})
        if imps:
            parts.append("test_imports=" + ",".join(imps[:10]))
    except (OSError, AttributeError):
        pass
    main_root = root / "src" / "main"
    count = len(list(main_root.rglob("*.java"))) if main_root.is_dir() else 0
    parts.append(f"main_sources_present={count}")
    parts.append("write the payload from these facts; read the test file only if a detail is missing")
    return " | ".join(parts)


def build_batch_message(tasks, feedback=None):
    """One coder session producing payloads for several same-domain stage-2 tasks."""
    first = tasks[0]
    instruction = STAGE_INSTRUCTIONS.get(first["stage"], "Complete these blackboard tasks.")
    message = (
        f"Repository root (blackboard root for all writer/reader scripts): {settings.ROOT}\n"
        f"Project root (task `path` resolves here): {workspace.project_root_for(first['project'])}\n"
        f"{instruction}\n"
        f"BATCH MODE: produce and persist a payload for EACH of the {len(tasks)} tasks below "
        "(writer script once per task id, `--task-id <id>`); load the stack and skills once and "
        "reuse them across tasks; do not skip any task.\n\n"
    )
    for task in tasks:
        t1 = next((d for d in task.get("dependsOn", []) if str(d).startswith("T1-")), None)
        block = json.dumps({key: task[key] for key in settings.PROMPT_KEYS}, indent=2)
        extra = ""
        if t1:
            extra = (f"\nUnit artifacts: mandatory `blackboard/red-phase/{t1}.json`"
                     f" | {_unit_brief(task, t1)}")
        message += f"--- task {task['id']} ---\n{block}{extra}\n"
    return append_feedback(message, first, feedback)


def append_feedback(message, task, feedback):
    if not feedback:
        return message
    return message + FEEDBACK_TEMPLATE.format(path=task["path"], log=feedback)


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

ARCHITECT_TASKS_PROMPT = """You are the blackboard architect for this repository. Phase 2 of 2: tasks.
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
2. Select the storage technology from the tech-stack skill. Write the migration and configuration
   scripts yourself, only under {project_root}/services/{slug}/db/migrations/ (absolute path). You own
   the database files of this domain: setup, schema migration, configuration, and backup.
3. Do NOT queue any task. Database work is executed by you in this phase, not by stage 0 agents.
   Never write into blackboard/queue/ or /tmp/tasks/ for the database.

Do not write application code. Finish by reporting the technology and the script paths you wrote.
"""

STAGE_INSTRUCTIONS = {
    0: "Generate the project root and scaffold described by this task.",
    1: "Read this task and create the test at `path`.",
    2: "Read this task and create the implementation at `path`.",
    3: "Read this task, inspect the implementation at `path`, and refactor it.",
}

FEEDBACK_TEMPLATE = """
Previous attempt FAILED verification. Fix the implementation at `{path}` so the build and tests pass.
Do not change unrelated files. Verification output:
```
{log}
```
"""
