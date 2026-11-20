"""All prompt templates and prompt builders for the pipeline agents.

Backend modules render these messages and hand them to their agent CLI.
The `{runner}` placeholder carries the backend-specific emit command.
"""
import json
import re
from pathlib import Path

import ddd
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


def build_architect_prompt(project_root, runner, phase="strategy"):
    """Phase 1 (strategy) brief - the split planner has its own builders
    (`build_planner_prompt` / `build_planner_repair_prompt`); the two phases share no
    bytes, each agent's context window starts clean (2026-11-20 architect split)."""
    if phase != "strategy":
        raise ValueError("phase 2 briefs moved to build_planner_prompt (architect split)")
    return (
        ARCHITECT_STRATEGY_PROMPT.replace("{project_root}", str(project_root))
        .replace("{domain_dir}", str(settings.DOMAIN_DIR.relative_to(settings.ROOT)))
        .replace("{context_map_dir}", str(settings.CONTEXT_MAP_DIR.relative_to(settings.ROOT)))
        .replace("{strategy_dir}", str(settings.COMPLETE_DIR.relative_to(settings.ROOT)))
        .replace("{runner}", runner)
        + _discipline(settings.ARCHITECT_STRATEGY_AGENT, extra=(
            "One strategy file per domain, one scaffold draft, one `--emit`."))
    )


def build_planner_prompt(project_root, runner, slug, context, draft, slice_path,
                         symbols_path, next_free, undrafted, gaps_path=None,
                         strategy_slice_path=None):
    """Phase 2 brief for ONE bounded context (2026-11-20 architect split). Every path the
    session reads or writes is computed by the engine and spelled here in full: the
    transcript of a short per-context session must contain decisions, not hunting.
    `gaps_path` defaults to the draft's own name with .gaps.json - the structured channel
    for coordinates the ONE build-manifest task lacks (X11: the engine consumes it)."""
    if gaps_path is None:
        gaps_path = str(draft).rsplit(".json", 1)[0] + ".gaps.json"
    if strategy_slice_path is None:
        strategy_slice_path = ddd.strategy_slice_path(slug, context)
    drafted_line = (f"{symbols_path} - the symbol table of the contexts already drafted "
                    "for this domain: their task ids, exports, signatures, owned meters, "
                    "served routes, config paths, the next-free numbers, and the stage-0 "
                    "families already scheduled (`build_manifest` with each task's verbatim "
                    "intent - a coordinate it carries is NOT yours to re-schedule)"
                    if symbols_path else
                    "(none yet - you draft the FIRST context of this domain: pins go only to "
                    "queued/complete ids and to ids inside your own draft file)")
    undrafted_line = (f"Undrafted contexts (their ids do not exist yet): {', '.join(undrafted)}."
                      if undrafted else
                      "You draft the LAST context of this domain: every other context is "
                      "already in the symbol table.")
    return (
        ARCHITECT_PLANNER_PROMPT.replace("{project_root}", str(project_root))
        .replace("{slug}", slug)
        .replace("{context}", str(context))
        .replace("{draft}", str(draft))
        .replace("{gaps}", str(gaps_path))
        .replace("{slice}", str(slice_path))
        .replace("{strategy_path}",
                  str(settings.COMPLETE_DIR / f"execution-strategy-{slug}.json"))
        .replace("{strategy_slice}", str(strategy_slice_path))
        .replace("{symbols_line}", drafted_line)
        .replace("{undrafted_line}", undrafted_line)
        .replace("{next_free}", ", ".join(f"{stage}: {tid}" for stage, tid in next_free.items()))
        .replace("{db_ids}", task_queue.stage_task_summary(0))
        .replace("{runner}", runner)
        + _discipline(settings.ARCHITECT_PLANNER_AGENT)
    )


