# Blackboard Evaluator Project

An experimental, agent-driven software factory that turns a business description into a domain-oriented codebase.

The orchestrator reads a seed document, discovers bounded contexts, plans the architecture, creates database and application tasks, and coordinates specialized agents to scaffold, test, implement, and evaluate each unit of work. Agents do not call one another directly: they communicate through validated JSON files stored on a local **blackboard**.

The same workflow can run with either **OpenCode** or **GitHub Copilot CLI**.

## What the project does

- Applies Domain-Driven Design (DDD) to split a business description into bounded contexts.
- Creates an execution strategy and a separate project for each discovered domain.
- Selects persistence technologies and queues database migration tasks.
- Breaks application work into dependency-aware test, code, and evaluation tasks.
- Runs each new test in **red phase**, records the result, and extracts **AST context** for the target class/method to guide the coder.
- Processes tasks with an in-memory dependency graph instead of repeatedly searching the queue after every task.
- Groups ready work by domain to improve execution locality and make logs easier to follow.
- Gives every task a stable, readable filename such as `T0-023-treasury-fx.json`.
- Validates task schemas and dependencies, quarantines invalid work, and records failures.
- Supports optional compilation/build checks and OpenTelemetry tracing.

## How it works

```text
Business description (seed/*.md)
              |
              v
   Domain boundary discovery
              |
              v
       Context mapping
              |
              v
   Execution strategy per domain
              |
              v
 Database planning and stage 0 tasks
              |
              v
 Application task decomposition
              |
              v
   Red-phase test execution
              |
              v
   AST context extraction
              |
              v
       Validated blackboard queue
              |
              v
 Dependency-aware, domain-grouped execution
              |
              v
 Generated projects under projects/<name>/services/
```

### Processing stages

| Stage | Agent / Tool | Responsibility |
| --- | --- | --- |
| 0 | `agent-container` | Generate the domain project scaffold and database artifacts. |
| 1 | `agent-tester` | Write tests for one implementation-ready unit, run the red-phase check, and record the result. |
| - | `ast-dispatcher` | Extract AST context for the target class/method into `blackboard/ast-context/<id>.json`. |
| 2 | `agent-coder` | Implement the unit described by the task, guided by the test and AST context. |
| - | `code-weaver-dispatcher` | Splice the coder payload into the source tree and record `blackboard/weave-results/<id>.json`. |
| 3 | `agent-evaluator` | TDD refactor: audit clean code, architecture, performance, and security while keeping the recorded test green; record `blackboard/evaluate-results/<id>.json`. |
| 4 | `agent-assembly` | Application assembly: boot the generated application. Stack-agnostic — detects the framework, loads its skill from `assembly-framework/`, closes runtime wiring gaps in production sources only, and re-runs the scaffold smoke test until the application starts. The orchestrator verifies the boot with its own deterministic gate; there is no agent artifact to trust. |

Before these stages, two specialists create the DDD artifacts:

- `domain-boundary-discovery-specialist` writes one domain boundary file per subdomain.
- `domain-context-mapping-specialist` writes the corresponding context maps.
- `agent-architect` writes execution strategies and decomposes the work into tasks.
- `agent-database-architect` selects storage technologies and queues database tasks.

### Red-phase checks and AST context extraction

Stage 1 is not just "write a test". The tester agent:

1. Loads the matching `tester-framework/<language-framework>/SKILL.md` (for example `java-junit5`).
2. Writes the test at the task `path`.
3. Runs only that test through `tester-framework/run-test-tool.py`, which parses the output and classifies it as `passed`, `compile_error`, `assertion_failure`, or `not_run`.
4. Persists the result with `read-write-file-ddd/writer-red-phase/write-red-phase.py` as `blackboard/red-phase/<id>.json`. The file must contain `{"executed": true}` for the orchestrator to proceed.

After validating the red-phase record, the OpenCode orchestrator invokes the **AST dispatcher**:

```text
python3 .opencode/skills/ast-dispatcher/ast-dispatcher.py \
  --root <project_root> --task-id <id>
```

The dispatcher:

