# Blackboard Evaluator Project

An experimental, agent-driven software factory that turns a business description into a domain-oriented codebase.

The orchestrator reads a seed document, discovers bounded contexts, plans the architecture, creates database and application tasks, and coordinates specialized agents to scaffold, test, implement, and evaluate each unit of work. Agents do not call one another directly: they communicate through validated JSON files stored on a local **blackboard**.

The same workflow can run with either **OpenCode** or **GitHub Copilot CLI**.

## What the project does

- Applies Domain-Driven Design (DDD) to split a business description into bounded contexts.
- Creates an execution strategy and a separate project for each discovered domain.
- Selects persistence technologies and queues database migration tasks.
- Breaks application work into dependency-aware test, code, and evaluation tasks.
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
      Validated blackboard queue
              |
              v
 Dependency-aware, domain-grouped execution
              |
              v
 Generated projects under projects/<name>/services/
```

### Processing stages

| Stage | Agent | Responsibility |
| --- | --- | --- |
| 0 | `agent-container` | Generate the domain project scaffold and database artifacts. |
| 1 | `agent-tester` | Create tests for one implementation-ready unit. |
| 2 | `agent-coder` | Implement the unit described by the task. |
| 3 | `agent-evaluator` | Inspect and refactor the implementation. |

Before these stages, two specialists create the DDD artifacts:

- `domain-boundary-discovery-specialist` writes one domain boundary file per subdomain.
- `domain-context-mapping-specialist` writes the corresponding context maps.
- `agent-architect` writes execution strategies and decomposes the work into tasks.
- `agent-database-architect` selects storage technologies and queues database tasks.

## Repository layout

```text
.
├── orchestrator_opencode.py       # Shared pipeline and OpenCode backend
├── orchestrator_github.py         # GitHub Copilot CLI backend
├── telemetry.py                   # Optional OpenTelemetry integration
├── seed/                          # Input business descriptions
├── blackboard/
│   ├── domain/                    # Discovered domain boundaries
│   ├── context-map/               # DDD context maps
│   ├── queue/                     # Tasks waiting to run
│   ├── complete/                  # Completed tasks and execution strategies
│   └── error/                     # Invalid or failed tasks with error details
├── projects/                      # Generated source code
├── .opencode/
│   ├── agents/                    # OpenCode agent definitions
│   └── skills/                    # Architecture, stack, and coding guidance
├── .github/
│   ├── agents/                    # Copilot agent profiles
│   └── skills/                    # Copilot-accessible skills
└── mcp_server/                    # MCP server images for project scaffolding
```

## Prerequisites

- Python 3.9 or newer.
- One configured agent backend:
  - [OpenCode](https://opencode.ai/) with access to the configured model, or
  - [GitHub Copilot CLI](https://docs.github.com/en/copilot) available as `copilot`.
- Docker when using the containerized MCP scaffolding servers.
- The build tools required by the generated projects, such as Maven/Gradle, Node.js, or another stack selected during planning.

The orchestrators themselves use the Python standard library. OpenTelemetry packages are optional.

## Quick start

### 1. Add a business description

Create a Markdown file in `seed/`. The first level-1 heading is used to derive the default output directory name.

The repository includes `seed/001_description.md`, an example core banking platform covering Accounts, General Ledger, Payments, Treasury/FX, and Compliance/Risk.

### 2. Run with OpenCode

```bash
python3 orchestrator_opencode.py --seed seed/001_description.md
```

### Or run with GitHub Copilot CLI

```bash
python3 orchestrator_github.py --seed seed/001_description.md
```

To keep polling for newly emitted tasks, add `--watch`:

```bash
python3 orchestrator_github.py --seed seed/001_description.md --watch
```

By default, output is written below `projects/<seed-title>/`. Use `--output` to choose another location:

```bash
python3 orchestrator_opencode.py \
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

Run `python3 orchestrator_opencode.py --help` or `python3 orchestrator_github.py --help` for the complete CLI reference.

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
python3 orchestrator_opencode.py --emit /tmp/tasks/T0-023.json
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
- **Architecture rules:** update the skills under `.opencode/skills/architect-practices/`.
- **Technology choices:** update `.opencode/skills/tech-stack/` and the MCP scaffolding configuration.
- **Coding standards:** update the relevant language and framework skills.
- **Queue behavior:** change the shared implementation in `orchestrator_opencode.py`; the GitHub backend reuses it.

Keep both backends' agent profiles aligned when changing the workflow.

## Project status and safety

This is an experimental evaluator and orchestration project, not a guarantee of production-ready generated software. Agent runs can create and modify files, install project dependencies through their workflows, and execute build commands. Review generated code, migrations, security decisions, and test results before using them in a real environment.
