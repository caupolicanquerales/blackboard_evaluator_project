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
        + _discipline(settings.DISCOVERY_AGENT,
                      "One read of the description, one of the skill, then one write per subdomain.")
    )


def build_mapping_prompt():
    return (MAPPING_PROMPT.replace(
        "{domain_dir}", str(settings.DOMAIN_DIR.relative_to(settings.ROOT))
    ).replace("{context_map_dir}", str(settings.CONTEXT_MAP_DIR.relative_to(settings.ROOT)))
        + _discipline(settings.MAPPING_AGENT,
                      "Read the slices directory once (never file by file), then one map file per slice.")
    )


def build_architect_prompt(project_root, runner, phase="tasks"):
    template = ARCHITECT_STRATEGY_PROMPT if phase == "strategy" else ARCHITECT_TASKS_PROMPT
    draft_rule = ("DRAFT AS ONE FILE: write a single JSON document (an array with every task object of "
                  "the domain) and call `--emit` once. One create call per task file is forbidden: each "
                  "extra call is another turn, and every turn re-sends the whole transcript."
                  if phase == "tasks" else
                  "One strategy file per domain, one scaffold draft, one `--emit`.")
    return (
        template.replace("{project_root}", str(project_root))
        .replace("{db_ids}", task_queue.stage_task_summary(0))
        .replace("{domain_dir}", str(settings.DOMAIN_DIR.relative_to(settings.ROOT)))
        .replace("{context_map_dir}", str(settings.CONTEXT_MAP_DIR.relative_to(settings.ROOT)))
        .replace("{strategy_dir}", str(settings.COMPLETE_DIR.relative_to(settings.ROOT)))
        .replace("{runner}", runner)
        + _discipline(settings.ARCHITECT_AGENT, extra=draft_rule)
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
        + _discipline(settings.DATABASE_AGENT,
                      "Read the strategy and the two tech-stack skills once, write the migration and "
                      "configuration files, then one array draft file and one `--emit`.")
    )