- Detects the language/framework from project files (`pom.xml`, `package.json`, `go.mod`, etc.).
- Selects the matching builder from `ast-dispatcher/builders/` (Java, Go, Python, TypeScript).
- Merges the task context from `blackboard/queue/<id>.json` (target class via `export`) and `blackboard/red-phase/<id>.json` (target method from missing symbols or assertion failures).
- Runs the configured AST executable and writes the result to `blackboard/ast-context/<id>.json`.

For Java/Spring Boot projects, the executable is the fat JAR located by `AST_TOOL_ROOT` and `AST_JAR_NAME` in `.env`. The bundled Java extractor is at `ast_tools/ast_extractor/target/ast_extractor-0.0.1-SNAPSHOT.jar`; point `.env` to the extractor you want to use.

A dispatcher failure is logged but does not block `agent-coder`; the context is treated as optional guidance.

### Green-phase code weaving

Stage 2 is not just "write the implementation": `agent-coder` never touches production code. It records the pure method body and return type (`returns`) in `blackboard/coder-changes/<id>.json` (via `read-write-file-ddd/writer-coder-changes/write-coder-changes.py`, which sets `executed: true`). The orchestrator then runs the weaver as part of the stage 2 verification gate, before the build/test command:

```text
python3 .opencode/skills/code-weaver-dispatcher/code-weaver-dispatcher.py \
  --root <repo_root> --project-root <project_root> --task-id <id>
```

The dispatcher:

- Loads builders from `code-weaver-dispatcher/builders/` at runtime (Java, Go, Python, TypeScript) and selects one by the payload `language`, falling back to project detection.
- Validates `blackboard/coder-changes/<id>.json` (required keys, `targetFile` stays inside the project root; a missing target file is allowed because the weaver creates it) and hands the payload file to the weaver executable.
- For Java/Spring Boot, the executable is the `ast_weaver_java` fat JAR located by `WEAVER_TOOL_ROOT` and `WEAVER_JAR_NAME` in `.env`; it replaces the target method body through JavaParser with lexical preservation, adding `imports` and leaving the rest of the file untouched.
- Create-if-missing: when the target class or overload does not exist yet (the usual red for new units), the JAR creates the file (package from the FQ `export` or the Maven path), the type, and the method using payload `returns` (`void` when blank), optional `kind` (`class|interface|enum|record`) and `members` (constructor/fields, abstract signatures, enum constants, record components). Member injection is idempotent (normalized-text dedupe), so deferred re-weaves never duplicate fields or ctors. Existing methods keep lexical-preserving edits; created nodes print with the default formatter.
- Writes the run record to `blackboard/weave-results/<id>.json` with `executed: true`.

A weaving failure is not fatal noise: its compact reason (e.g. body parse error, no overload matching the signature) becomes `agent-coder` retry feedback, so the coder re-emits the payload with `--retry` and the orchestrator weaves again before re-running the gate.

### Green-phase test gate

Immediately after weaving, the orchestrator re-executes the tester's scoped test command through the shared `tester-framework/run-test-tool.py` — no agent involvement. The command is read from the `command` key that `write-red-phase.py` records in `blackboard/red-phase/<id>.json`. Gate outcomes:

| Result | Orchestrator behavior |
| --- | --- |
| `status: passed` | continue to the build gate, then mark the task complete (stage 3 `agent-evaluator` becomes ready) |
| `assertion_failure` / `compile_error` / `error` | retry the stage 2 coder with the compact failure log (up to `MAX_TDD_RETRIES` = 3 attempts) |
| `not_run` (silent exit-0, or a `&&`/`$VAR` command refused by the argv-only guard) | treated as failure and retried: an unexecuted suite never passes the gate |
| still failing after 3 attempts | the task moves to `blackboard/error/` and its dependents are quarantined |
| no `command` recorded (older red-phase files) | the gate is skipped with a warning; the build gate still applies |
| classification | patterns cover Maven/Surefire, Gradle, Jest/ts-jest, pytest, unittest, `go test`, and cargo; the tool ships its own suite in `run-test-tool-tests.py` |