def build_planner_repair_prompt(runner, slug, problems, drafts, digest_path):
    """The bounded remedy after an engine-run refusal: the error text and the named files,
    nothing else - the repair window starts EMPTY of the planning turns that produced the
    defect (each of which would re-send the transcript it failed on)."""
    return (
        ARCHITECT_PLANNER_REPAIR_PROMPT.replace("{slug}", slug)
        .replace("{problems}", problems.strip()[:8000])
        .replace("{drafts}", " ".join(str(d) for d in drafts))
        .replace("{digest}", str(digest_path))
        .replace("{runner}", runner)
        + _discipline(settings.ARCHITECT_PLANNER_AGENT)
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


def _planning_inputs(slug):
    """Board paths the between-phase specialists read (security/performance/AI share them)."""
    return {
        "slug": slug,
        "strategy_path":
            f"{settings.COMPLETE_DIR.relative_to(settings.ROOT)}/execution-strategy-{slug}.json",
        "slice_path":
            f"{settings.DOMAIN_DIR.relative_to(settings.ROOT)}/domain-boundary-{slug}.json",
        "map_path":
            f"{settings.CONTEXT_MAP_DIR.relative_to(settings.ROOT)}/context-map-{slug}.json",
    }


def build_security_prompt(slug, runner=None):
    """The security architect's per-domain message: plan in, one spec artifact out.

    `runner` is accepted and ignored: this agent emits nothing. The signature keeps the
    two backends' call sites uniform, and the ignored parameter is the assertion that no
    queue writer belongs in this phase - a future edit that passes a runner and starts
    emitting has changed the separation, not the wording.
    """
    del runner
    fields = _planning_inputs(slug)
    fields["spec_path"] = (
        f"{settings.COMPLETE_DIR.relative_to(settings.ROOT)}/security-spec-{slug}.json")
    message = SECURITY_PROMPT
    for key, value in fields.items():
        message = message.replace("{" + key + "}", str(value))
    return message + _discipline(settings.SECURITY_AGENT,
                                 "Three reads, one skill, one spec file. Nothing else is "
                                 "written or queued.")


def build_performance_prompt(slug, runner=None):
    """The performance architect's message: plan in, one performance spec out. Same
    no-emitter signature rule as `build_security_prompt`."""
    del runner
    fields = _planning_inputs(slug)
    fields["spec_path"] = (
        f"{settings.COMPLETE_DIR.relative_to(settings.ROOT)}/performance-spec-{slug}.json")
    message = PERFORMANCE_PROMPT
    for key, value in fields.items():
        message = message.replace("{" + key + "}", str(value))
    return message + _discipline(settings.PERFORMANCE_AGENT,
                                 "Three reads, one skill, one spec file. Nothing else is "
                                 "written or queued.")


def build_ai_prompt(slug, runner=None):
    """The AI architect's message: plan + the verified directive quote in, one AI spec out.
    The directive note is filled by the engine AFTER its verbatim check - the agent reads
    the witness, it never produces one."""
    del runner
    fields = _planning_inputs(slug)
    fields["spec_path"] = (
        f"{settings.COMPLETE_DIR.relative_to(settings.ROOT)}/ai-spec-{slug}.json")
    verified, note = ddd.ai_required(slug)
    fields["directive_note"] = note if verified else "(engine could not verify the directive)"
    message = AI_PROMPT
    for key, value in fields.items():
        message = message.replace("{" + key + "}", str(value))
    return message + _discipline(settings.AI_AGENT,
                                 "Three reads, one skill, one spec file. Nothing else is "
                                 "written or queued.")


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
        "record|exception. A generic type declares its type parameters inside `export`, spelled "
        "the way your language writes them on a type declaration (your stack skill gives the "
        "concrete shape): the shell the weaver creates carries them and `members`/`body` may use "
        "them. Supertype clauses the frozen tests demand (IS-A a port/base): "
        "`extends` one name and/or `implements` a list land on the created type header once; "
        "list those supertypes in `imports` too. `export` is the BARE type name (or the "
        "file's base name for config units) - never a modifier (`final`, `public`), never "
        "spaced: the weaver derives the created type from it, and a malformed export is a "
        "re-emit-field fix the writer message names. A method `signature` may be written TWO ways: "
        "the bare contract spelling (`from(Cart cart)` - keeps the located method's declared "
        "shape) or the COMPLETE declaration (`public static Order from(Cart cart)` - the method "
        "is then REDECLARED from that text: modifiers, type parameters and return type all "
        "ride the text, existing annotations are kept; no new field is needed for a shape "
        "nobody predicted. For a record, `members` is an array with ONE entry per part: every "
        "component its own element (`\"String deviceId\"`, `\"Instant tDevice\"`) and every body "
        "member (compact constructor, factory, extra method) another element - NEVER one joined "
        "string like \"String a, int b\": the weaver parses each element alone and rejects the "
        "joined form. The weaver routes the bare components to the header and the rest to the "
        "record body. Framework annotations go in `annotations` (type level) and "
        "`methodAnnotations` (method level), without the `@`, never inside `signature`; parameter "
        "annotations stay inside `signature`, which the weaver preserves. Keep the shape "
        "the `intent` asks for; never downgrade a record to a class to dodge a rejection. If a payload "
        "is rejected, the writer or weaver message names the field to fix: change that payload field "
        "and re-emit with `--retry`."
    )


def _collaborator_tables(task):
    """Pinned collaborators inlined in the tester's own message: name, producing task,
    package, supertypes and method table. The engine already holds these records; making
    the agent hunt for `blackboard/queue/<id>-<project>.json` by trial wasted tool calls
    and produced bogus 'records not found' blocks (T1-018). An unsatisfied pin is
    surfaced explicitly so the agent reports the plan hole instead of guessing."""
    hints = task.get("ast_hints") or {}
    deps = [d for d in (hints.get("dependencies") or []) if isinstance(d, dict)]
    if not deps:
        return ""
    index = task_queue.load_index(include_error=True)
    lines = ["Collaborators (API truth for construction, calls and stubs - the producing"
             " task's ast_hints, no file hunt needed):"]
    for dep in deps:
        producer = index.get(str(dep.get("task_id", "")))
        name = str(dep.get("type", "")).rsplit(".", 1)[-1]
        if not isinstance(producer, dict):
            lines.append(f"- {name} (producer {dep.get('task_id')}): NOT FOUND in queue or "
                         "complete - PLAN HOLE: report it as blocked, never guess its surface")
            continue
        ph = producer.get("ast_hints") or {}
        methods = "; ".join(
            f"{m.get('signature')}: {m.get('returns')}"
            + (f" [semantics: {m.get('semantics')}]" if str(m.get("semantics") or "").strip() else "")
            for m in (ph.get("methods") or [])[:8])
        vocabulary = ""
        if ph.get("meters"):
            vocabulary += "; meters: " + ", ".join(
                f"{m.get('name')}[{m.get('duty')}]" for m in ph["meters"] if isinstance(m, dict))
        if ph.get("routes"):
            vocabulary += "; routes: " + ", ".join(
                f"{r.get('method')} {r.get('path')}[{r.get('duty')}]"
                for r in ph["routes"] if isinstance(r, dict))
        if ph.get("config"):
            vocabulary += "; config: " + ", ".join(
                f"{c.get('path')}[{c.get('kind')}"
                + (":" + "|".join(c["fields"]) if c.get("fields") else "") + "]"
                for c in ph["config"] if isinstance(c, dict))
        lines.append(f"- {name} ({ph.get('package', '?')}) by {producer['id']}: "
                     f"implements {ph.get('implements') or []}; methods: {methods or '(value object)'}"
                     + vocabulary
                     + ("  <- CONSTRUCTION CONTRACT: table `semantics` bind legal values; "
                        "build fixtures through the named factory/legal literals only, "
                        "never a guessed argument" if any(
                            str(m.get("semantics") or "").strip()
                            for m in (ph.get("methods") or [])) else ""))
    return "\n" + "\n".join(lines) + "\n"