def _coder_contract(task_ids):
    """The only accepted coder output, spelled out with absolute paths.

    A batch session that improvises its own draft folder produces nothing the
    orchestrator can read (the weaver looks only at blackboard/coder-changes), so the
    whole session is paid for and thrown away. The command below is what lands.
    """
    ids = ", ".join(task_ids)
    return (
        "\nOUTPUT CONTRACT: for each task id below, run exactly once, from the repository root:\n"
        f"  python3 {settings.CODER_WRITER} --root {settings.ROOT} --task-id <id> "
        "--input <draft.json>\n"
        "The accepted result is blackboard/coder-changes/<id>.json; a draft written anywhere "
        f"else (including any agent scratch or session folder) is invisible to the orchestrator. "
        f"Task ids of this session: {ids}. Run the writer for every one of them before finishing.\n"
        "WEAVER SHAPE (do not go read the weaver to discover it): `kind` is class|interface|enum|"
        "record|exception. For a record, `members` may mix components (`Type name`) and body members "
        "(compact constructor, factories, extra methods): the weaver routes the bare ones to the header "
        "and the rest to the record body. Framework annotations go in `annotations` (type level) and "
        "`methodAnnotations` (method level), without the `@`, never inside `signature`; parameter "
        "annotations stay inside `signature`, which the weaver preserves. Keep the shape "
        "the `intent` asks for; never downgrade a record to a class to dodge a rejection. If a payload "
        "is rejected, the writer or weaver message names the field to fix: change that payload field "
        "and re-emit with `--retry`."
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
        message += _coder_contract([task["id"]])
    message += _discipline(task["targetAgent"])
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
    if first["stage"] == settings.TDD_STAGE:
        message += _coder_contract([task["id"] for task in tasks])
    shared = (f"The budget is shared by all {len(tasks)} units of this session. Detect the stack and "
              "load the skills ONCE and reuse them: reading a skill or a manifest again per task is the "
              "single most expensive mistake here.")
    message += _discipline(first["targetAgent"], units=len(tasks), extra=shared)
    return append_feedback(message, first, feedback)


def append_feedback(message, task, feedback):
    """Retry instructions, told in the language of the role that has to act on them.

    A stage-2 coder must not "fix the implementation at path": it has no business editing source.
    It re-emits its payload, and the writer only accepts that with --retry.
    """
    if not feedback:
        return message
    template = FEEDBACK_TEMPLATE_CODER if task["stage"] == settings.TDD_STAGE else FEEDBACK_TEMPLATE
    return message + template.format(path=task["path"], id=task["id"], log=feedback)


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

3. Write ONE file /tmp/tasks/<slug>-tasks.json holding a JSON ARRAY of all the task objects of
   this domain, then queue the whole batch with a single command:
   python3 {runner} --emit /tmp/tasks/<slug>-tasks.json
   Fix any validation error by editing that one file and re-emit. Never write into
   blackboard/queue/ directly, and never one draft file per task.

4. Do not create or modify application source files.

5. Finish by listing the queued task ids, stages, and target agents.
"""

DATABASE_PROMPT = """You are the blackboard database architect for this repository.
Run your workflow for the bounded context slug `{slug}` only. Its project root is {project_root}/services/{slug}/.

1. Read the strategy file {strategy_path} with the read tool and use only its `persistence` object.
2. Select the storage technology from the tech-stack skill. Write the migration and configuration
   scripts yourself, only under {project_root}/services/{slug}/db/migrations/ (absolute path). You own
   the database files of this domain: setup, schema migration, configuration, and backup.
3. Queue one stage 0 bootstrap task per database concern (store setup, schema migration, configuration
   profile, backup/recovery). Write ONE array file /tmp/tasks/{slug}-db-tasks.json holding every task
   object, with exactly the keys of your output contract, ids starting at {next_id}, each with dependsOn
   ["{scaffold_id}"] and path db/migrations/<file> relative to the domain project root, then queue them
   with: `python3 {runner} --emit /tmp/tasks/{slug}-db-tasks.json`. Never write into blackboard/ directly.
   Application tasks queued later reference these ids.

Do not write application code. Finish by reporting the technology, the script paths and the task ids.
"""

STAGE_INSTRUCTIONS = {
    0: "Generate the project root and scaffold described by this task.",
    1: "Read this task and create the test at `path`.",
    2: ("Emit the payload of this unit through the coder writer script into "
        "`blackboard/coder-changes/<id>.json`. Never create, edit or delete the file at "
        "`path`, and never write a payload anywhere else."),
    3: "Read this task, inspect the implementation at `path`, and refactor it.",
}

BUDGET_SHAPES = {
    1: "skill read, task/manifest read, one test write, run-test-tool (max twice), red-phase writer",
    2: "assigned skill, red-phase read, one draft write, one writer call",
    3: "one skill, baseline test run, up to two refactor steps with a re-run each, evaluate writer",
    0: "one skill, the MCP session, the scaffold move",
}

# Every turn re-sends the whole transcript, so a stray `cat` of our own tooling is paid for again
# on every following call. These rules are stated in the prompt because the profiles alone were
# not enough to keep agents inside their inputs.
SCOPE_RULES = (
    "SCOPE: skills live only in `.opencode/skills/` and the SKILL.md named by your role is read once; "
    "do not list or search skill folders. Never read or grep `orchestrators/`, `ast_tools/`, "
    "`ast_weaver_tools/`, `.opencode/skills/read-write-file-ddd/**` sources, other tasks' "
    "`blackboard/queue|complete|error` records, or any agent scratch/session folder; never run `git`. "
    "The facts of this unit are in the message above: read a source file only to copy an exact signature, "
    "and then with a line-bounded `grep -n`, never a whole-file `cat`."
)


def _budget_line(target_agent, units=1, extra=""):
    """`TOOL BUDGET` sentence built from the single source of truth in settings."""
    budget = settings.call_budget(target_agent, units)
    if budget is None:
        return extra
    word = "call" if budget == 1 else "calls"
    shape = BUDGET_SHAPES.get(_stage_of(target_agent), "")
    lead = (f"TOOL BUDGET: at most {budget} tool {word} in this session "
            f"({shape})." if shape else f"TOOL BUDGET: at most {budget} tool {word} in this session.")
    return "\n".join(part for part in (lead, extra) if part)


def _stage_of(target_agent):
    """Stage number of an agent name, or -1 for the planning agents."""
    return next((stage for stage, agent in settings.STAGE_AGENTS.items()
                 if agent == target_agent), -1)


def _discipline(target_agent, units=1, extra=""):
    """Per-agent tool budget plus the shared scope rules, appended to every agent message."""
    return "\n" + "\n".join(part for part in (_budget_line(target_agent, units, extra),
                                              SCOPE_RULES) if part)

FEEDBACK_TEMPLATE = """
Previous attempt FAILED verification. Fix the implementation at `{path}` so the build and tests pass.
Do not change unrelated files. Verification output:
```
{log}
```
"""

FEEDBACK_TEMPLATE_CODER = """
Previous attempt FAILED verification. Do not edit the file at `{path}`: re-emit the payload of task
`{id}` through the writer script with `--retry`, changing only the payload field the message names
(`body`, `signature`, `returns`, `kind`, `members`, `annotations`, `methodAnnotations` or `imports`).
Same budget as before: one draft write plus one writer call.
Verification output:
```
{log}
```
"""