Stage 3 reuses the same mechanism: `agent-evaluator` refactors against the test command recorded in `blackboard/red-phase/<T1-id>.json` (resolved through the task `dependsOn` chain), re-runs it through `run-test-tool.py` after every step, and persists an `evaluate-results` artifact via `writer-evaluate-results.py` — which refuses to write when the final test is not green. The hand-off back to the orchestrator is deterministic: (1) `evaluate_result_problem` checks that `blackboard/evaluate-results/<id>.json` exists, is `executed`, and reports `final_test.status == "passed"`; (2) the stage-3 verify step runs the final **global** compile/check gate for the domain project (`verify_project`, skipped under `--verify none`); (3) only then is the task moved from `blackboard/queue/` to `blackboard/complete/`. Any step failing sends the task to `blackboard/error/` with the reason. After the green hand-off, the engine appends `engine_diff` to the artifact: a ground-truth unified diff of every production source the session actually changed (computed by `refactor_audit.py` from before/after snapshots, not from the agent's self-reported `changes[]`).

### Application assembly (stage 4)

No scoped gate ever boots the application: unit tests construct collaborators with
`new` and mocks, so a class the framework container cannot supply (an unregistered
service, a port without an adapter, a driver without configuration) passes every
unit gate and still fails to start. The scaffold's own smoke test is the only
contract that proves the whole application wiring resolves, so the pipeline queues
**one stage-4 task per domain** (`assembly.py`, drained structurally last):
`agent-assembly` detects the stack, loads the matching skill from
`.opencode/skills/assembly-framework/<language>-<framework>/` (Spring Boot, NestJS,
FastAPI — each owns its failure-reading map, ordered fix menu, and editable roots),
runs the smoke command through `run-test-tool.py`, and closes wiring gaps in
production sources only — never tests, manifests, or unit contracts. The agent and
the queue carry no framework vocabulary; per-stack detection rules live in the small
detector registry in `assembly.py`. The orchestrator re-checks the boot with its own
deterministic gate after every session, retrying the agent with the fresh log up to
`MAX_TDD_RETRIES`. There is no agent artifact to trust: the gate is the proof.

The tester agent keeps deciding *which* test command proves the unit red (it needs domain judgment); the orchestrator owns *re-running* it for green (pure mechanics). Both use the same generic script, so the red and green executions are identical commands parsed by identical regexes.

## Repository layout

```text
.
├── orchestrators/                 # Pipeline implementation, split by responsibility
│   ├── orchestrator_opencode.py   # Entry point: OpenCode backend
│   ├── orchestrator_github.py     # Entry point: GitHub Copilot CLI backend
│   ├── pipeline.py                # Shared CLI shape and full phase order
│   ├── settings.py                # Repository layout, stages, schema, timeouts
│   ├── workspace.py               # Seed and project-root resolution
│   ├── prompts.py                 # Agent prompt templates and builders
│   ├── tasks.py                   # Task schema validation and ordering
│   ├── task_queue.py              # Queue files: read, index, emit, quarantine
│   ├── ddd.py                     # Discovery, context-map and strategy gates
│   ├── assembly.py                # Stage 4: scaffold smoke-test detection, task emit, boot gate
│   ├── refactor_audit.py          # Engine-computed diffs of what stage-3 sessions changed
│   ├── verification.py            # Framework build/check gates
│   ├── dispatchers.py             # red-phase, ast-dispatcher, code-weaver-dispatcher
│   ├── test_gate.py               # Green-phase re-run of the recorded test command
│   ├── agent_runners.py           # Subprocess plumbing and log tails
│   ├── tdd_engine.py              # execute_with_tdd and drain_queue
│   ├── opencode_backend.py        # ``opencode run`` phase runners
│   ├── copilot_backend.py         # Copilot CLI profiles and phase runners
│   └── telemetry.py               # Optional OpenTelemetry integration
├── seed/                          # Input business descriptions
├── ast_tools/                     # Language-specific AST extractors (e.g. Java)
├── blackboard/
│   ├── domain/                    # Discovered domain boundaries
│   ├── context-map/               # DDD context maps
│   ├── queue/                     # Tasks waiting to run
│   ├── complete/                  # Completed tasks and execution strategies
│   ├── error/                     # Invalid or failed tasks with error details
│   ├── red-phase/                 # Red-phase test-run records produced by agent-tester
│   ├── ast-context/               # AST context extracted for each stage-1 task
│   ├── coder-changes/             # Pure method-body payloads produced by agent-coder
│   ├── weave-results/             # Code-weaver runs applied to the source tree
│   └── evaluate-results/          # Stage-3 refactor reports (final green test + engine diff attached)
├── projects/                      # Generated source code
├── .opencode/
│   ├── agents/                    # OpenCode agent definitions
│   └── skills/                    # Architecture, stack, coding, testing, and AST guidance
│       ├── tester-framework/      # Language/framework testing skills + run-test-tool.py
│       ├── ast-dispatcher/        # Language detection and AST executable dispatch
│       ├── code-weaver-dispatcher/ # Language detection and code-weaver dispatch
│       ├── read-write-file-ddd/   # Blackboard file writers (red-phase, architect, etc.)
│       ├── architect-practices/   # DDD and architecture skills
│       ├── tech-stack/            # Technology selection and migration skills
│       └── java-standard-best-practices/
├── .github/
│   ├── agents/                    # Copilot agent profiles
│   └── skills/                    # Copilot-accessible skills (mirrored layout)
└── mcp_server/                    # MCP server images for project scaffolding
```

## Prerequisites

- Python 3.9 or newer.
- One configured agent backend:
  - [OpenCode](https://opencode.ai/) with access to the configured model, or
  - [GitHub Copilot CLI](https://docs.github.com/en/copilot) available as `copilot`.
- Docker when using the containerized MCP scaffolding servers.
- The build tools required by the generated projects, such as Maven/Gradle, Node.js, or another stack selected during planning.
- Java 21 if you use the bundled Java AST extractor.

The orchestrators themselves use the Python standard library. OpenTelemetry packages are optional.

Configure the AST extractor location in `.env`:

```dotenv
AST_TOOL_ROOT=<path-to-extractor-project>
AST_JAR_NAME=<extractor-jar-name>
```

## Quick start

### 1. Add a business description

Create a Markdown file in `seed/`. The first level-1 heading is used to derive the default output directory name.

The repository includes `seed/001_description.md`, an example core banking platform covering Accounts, General Ledger, Payments, Treasury/FX, and Compliance/Risk.

### 2. Run with OpenCode

```bash
python3 orchestrators/orchestrator_opencode.py --seed seed/001_description.md
```

### Or run with GitHub Copilot CLI

```bash
python3 orchestrators/orchestrator_github.py --seed seed/001_description.md
```

To keep polling for newly emitted tasks, add `--watch`:

```bash
python3 orchestrators/orchestrator_github.py --seed seed/001_description.md --watch
```

By default, output is written below `projects/<seed-title>/`. Use `--output` to choose another location:

```bash
python3 orchestrators/orchestrator_opencode.py \
  --seed seed/001_description.md \
  --output projects/my-banking-platform
```

Each domain is generated as a separate project:

```text
projects/my-banking-platform/
└── services/
    ├── accounts/
    ├── general-ledger/
    ├── payments/
    ├── treasury-fx/
    └── compliance-risk/
```

## Common options

Both orchestrators expose the same main pipeline options:

| Option | Description |
| --- | --- |
| `--seed FILE` | Business description to process. Defaults to the first Markdown seed. |
| `--output DIR` | Root directory for generated projects. |
| `--force` | Regenerate existing DDD discovery and context-map reports. |
| `--watch` | Poll the queue continuously. |
| `--interval N` | Seconds between polls in watch mode; default: `5`. |
| `--timeout N` | Seconds before an agent run is stopped; default: `900`. |
| `--limit N` | Stop after N tasks; `0` means no limit. |
| `--verify MODE` | Verification mode: `none`, `typecheck`, or `build`; default: `typecheck`. |
| `--verify-timeout N` | Seconds allowed for each verification command; default: `300`. |
| `--emit FILE ...` | Validate and enqueue task JSON files without running the pipeline. |

OpenCode also supports `--no-auto` to omit automatic approval. The GitHub backend supports `--copilot-bin` and `--allow-tool`; their defaults can also be set with `COPILOT_BIN` and `COPILOT_ALLOW_TOOL`.

Run `python3 orchestrators/orchestrator_opencode.py --help` or `python3 orchestrators/orchestrator_github.py --help` for the complete CLI reference.

## The blackboard task model

A task is a small JSON contract containing everything an agent needs to perform one unit of work:

```json
{
  "id": "T0-023",
  "targetAgent": "agent-container",
  "stage": 0,
  "dependsOn": ["T0-005"],
  "path": "db/migrations/V1__store_setup.sql",
  "kind": "bootstrap",
  "layer": "root",
  "feature": null,
  "export": "treasury-fx-store-setup",
  "intent": "Create the PostgreSQL store setup for the treasury-fx bounded context.",
  "project": "treasury-fx"
}
```

Important conventions:

- IDs use `T<stage>-<number>`, for example `T0-023` or `T2-104`.
- `dependsOn` references earlier task IDs and defines the execution graph.
- `path` is relative to the domain project root, not the repository root.
- `project` is the domain slug and determines the generated project, filename suffix, and execution grouping.
- New queue filenames follow `<id>-<project>.json`, such as `T0-023-treasury-fx.json`.

Tasks can be emitted manually through either backend:

```bash
python3 orchestrators/orchestrator_opencode.py --emit /tmp/tasks/T0-023.json
```

The orchestrator validates the complete schema before writing to `blackboard/queue/`; task files should not be copied into the queue directly.

## Scheduling and failure handling

At the start of a pass, the orchestrator loads and validates the queue, builds an in-memory dependency graph, and places ready tasks in a priority heap. Tasks are ordered by:

```text
(stage, project, path)
```

This preserves stage order while keeping work from the same domain together. Completing a task updates dependent tasks immediately, without rescanning the queue.

Invalid tasks and failed executions are moved to `blackboard/error/` with an `error` field explaining the reason. Dependents of failed work are quarantined when they can no longer be resolved. Successful tasks move to `blackboard/complete/` using the same filename.

Stage 2 supports up to three implementation attempts when verification fails. The verification output is returned to the coder as focused feedback for the next attempt.

## Verification

Verification detects the generated project's build system and runs an appropriate check:

- `typecheck` performs a lightweight compile or static check where supported.
- `build` runs the detected build command.
- `none` disables verification.

After the queue drains, each discovered domain project is verified again unless verification is disabled. Build tools and dependencies must be available locally for these checks to succeed.

## Optional telemetry

Tracing is disabled by default. To enable it, configure an OTLP endpoint in the environment or in a local `.env` file:

```dotenv
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=blackboard-evaluator
```

The OpenTelemetry SDK and an OTLP HTTP or gRPC trace exporter must also be installed. If the endpoint or packages are missing, the orchestrators continue normally without tracing.

## Customizing the system

- **Business input:** add or replace files in `seed/`.
- **Agent behavior:** edit `.opencode/agents/` and the matching `.github/agents/` profiles.
- **Test conventions:** update `agent-tester` and the skills under `tester-framework/<language-framework>/`.
- **Red-phase record:** change `read-write-file-ddd/writer-red-phase/write-red-phase.py` or `orchestrators/dispatchers.py`.
- **AST extraction:** add builders under `ast-dispatcher/builders/` and configure `AST_TOOL_ROOT`/`AST_JAR_NAME` in `.env`.
- **Code weaving:** add weavers under `code-weaver-dispatcher/builders/` and configure `WEAVER_TOOL_ROOT`/`WEAVER_JAR_NAME` in `.env`.
- **Architecture rules:** update the skills under `.opencode/skills/architect-practices/`.
- **Technology choices:** update `.opencode/skills/tech-stack/` and the MCP scaffolding configuration.
- **Coding standards:** update the relevant language and framework skills.
- **Queue behavior:** change `orchestrators/task_queue.py` and `orchestrators/tdd_engine.py`; both backends reuse them.

Keep both backends' agent profiles aligned when changing the workflow.

## Project status and safety

This is an experimental evaluator and orchestration project, not a guarantee of production-ready generated software. Agent runs can create and modify files, install project dependencies through their workflows, and execute build commands. Review generated code, migrations, security decisions, and test results before using them in a real environment.