def _tester_tool_paths():
    """The EXACT commands the tester must run, spelled by the engine (the same principle as
    _collaborator_tables and _coder_contract: the message carries every fact the session
    needs, so searching the tooling costs zero calls instead of blowing the budget).
    Measured 2026-11-12: batch testers burned 20+ calls guessing these paths while SCOPE
    forbade listing the skill folders that contain them."""
    run_tool = settings.RUN_TEST_TOOL
    writer = settings.RED_PHASE_WRITER
    keys = sorted(p.name for p in settings.SKILLS_DIR.joinpath("tester-framework").iterdir()
                  if p.is_dir() and (p / "SKILL.md").is_file())
    return (
        "\nORACLE: this task's `intent` + `ast_hints` tables as QUEUED (methods, meters, routes, "
        "config) are the ONLY source of asserted names - the delivered implementation beside them "
        "in the tree is NOT the oracle. A reopened or regenerated test that copies what shipped "
        "launders the implementation's drift into frozen contract (2026-11-19 R1). A name your "
        "test must assert that the tables do not carry is a PLAN HOLE: report it, never harvest "
        "it from sources.\n"
        "\nTOOL PATHS (use these EXACT paths; do not search for scripts or list skill folders):\n"
        f"  run-test-tool: python3 {run_tool} --cwd <project root> --cmd \"<argv test command>\"\n"
        f"  red writer:    python3 {writer} --root {settings.ROOT} --task-id <id> "
        "--cmd \"<same argv>\"  (pipe the run-test-tool JSON into its stdin)\n"
        f"  tester skill:  {settings.SKILLS_DIR}/tester-framework/<key>/SKILL.md - available keys: "
        f"{', '.join(keys) if keys else 'NONE'}; pick the one matching this unit's language and "
        "test framework (a Java/JUnit unit uses java-junit5); no key fits => report and stop.\n")


def _evaluator_tool_paths():
    """Stage-3 exact tool commands (same no-search principle as _tester_tool_paths)."""
    return (
        "\nTOOL PATHS (use these EXACT paths; do not search):\n"
        f"  run-test-tool: python3 {settings.RUN_TEST_TOOL} --cwd <project root> "
        "--cmd \"<argv test command from the unit's red-phase record>\"\n"
        f"  evaluate writer: python3 {settings.SKILLS_DIR}/read-write-file-ddd/"
        f"writer-evaluate-results/write-evaluate-results.py --root {settings.ROOT} "
        "--task-id <id> --input <draft.json>\n")


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
    message += json.dumps({key: task.get(key) for key in settings.PROMPT_KEYS}, indent=2)
    if task["stage"] == settings.TESTER_STAGE:
        message += _tester_tool_paths()
        message += _collaborator_tables(task)
    if task["stage"] == settings.EVALUATOR_STAGE:
        message += _evaluator_tool_paths()
    if task["stage"] == settings.TDD_STAGE:
        t1 = next((d for d in task.get("dependsOn", []) if str(d).startswith("T1-")), None)
        if t1:
            message += (f"\nUnit artifacts (both mandatory): `blackboard/red-phase/{t1}.json`; "
                        f"`blackboard/ast-context/{t1}.json` - the exact constructors, calls and stubbed "
                        f"returns the test demands.")
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
    if not count:
        import test_gate
        count = len([f for f in test_gate.source_files(root)
                     if "test" not in f.parts and "tests" not in f.parts])
    parts.append(f"main_sources_present={count}")
    parts.append("write the payload from these facts plus your unit's blackboard/ast-context "
                 "<T1-id>.json (the exact constructors/calls/returns the test demands); "
                 "open the test file only if the contract is missing a fact")
    return " | ".join(parts)


def build_batch_message(tasks, feedback=None):
    """One session producing for several same-domain tasks (stage 1 tests, stage 2 payloads)."""
    first = tasks[0]
    stage = first["stage"]
    instruction = STAGE_INSTRUCTIONS.get(stage, "Complete these blackboard tasks.")
    if stage == settings.TESTER_STAGE:
        duty = (f"BATCH MODE: for EACH of the {len(tasks)} tasks below write the test at the "
                "task `path`, run it once through run-test-tool to confirm it fails as a "
                "proper red (fix and rerun that unit's test only if it fails for the WRONG "
                "reason), and write its red-phase record through the writer script "
                "(`--task-id <id>` per unit). Load the stack and skills ONCE and reuse them; "
                "do not skip any task; never open or run another unit's test.")
    else:
        duty = (f"BATCH MODE: produce and persist a payload for EACH of the {len(tasks)} tasks below "
                "(writer script once per task id, `--task-id <id>`); load the stack and skills once and "
                "reuse them across tasks; do not skip any task.")
    message = (
        f"Repository root (blackboard root for all writer/reader scripts): {settings.ROOT}\n"
        f"Project root (task `path` resolves here): {workspace.project_root_for(first['project'])}\n"
        f"{instruction}\n"
        f"{duty}\n\n"
    )
    if stage == settings.TESTER_STAGE:
        message += _tester_tool_paths()
    for task in tasks:
        t1 = next((d for d in task.get("dependsOn", []) if str(d).startswith("T1-")), None)
        block = json.dumps({key: task.get(key) for key in settings.PROMPT_KEYS}, indent=2)
        extra = ""
        if stage == settings.TESTER_STAGE:
            extra = _collaborator_tables(task)
        elif t1:
            extra = (f"\nUnit artifacts: mandatory `blackboard/red-phase/{t1}.json` and "
                     f"`blackboard/ast-context/{t1}.json`"
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
    if task["stage"] == settings.TDD_STAGE:
        template = FEEDBACK_TEMPLATE_CODER
    elif task["stage"] == settings.ASSEMBLY_STAGE:
        template = FEEDBACK_TEMPLATE_ASSEMBLY
    else:
        template = FEEDBACK_TEMPLATE
    return message + template.format(path=task["path"], id=task["id"], log=feedback)


DISCOVERY_PROMPT = """You are the domain boundary discovery specialist for this repository.
Read the business description at {description} and follow your agent instructions.
Write one domain boundary file per subdomain into {domain_dir}, recording
metadata.source_description = the path of the description you are reading.
If - and ONLY if - the description itself states that this domain needs no security,
record `security_directive` in that slice with the sentence copied VERBATIM: you do not
decide it, you transcribe it, and the engine checks the quotation against this file.
No directive means security IS required.
If - and ONLY if - the description itself states that this domain carries an AI capability
(generation, embedding, retrieval-augmented answers, agentic or tool-calling flows), record
`ai_directive` {required:true, quote, source:"description"} in that slice with the sentence
copied VERBATIM: you do not decide it, you transcribe it, and the engine checks the quotation
against this file. No ai_directive means NO AI capability - the phase never runs; never infer
one and never record required:false (the absent default says it).
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

ARCHITECT_STRATEGY_PROMPT = """You are the blackboard strategy architect for this repository. Phase 1 of 2 (the
split planner flow): strategy only. A separate planning session per bounded context
decomposes the tasks after the database, security, performance and AI phases - you write
the plan they read.
The generated project root is {project_root}.

For every slice `{domain_dir}/domain-boundary-<slug>.json`, read it together with its context map
`{context_map_dir}/context-map-<slug>.json`.

Once per domain:
1. Write the execution strategy to {strategy_dir}/execution-strategy-<slug>.json with the edit tool.
   Include the bounded contexts, module/package layout, build order, risks, a `persistence`
   object when the context owns data, and an `observability` object ALWAYS - for every
   executable context, UNCONDITIONALLY, whether or not the business description mentions
   auditing, logging or visibility (it is the operational floor, not a feature request; a
   strategy without the floor is refused when its tasks emit): step logs with their
   correlation key, the audit-trail records (actor, action, outcome, timestamp), named metrics with bounded
   tags, AND an `export` entry declaring how those events leave the process in machine-readable
   form for EXTERNAL tools (log management such as Elasticsearch: structured schema + local
   append-only sink; metrics: a scrape endpoint or push only when named). The app writes the
   contract, the platform ships it - no hard runtime dependency on the external tool, and the
   boot test must pass with the tool absent. Keep observability abstract - the tech-stack skill
   supplies the concrete properties.
   The security step runs after you and reads ONLY this file plus the slice and the map, and it
   tables ONE authorization row per entry of your `surfaces` array: every inbound surface the
   domain receives - http endpoint, message consumer, schedule, cli, cross-context call - is one
   entry `{name, kind, context, operations, traced_from}`, with `kind` from
   `http|consumer|job|cli|internal-call` and `context` one of your `bounded_contexts` BY EXACT
   NAME. A bounded context that receives nothing from outside declares itself in
   `contexts_without_inbound` WITH a reason: silence is not a decision, and phase 1 is refused
   when a context appears in neither table. `surfaces[].name` is the join key the spec copies
   VERBATIM into `authorization_matrix[].surface` and that the decomposition copies into the unit
   which IS that surface, so a surface not named here gets no permission row and no guard - and
   an undefended surface is found by its first caller, not by this run. `persistence.data_model`
   must likewise name every persisted concept the spec is to classify.
   Use only the slice and its own context map.
   The `tech stack` / `language` fields MUST repeat the versions the business description names
   VERBATIM (a seed saying "Java 21 / Spring Boot 3 WebFlux" yields language "Java 21", never a
   defaulted or normalized version). When the description names NO version, the tech-stack skill's
   DEFAULT applies (Java: 21 LTS). A skill floor ("Java 17+") is a compatibility minimum, never an
   emitted value: every version field carries ONE exact number. Never copy versions from an
   existing scaffold or tool default (Spring Initializr's default is a trap, not a decision):
   the description is the source of truth, and downstream stages pin the build from it.

2. Emit exactly one separate project scaffold task for THIS domain. Each domain is its own project,
   rooted at {project_root}/services/<slug>/. Fields:
   id (the next free T0 id), targetAgent "agent-container", stage 0, dependsOn [],
   kind "bootstrap", layer "root", feature null, export "project_scaffold",
   project "<slug>", path "<build marker>" relative to the domain root ("pom.xml" or "package.json"
   chosen from the stack), intent "Generate the <slug> project root and build scaffold using the matching
   mcp-server-alternatives skill, with language version <the ONE exact number from your strategy>,
   framework version <the exact pinned name and major from your strategy's tech stack, e.g. Spring Boot 3>,
   and build dependencies <the GENERATOR-NATIVE dependency ids of the stack's scaffold tool - for Spring
   Initializr the short ids like webflux, data-r2dbc, flyway, actuator, test, reactor-test, never the
   spring-boot-starter-* artifactIds - covering EVERY starter AND EVERY test artifact the tech stack names>".
   The intent MUST list the build dependencies AND the exact language AND framework versions the strategy
   names (a Boot-3 plan scaffolded on Boot 4 is off-plan; an omitted test artifact is a classpath hole that
   makes every later green gate impossible). agent-container cannot guess them: for Spring Initializr the
   list MUST include `test` and, when the plan tests reactive code, `reactor-test`, spelled as generator ids.
   A generator that retired the pinned major does NOT relax the plan: the stage-0 skill's machine-verified
   re-pin fallback keeps the tree equal to the pin. Never write a version RANGE ("3.x") where the plan
   demands a pin, and never cite "generator availability" in a strategy - availability is stage 0's problem.
    The intent MUST also require, for the chosen stack: a SINGLE composition root (never a second boot
    class beside the scaffold's), test-run timeout guardrails (a hung test must fail fast, never freeze
    the suite), and when the strategy's persistence object owns SQL, a schema MIGRATION RUNNER wired
    into the build plus an embeddable in-process substitute so the scaffold's own boot test passes
    without external services. Take the concrete artifact, plugin and tool names for these three
    requirements from the selected stack's tech-stack skill; the stage-4 assembly gate fails each of
    these structural requirements.
   Write it to /tmp/tasks/T0-<slug>.json and queue it with:
   python3 {runner} --emit /tmp/tasks/T0-<slug>.json

Do not create other task files and do not write application code in this phase.
Finish by listing the strategy file paths and the scaffold task id of each domain.
"""

ARCHITECT_PLANNER_PROMPT = """You are the blackboard planning architect for this repository.
Phase 2 of 2 (the split planner): the tasks of ONE bounded context, in this session.
Domain: {slug} - project root {project_root}/services/{slug}/; every task `path` is relative to it.
Context: {context} - draft file: {draft}.

READ EXACTLY THESE, once each - they are the whole input; nothing else is:
1. {strategy_slice} - phase 1's plan FILTERED to this context by Python: your surfaces
   (the `surfaces[].name` join keys), your persistence, your step logs, the module layout.
   The full file at {strategy_path} stays CLOSED - a fact the slice lacks is a reported
   gap for phase 1, never a silent re-read. Paths in this brief are repository paths;
   only a task `path` INSIDE your JSON is domain-root-relative. Do not rewrite the
   strategy; the ONE lawful edit: a mechanism the strategy promised ("via <mechanism>")
   that this plan will not install - amend the promise to what ships (the skill's rule
   (t)) and report the amendment.
2. {slice} - this context's duty digest, and every duty arrives COMPLETE: `surface`,
   `test_duty`, `measurement` are joined ONTO the duty (the specs' own sections -
   principals, assumptions, trust boundaries, risks - are not here and nothing in them is
   needed to claim), `covers` is expanded, and the matched mapping-table row rides as the
   duty's `table_row` (the identifier the intent must spell and the key the config unit
   owns, copied, not recalled). `build_coordinates` names the stage-0 manifest duty's
   dependencies when the scaffold lacks one. The raw specs and the mapping tables STAY
   CLOSED unless this file lists `unmapped_duties` - then open ONLY that spec's table.
3. {symbols_line}

DRAFT one JSON array at {draft} - the stage 1-3 units of context "{context}" - created with
your edit tool. A generator script is forbidden: no python/shell/heredoc that produces or
patches drafts (it rides every later turn, patches blind, and re-emits through your
costliest class - measured 2026-11-18: 91k carried, 41k worst single-turn output). Never
touch another context's file.

Id and pin law (the split makes this exact): number from {next_free}; the suffix matches
the stage. A pin goes ONLY to queue/complete ids, to ids inside this file, or to the symbol
table - a context not yet drafted cannot be referenced, because its ids do not exist yet:
{undrafted_line} Units that use the store list these queued database ids in `dependsOn`:
{db_ids}

Stage shape - the graph is law, because the drain orders units ONLY by dependsOn and
red must precede green: every unit of work is a T1+T2+T3 TRIPLE. stage 1 -> agent-tester
(path = the TEST file it creates, never a production file); stage 2 -> agent-coder (path =
the production file); stage 3 -> agent-evaluator (stage 2's file, kind refactor). A T1
dependsOn the domain scaffold + earlier units' T1 tasks - NEVER a stage-2 task (emit
refuses the inverted edge); a T2 dependsOn its own T1 + the T2 tasks of pinned producers;
a T3 dependsOn its own T2. The T1/T2 pair carries the IDENTICAL ast_hints table: the single API truth, shared literals TABLED - meter names only in
`ast_hints.meters`, request paths only in `ast_hints.routes`, property paths only in
`ast_hints.config` (rule (z)), one owner each, everyone else cites VERBATIM. intent
40-80 words (180 refused at emit): the claim, the config literals, both branches of a
signal - a fact `ast_hints` pins is never re-spelled in prose.

Build coordinates: consult the symbol table's `build_manifest` FIRST - a coordinate its
intent already carries is SCHEDULED, emit nothing for it. If none is scheduled yet and the
slice's `build_coordinates` names a coordinate the scaffold build file lacks, schedule the
ONE lawful stage-0 build-manifest duty as a bootstrap task (layer root, feature null,
targetAgent agent-container, kind bootstrap, layer root, feature null, export
build-manifest, dependsOn empty, path = the stack's build file, intent = the
generator-native ids). If the ONE manifest task exists but lacks YOUR coordinate, write it
VERBATIM into {gaps} - JSON: {"missing_coordinates": ["<coordinate string>", ...]},
spelled exactly as the slice's build_coordinates spells it: the ENGINE reads that file and
appends every reported coordinate to the ONE task before the batch emit. Never emit a
second manifest (the linter refuses it), never edit another context's file, and never
settle for prose in your output - a report the machine cannot read is an unscheduled
coordinate, and the first red compile dies in that hole. A unit whose copied mechanism
needs such a coordinate lists the build-manifest task id in its `dependsOn` (its T1
twin inherits it through the pair): the tester compiles against a classpath that must
exist first.

Lead duties: every aggregate root / event / read endpoint of this context gets its
API/UseCase unit; repository port + adapter (DDL is the database phase's); the strategy's
observability floor decomposes into its units here as the skill directs - audit ports
tabled, one correlation middleware unit unless the symbol table already shows one, an
externalized-config unit ONCE per domain (skip it if the symbol table already has one).

DUTY CLAIMS, machine-enforced at emit: every duty of the slice is discharged INSIDE the
enforcing STAGE-2 unit by spelling its `spec_ref` AND `capability` VERBATIM beside the
mechanism copied from that duty's `table_row`. Security duties add the reach geometry: the
unit that IS a surface (its intent names the strategy's `surfaces[].name`) pins the
enforcing unit in `ast_hints.dependencies` + `dependsOn`, and that entry unit's stage-1
pair carries the row id and its `test_duty` CROSS-OWNER case. Performance (PB-/PI-, WB-
only where no PB- covers the capability) and AI (AC-/AM-) duties ride the same (y1) form
without the reach law; PA- assumptions and AI roles/assumptions never carry claims. The
HOME OF THE ARTIFACT is a SOURCE unit and the writable channel is language source or
configuration document ONLY - a template file has no writer on this board.

The FULL contract (a)-(z) is `task-decomposition-dag` SKILL.md - load it once, do not
memorize it: the linter and the batch emit quote the violated rule by letter.

FINISH with the lint, then stop:
    python3 {runner} --lint {draft}
EDIT every ERR [id]: line into existence-proof (one lint pass of edits costs hundreds of
tokens; a rewrite costs 10-30k), lint again. If ONE defect shape repeats across tasks it
is a law you missed, not N typos: reread that rule, rewrite the WHOLE file in ONE create
call, lint once - a 20-edit cascade re-sends the transcript 20 times and costs the
session its budget (measured live 2026-11-20). A `LINT-CLEAN` line is your exit. Do NOT run
`--emit`: when every context of the domain is drafted, the ENGINE emits the batch in one
command and only a refusal then comes back to a repair session.

Output: task ids + deps, the duty-by-duty closure (`spec_ref -> claiming unit ids ->
mechanism named -> surface unit`), any `unmapped_duties` you had to open, risks.
"""

ARCHITECT_PLANNER_REPAIR_PROMPT = """You are the blackboard planning architect for this repository. Repair
pass for domain `{slug}`: the engine validated the planning drafts and REFUSED the batch -
no planning session ran yet in this context window, these lines are your only input besides
the named files.

ERRORS (each `ERR [pointer]` names the exact task object and field):
{problems}

Files of this domain's plan: {drafts}
The full duty digest (duties, rule rows, matched mechanism rows): {digest}
The contract (a)-(z): task-decomposition-dag SKILL.md.

Work: read ONLY the files the pointers name. Locate every object one pointer SHAPE
covers with ONE grep over the named draft files - then fix them: a repeating shape is ONE
defect, not N typos, so batch the repairs (several edits in one pass, or one rewrite of
the affected file), never one edit per task object across a dozen turns. Re-lint each
edited file ONCE with `python3 {runner} --lint <file>`; never re-lint a file you did not
change; then stop - the ENGINE re-runs the batch emit.
A refusal that contradicts a spec (a duty the mechanism rows cannot realize) is a reported
flow defect you NAME, never a spec rewrite: the operator re-runs the phase that wrote it.
"""

DATABASE_PROMPT = """You are the blackboard database architect for this repository.
Run your workflow for the bounded context slug `{slug}` only. Its project root is {project_root}/services/{slug}/.

1. Read the strategy file {strategy_path} with the read tool and use only its `persistence` object.
2. Select the storage technology from the tech-stack skill. Write the migration and configuration
   scripts yourself, only under {project_root}/services/{slug}/db/migrations/ (absolute path). You own
   the database files of this domain: setup, schema migration, configuration, and backup.
   Runner/configuration fragments carry weight ONLY in the property namespace the runtime actually
   reads (the tech-stack skill names it) and only in files the application loads: use the framework
   namespace (not the bare tool's), name the consuming config unit, and make the configured locations
   align with where the migration scripts physically live. A fragment nothing reads is schema fiction -
   prefer the app's own config file over a standalone profile when a config unit exists.
3. Queue one stage 0 bootstrap task per database concern (store setup, schema migration, configuration
   profile, backup/recovery). Write ONE array file /tmp/tasks/{slug}-db-tasks.json holding every task
   object, with exactly the keys of your output contract (every `export` a non-empty file base name,
   never null), ids starting at {next_id}, each with dependsOn ["{scaffold_id}"] and path
   db/migrations/<file> relative to the domain project root, then queue them
   with: `python3 {runner} --emit /tmp/tasks/{slug}-db-tasks.json`. Never write into blackboard/ directly.
   Application tasks queued later reference these ids.

Do not write application code. Finish by reporting the technology, the script paths and the task ids.
"""

SECURITY_PROMPT = """You are the blackboard security architect for this repository.
Run your workflow for the domain `{slug}` only.

1. Load your `security-strategy` skill once. Its `references/security-spec.schema.json` is the
   shape of your only deliverable; the skill's rules are the content.
2. Read the plan, once each:
   - {strategy_path} with the read tool - it is a strategy, not a DDD report, and the reader
     refuses files that carry no `schema_version`, so this is the only correct route to it
     (use `bounded_contexts`, `surfaces`, `modules`, `module_layout`, `persistence.data_model`,
     `observability`);
   - {slice_path} (`actors`, `external_systems`, `invariants`) and {map_path}
     (`relationships`, `cross_boundary_flows`) with the reader command your profile gives -
     the only shell this phase runs, and it validates each report before you rely on it.
   A missing, unreadable, or refused input is a reportable STOP: never repair it, never rewrite
   it, never re-decide persistence or observability.
3. Decide what must hold. Threat model per context (assets, entrants, surfaces, crossings);
   ONE authorization row for every entry of the strategy's `surfaces` array, its `surface` field
   copying `surfaces[].name` VERBATIM (that string is the join key: the gate refuses a declared
   surface with no row, and the architect matches the enforcing unit to the surface by it); an
   ownership predicate on EVERY row addressed by a client-supplied identifier; per-concept data
   classification with its log, error and export visibility; deny-by-default and fail-closed
   invariants; the security audit floor. `principals[].source` names the slice entry it came from
   VERBATIM, and `invariants[].owner_context` names a `bounded_contexts` entry exactly as the
   strategy spells it.
4. Write {spec_path} with your edit tool, exactly in the reference shape: same keys in the same
   order, closed enumerations, ids sorted, one telegraphic sentence per string (<=15 words, no
   because/so/therefore filler). Every rule names the capability token that holds it, its
   enforcement point, its test duty, and a duty that discharges it; rules sharing one
   (`capability`, `unit_kind`, `owner_context`) are discharged by ONE duty that lists the
   other rule ids in its `covers` - a duplicate triple is refused, while the same pair in
   two bounded contexts is TWO duties, each naming its `owner_context` (exact
   `bounded_contexts` spelling).
   A `risks[]` entry cites the control in THIS spec that answers it, or states an accepted posture
   (`accepted:` / `none:` / `operator:`) WITH the exposure that remains: a risk that does neither
   is refused, and the pipeline prints every one of them, so nothing you record goes unread.
   Do not touch any other file on the board.
5. Your vocabulary is requirements only. If the artifact contains a framework, library, product,
   annotation, file path, package, property key, stage, task id, or agent name, it is wrong: the
   architect who decomposes these duties already holds the tech-stack skill and owns every
   mechanism, path, and wiring decision. What you cannot decide from the INPUTS - a missing
   surface, flow, or persisted concept, a conflict between requirements - goes to
   `open_questions`, never an invented answer; an entry there STOPS the run. A missing NUMBER
   is not that: it is the baseline assumption's job (step 3) - halting a functional seed that
   never stated RPS mistakes the floor for a spec sheet., so name the missing input precisely (which
   surface, which concept, which file should have carried it) instead of softening it into a risk.

You queue nothing and you author no project file: no task JSON, no `--emit`, no scaffold, no
migration, no configuration. Capability tokens are the whole handoff. Do not run a validator or
re-read the board to grade yourself: the orchestrator machine-checks {spec_path} when the session
ends, and refuses the phase - self-validation would make the judged party its own witness.

Finish by reporting the spec path, the matrix row and classification counts, the capability tokens
you named, the risks, and the open questions.
"""

PERFORMANCE_PROMPT = """You are the blackboard performance architect for this repository.
Run your workflow for the domain `{slug}` only.

1. Load your `performance-strategy` skill once. Its
   `references/performance-spec.schema.json` is the shape of your only deliverable; the skill's
   rules are the content.
2. Read the plan, once each:
   - {strategy_path} with the read tool - `bounded_contexts`, `surfaces`, `modules`,
     `persistence` (drivers, data_model, queries), `observability`;
   - {slice_path} and {map_path} with the reader command your profile gives - the only shell
     this phase runs. A missing, unreadable, or refused input is a reportable STOP: never
     repair it, never rewrite it, never re-decide the architecture.
3. Model the load, then table it:
   - ONE workload entry for every entry of the strategy's `surfaces` array, its `surface` field
     copying `surfaces[].name` VERBATIM (same join-key law as the security rows), each stating
     what drives it (rate, payload size, fan-out, data volume) or moving to
     `surfaces_exempt` WITH a reason - a surface nobody sized is sized by framework defaults;
     a MISSING NUMBER IS A BASELINE ASSUMPTION, NEVER AN OPEN QUESTION: functional seeds
     describe behavior, not traffic - record one assumption (PA-01, e.g. "single-node baseline
     ceiling assumed wherever the description omits rates and volumes"), bound the budgets
     conservatively from it, and cite it in the driver ("per PA-01");
   - a budget per load-side decision that bounds something: concurrency, queue/acceptance,
     cache, retry, page size, payload, pool, timeout - each with a `measurement` whose `kind`
     is one of the closed deterministic set (query-count, config-key, status-code,
     payload-size, queue-depth, deterministic-count). A wall clock is NOT a legal kind:
     a limit only provable by a stopwatch is a wish no stage-1 gate can enforce without
     flaking;
   - invariants that hold at worst case (no unbounded queue anywhere, one bounded policy per
     path), each naming an abstract capability token;
   - a duty discharging EVERY budget and invariant, ONE duty per unique (capability,
     unit_kind, owner_context): obligation, capability token, unit_kind from the closed set,
     owner_context an exact bounded_contexts name - the same pair in two contexts is TWO
     duties;
     WB- workload rows and PA- assumptions are context, their ids riding a PB duty's
     `covers`, never duplicate duty rows. Never the mechanism, never the vendor, never the
     library.
4. Write {spec_path} with your edit tool, exactly in the reference shape, one telegraphic
   sentence per string (<=15 words, no because/so/therefore filler). A `risks[]` entry
   cites an entry this spec declares or states an accepted posture (`accepted:` / `none:` /
   `operator:`) with a non-empty `residual`. Anything you cannot decide from the inputs goes
   to `open_questions` - never an invented answer; an entry there STOPS the run.
5. Your vocabulary is requirements only. If the artifact contains a framework, library,
   product, annotation, file path, package, property key, stage, task id, or agent name, it
   is wrong: the architect who decomposes these duties holds the stack skill and owns every
   mechanism. Ordinary capacity words (throughput, latency budget as a REQUIREMENT sentence,
   backpressure, cache, pool) are legal prose; realization names are not.

You queue nothing and you author no project file. The orchestrator machine-checks {spec_path}
when the session ends and refuses the phase; do not grade yourself.

Finish by reporting the spec path, workload coverage, budget count and kinds, the capability
tokens, the risks, and the open questions.
"""

AI_PROMPT = """You are the blackboard AI architect for this repository.
Run your workflow for the domain `{slug}` only. The business description itself directed this
phase - the engine verified the sentence VERBATIM: {directive_note}

1. Load your `ai-strategy` skill once. Its `references/ai-spec.schema.json` is the shape of
   your only deliverable; the skill's rules are the content.
2. Read the plan, once each: {strategy_path} with the read tool (`bounded_contexts`,
   `surfaces`, `persistence.data_model`, `observability`); {slice_path} and {map_path} with
   the reader command your profile gives. A missing or refused input is a reportable STOP.
   The description sentence quoted above is your mandate and your BOUNDARY: plan the AI
   capability it names, nothing the description never asked for.
3. Decide, then table:
   - `model_roles`: every model/embedding role the capability needs, each stating its
     statefulness AND (unless none) its memory_technique - none: single-turn work or a
     handoff worker whole in its envelope; session: history loss on restart is acceptable
     with no audit/resume duty; DURABLE is mandatory when continuity crosses sessions or
     devices, when a `human-approval-gate` pause binds the role (an awaiting-approval that
     resumes from outside cannot live in a restartable process - checked), when a shared
     blackboard or audit trail needs history (its concept must already sit in the strategy's
     `persistence.data_model` or the question goes to `open_questions` - checked), or when
     recall is semantic across sessions (then `retrieval-scope-guard` is required - checked);
     techniques: sliding-window (last N verbatim), rolling-summary (older turns condensed
     into a running summary - compaction IS the budget mechanism, bound it too),
     semantic-episodic (embedded, retrieved top-K); a role that names no data classes
     touches all of them;
   - `capabilities`: one entry per AI behavior, keyed VERBATIM to a strategy `surfaces[].name`
     or a context-map flow, each carrying ONE token from the CLOSED vocabulary (the skill
     lists them) and a `measurement` whose kind is deterministic (stub-call-count,
     schema-validation, config-key, status-code, payload-size, deterministic-count);
   - the mandatory invariant: every model/embedding access is a PORT with an offline
     stand-in, and NO test or slice may reach a live endpoint - a plan that can call the
     world from CI will, and it bills real tokens to do it;
   - a `prompt-contract` capability names a SOURCE TYPE as its home (the five elements -
     version, role identity, input placeholders, output-schema reference, refusal text -
     are members the unit's table holds; template files have no writer on this board);
   - DELIVERY SHAPE is yours to decide, TRANSPORT is not: emit `incremental-progress-stream`
     whenever the directed capability is multimodal analysis, a handoff loop, or user-facing
     generation whose time-to-first-token would stall one request-response call - the row
     states incremental events THEN a terminal completion, proved by stub-call-count /
     deterministic-count; where completion is polled from the durable store, record the
     assumption instead - silence about the shape is undecided delivery. Naming SSE,
     websockets or gRPC here is a gate refusal: the protocol is the architect's mapping onto
     the concrete surface;
   - if the directed capability is a MULTI-AGENT system: every delegation edge is an
     `agent-handoff` row enumerating from-role to to-role over the `model_roles` entries
     (typed envelope tabled, edges closed); EVERY autonomous cycle carries a
     `loop-budget-cap` invariant - max-turns bound + named cycle-break outcome, proved by
     stub-call-count - and the gate refuses a handoff topology without it, because each
     call can be valid and small while the LOOP spins forever (the AI class of the
     unbounded queue); a high-impact or irreversible tool SPLITs into propose/execute
     under `human-approval-gate`: the awaiting-approval pause is persisted state resumed
     ONLY through the declared channel, denial a first-class outcome, never a thread
     blocked on a human; every agent an edge or rule involves is bound through the row's
     `roles` list (AR- ids only);
   - a duty per capability and per invariant: obligation, the SAME token, unit_kind from the
     closed set. `spec_ref` names ONLY an AC-/AM- row - the rows that carry a token; a
     model role is a SUBJECT realized through the capabilities that bind it, an assumption
     is context: cite them inside an obligation, never discharge them. Never a framework,
     never a vendor, never a model product name - the directed sentence may name one,
     your artifact translates it into roles and capabilities.
4. Write {spec_path} with your edit tool, exactly in the reference shape. `risks[]` follows the
     register law (control cited, or accepted posture + residual). Undecided goes to
     `open_questions` - never invented; an entry there STOPS the run.

You queue nothing and you author no project file. The orchestrator machine-checks {spec_path}
when the session ends and refuses the phase; do not grade yourself.

Finish by reporting the spec path, the roles, the capability tokens, the offline invariant,
the risks, and the open questions.
"""

STAGE_INSTRUCTIONS = {
    0: "Generate the project root and scaffold described by this task.",
    1: "Read this task and create the test at `path`.",
    2: ("Emit the payload of this unit through the coder writer script into "
        "`blackboard/coder-changes/<id>.json`. Never create, edit or delete the file at "
        "`path`, and never write a payload anywhere else."),
    3: "Read this task, inspect the implementation at `path`, and refactor it.",
    4: ("Boot the generated application: detect the stack, load your assembly skill, run "
        "the assembly command named in the task intent through run-test-tool, close every "
        "wiring gap in production sources only, and repeat until the smoke test is green."),
}

BUDGET_SHAPES = {
    1: "skill read, task/manifest read, one test write, run-test-tool (max twice), red-phase writer",
    2: "assigned skill, red-phase read, ast-context read, one draft write, one writer call",
    3: "one skill, baseline test run, up to two refactor steps with a re-run each, evaluate writer",
    0: "one skill, the MCP session, the scaffold move",
}

# Every turn re-sends the whole transcript, so a stray `cat` of our own tooling is paid for again
# on every following call. These rules are stated in the prompt because the profiles alone were
# not enough to keep agents inside their inputs.
SCOPE_RULES = (
    "SCOPE: skills live only in `.opencode/skills/` and the SKILL.md named by your role is read once; "
    "do not list or search skill folders. Never read or grep `orchestrators/`, `ast_tools/`, "
    "`ast_weaver_tools/`, other tasks' `blackboard/queue|complete|error` records, or any agent "
    "scratch/session folder; never run `git`. The writer scripts under "
    "`read-write-file-ddd/**` are RUN via the exact commands given in this message - that is "
    "REQUIRED; the ban covers reading their SOURCE CODE only. "
    "The facts of this unit are in the message above: read a source file only to copy an exact "
    "signature or literal NAMED BY THIS UNIT'S ast_hints TABLE - the delivered tree is never the "
    "source of a name you assert, and then read with a line-bounded `grep -n`, never a whole-file "
    "`cat`."
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

FEEDBACK_TEMPLATE_ASSEMBLY = """
Previous attempt FAILED the assembly gate: the application still does not boot. Close the
remaining wiring gaps in production sources following your assembly skill (framework
registration, providers/adapters for interfaces, driver configuration). Never edit tests,
build manifests, or another task's contract. Verification output:
```
{log}
```
"""

FEEDBACK_TEMPLATE_CODER = """
Previous attempt FAILED verification. Do not edit the file at `{path}`: re-emit the payload of task
`{id}` through the writer script with `--retry`, changing only the payload field the message names
(`body`, `signature`, `returns`, `kind`, `members`, `annotations`, `methodAnnotations`, `imports`,
`export` to declare the type's parameters, or `extends`/`implements` when the type must be a subtype of a port).
Same budget as before: one draft write plus one writer call.
Rules for reading the log: the gate compiles the WHOLE module, so the failure may be attributed to
your unit even when the blamed file is a frozen test of another unit. If the log names a missing
constructor, method or accessor ON THE TYPE YOUR TASK EXPORTS (task `export`) - e.g.
`no suitable constructor`, `cannot find symbol: method x() location: class YourType` - your payload
must ADD that member to your type as a delegating overload or accessor matching the exact call
shown; other units' frozen tests are part of your contract surface. Fix EVERY demand the log
attributes to your type in ONE re-emit (all `MUST PROVIDE` entries and all blamed lines of your
file), not only the first. Never re-emit an unchanged
payload: if after reading the whole log you truly own none of it, change the payload to the strictest
reading of your red-phase contract instead of repeating byte-identical content.
Verification output:
```
{log}
```
"""
