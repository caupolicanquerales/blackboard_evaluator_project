# Blackboard Evaluator Project

An experimental, agent-driven software factory that turns a business description into a domain-oriented codebase.

The orchestrator reads a seed document, discovers bounded contexts, plans the architecture, creates database and application tasks, and coordinates specialized agents to scaffold, test, implement, and evaluate each unit of work. Agents do not call one another directly: they communicate through validated JSON files stored on a local **blackboard**.

The same workflow can run with either **OpenCode** or **GitHub Copilot CLI**.

Contents:

- [What the project does](#what-the-project-does)
- [How it works](#how-it-works) — pipeline, stages, agents
- [Core mechanisms](#core-mechanisms) — planning, red phase, weaving, test gate, assembly, attempts, cost, observability
- [Gauntlet](#gauntlet-engine-regression-suite) — pre-flight for the engine itself
- [Repository layout](#repository-layout) · [Prerequisites](#prerequisites) · [Quick start](#quick-start) · [Options](#common-options)
- [The blackboard task model](#the-blackboard-task-model) — including the `ast_hints` contract table
- [Scheduling and failure handling](#scheduling-and-failure-handling) · [Verification](#verification) · [Telemetry](#optional-telemetry)
- [Customizing the system](#customizing-the-system) · [Project status and evaluation runs](#project-status-and-evaluation-runs)

## What the project does

- Applies Domain-Driven Design (DDD) to split a business description into bounded contexts, then drives every unit through a strict TDD loop (red → green → refactor) — the pair exists to make hallucination structurally impossible: DDD pins *what to build* as machine-checkable contracts before any code exists, TDD proves *what is true* through artifacts no agent can talk over.
- No agent claim is ever a completion criterion: every phase transition is verified by a deterministic tool witness (revalidated red records, weaver results, engine-run verdicts, boot gates, terminal suite verdicts).
- Creates an execution strategy and a separate project for each discovered domain.
- Selects persistence technologies and queues database migration tasks.
- Breaks application work into dependency-aware test, code, and evaluation tasks, each carrying an **`ast_hints` contract table** (package, supertypes, pinned collaborators, exact method signatures) that is validated at emit time — contradictory or under-specified plans are rejected before any agent session is billed.
- Runs each new test in **red phase**, records the result, and extracts **AST context** for the target class/method to guide the coder. A missing red record is re-derived deterministically by the engine; a session is never paid to re-observe a build result.
- Batches both stage-1 testers and stage-2 coders: one session writes up to four same-domain units, sharing a budget that scales with the batch.
- Processes tasks with an in-memory dependency graph instead of repeatedly searching the queue after every task.
- Groups ready work by domain to improve execution locality and make logs easier to follow; a domain's green test gate runs as **one wave** once all payloads are woven, and verdicts are memoized by source-tree fingerprint.
- Attributes green-gate failures to the owning unit — including **runtime bean-graph demands** — so a unit is never charged for a peer's missing bean.
- Gives every task a stable, readable filename such as `T0-023-treasury-fx.json`.
- Validates task schemas and dependencies, quarantines invalid work, and records failures; quarantined tasks can be restored with `--retry`.
- Audits test-import closure before draining, so a domain that can never go green stops the run early instead of burning agent calls.
- Enforces per-agent tool-call budgets, kills runaway sessions, caps the number of *billed* sessions per unit through an attempt ledger with honest grant accounting, and keeps every agent profile and skill document under 450 tokens.
- Runs independent domains concurrently with `--parallel` while preserving stage order.
- Boots the generated application through a stage-4 assembly gate backed by the scaffold's own smoke test — with structural probes that refuse a vacuous green (composition-root visibility, request-path evidence, base-document substitution discipline with its test-witnessed exemption, config documents in their kind's native form) and a terminal tree verdict at every exit.
- Ships a **gauntlet** — a 231-case regression suite (174 engine decisions + 57 skill scripts) that pins every incident class observed during live drains — and a read-only board status tool with token rollups.
- Supports optional compilation/build checks and OpenTelemetry tracing.

## How it works

Two disciplines run the machine. **DDD decides WHAT to build** — subdomains,
invariants, ubiquitous language — and pins them as machine-checkable contracts
*before any code exists*. **TDD proves WHAT IS TRUE about the code** — a test frozen
before its implementation is the only voice a unit gets, and the party judged by a
test can never edit it. Between them, no agent claim is ever a completion criterion:
every stage transition is a deterministic artifact produced or re-verified by tools.

```text
Business description (seed/*.md)
              |
              v
  ==========  DDD: decide WHAT to build, as contracts checkable by machines  ==========
              |
   Domain boundary discovery      subdomains, invariants, ubiquitous language;
              |                   uncertainty becomes an explicit Assumption or
              v                   an operator decision - never a silent invention
        Context mapping           relationships, boundary protection, cross-domain flows
              |
              v
   Execution strategy per domain  layers, ports/adapters, persistence, and an
              |                   UNCONDITIONAL observability floor (audit, step
              v                   logs, correlation, metrics, export)
  Database planning + stage 0 tasks
              |
              v
  Application task decomposition  per unit: a stage-1 TEST + stage-2 CODE +
              |                   stage-3 REFACTOR triple, all pinned to the SAME
              v                   ast_hints contract table (prose is never the only truth)
   Plan validation + emit gates   rules (a)-(x): contradictions between artifacts
              |                   that freeze at write time die HERE, at zero
              v                   billed sessions - never after a test is frozen
              |
  ==========  TDD: prove WHAT IS TRUE, without ever asking the agent  ==========
              v
   +--------------------------- per unit, dependency-ordered --------------------+
   |  RED      tester writes the failing test at its OWN path (rule (w)); the    |
   |           engine re-runs it and revalidates the record (or derives it       |
   |           for free) - a PASSING pre-implementation test is refused          |
   |    v    AST      context extracted from the REAL source tree                |
   |    v    GREEN    coder emits a PAYLOAD (never edits source); the WEAVER     |
   |           splices it; the wave gate runs the frozen test - ONE build per    |
   |           tree state, verdicts memoized by fingerprint. Loop-backs: a       |
   |           tool-reject bounces the payload FREE (no attempt consumed); a     |
   |           red verdict is charged to the OWNING unit, never a bystander      |
   |    v    REFACTOR evaluator cleans the unit; the SAME frozen test anchors it |
   +--------------------------------------+--------------------------------------+
                                          v
    Stage-4 assembly gate        boot over the real context; structural probes
              |                  refuse the vacuous green; a broken delivered
              v                  contract REOPENS its owner (not the victim it broke)
    Terminal suite gate          the WHOLE delivered suite re-run at every exit
              |                  on a quiet board - yesterday's green is not evidence
              v
  Generated projects under projects/<name>/services/
```

### Processing stages

| Stage | Agent / Tool | Responsibility |
| --- | --- | --- |
| 0 | `agent-container` | Generate the domain project scaffold and database artifacts. |
| 1 | `agent-tester` | Write tests for implementation-ready units (up to four per batch session), run the red-phase check, and record the result. |
| - | `ast-dispatcher` | Extract AST context for the target class/method into `blackboard/ast-context/<id>.json`. |
| 2 | `agent-coder` | Emit the payload (pure method body + creation metadata) for the unit described by the task, guided by the test, AST context, and `ast_hints` table; up to four units per batch session. |
| - | `code-weaver-dispatcher` | Splice the coder payload into the source tree and record `blackboard/weave-results/<id>.json`. |
| 3 | `agent-evaluator` | TDD refactor: audit clean code, architecture, performance, and security while keeping the recorded test green; record `blackboard/evaluate-results/<id>.json`. |
| 4 | `agent-assembly` | Application assembly: boot the generated application. Stack-agnostic — detects the framework, loads its skill from `assembly-framework/`, closes runtime wiring gaps in production sources only, and re-runs the scaffold smoke test until the application starts. The orchestrator verifies the boot with its own deterministic gate; there is no agent artifact to trust. |

Before these stages, two specialists create the DDD artifacts:

- `domain-boundary-discovery-specialist` writes one domain boundary file per subdomain.
- `domain-context-mapping-specialist` writes the corresponding context maps.
- `agent-architect` writes execution strategies and decomposes the work into tasks, including each unit's `ast_hints` contract table.
- `agent-database-architect` selects storage technologies and queues database tasks.

### How the TDD is implemented — the loop per unit

Every business obligation reaches the drain as a **triple of tasks pinned to one
contract**: a stage-1 TEST task, a stage-2 CODE task, and a stage-3 REFACTOR task, all
three describing the same unit and carrying the **identical `ast_hints` table**
(package, supertypes, collaborators pinned to their producing tasks, exact method
signatures). The loop then runs classic red → green → refactor, but each phase belongs
to a different agent and is verified by a different machine, so no single session ever
grades its own homework:

1. **RED (stage 1).** The tester writes ONE failing test at its task `path` — which is
   its own test file, never the production file (rule (w)) — asserting only against the
   pinned table, and runs it through `run-test-tool.py`, piping the verdict into the
   official writer. A red is only valid if the engine can RE-VERIFY it: the record must
   show the test ran and failed with a `compile_error` (missing symbol — the
   implementation genuinely does not exist yet) or an `assertion_failure`; a test that
   PASSES before implementation is rejected, and a missing record is re-derived
   deterministically at zero cost (the engine refuses to pay a session to re-observe a
   build result it can produce itself). Once the test is frozen, the AST dispatcher
   extracts the real context of the target file so the next phase implements against
   the tree as it is, not as remembered.
2. **GREEN (stage 2).** The coder never touches a source file: it emits a *payload* —
   pure method bodies plus creation metadata, one JSON per unit — and the **code
   weaver** splices it into the pinned surface, recording the result. A rejection by
   the weaver tool itself is a bounce back to the coder that consumes **no attempt**
   (a session spent on a tool rejection is pure waste). Verification is the wave gate:
   when the domain's payloads are woven, the engine runs the frozen tests ONCE per tree
   state — a shared build, verdicts memoized by source-tree fingerprint — and
   normalizes each outcome through the same tool that read the red phase.
3. **REFACTOR (stage 3).** The evaluator audits and cleans the implementation under the
   same recorded test: it may change bodies and structure, must keep the green verdict
   (re-run before and after), may not touch the test contract, and its diff is recorded
   for attribution to answer later.
4. **BOOT (stage 4) and the terminal suite gate.** Assembly proves the application
   actually starts over its real bean graph, and on a quiet board the engine re-runs
   the WHOLE delivered suite — a completion claim never survives on yesterday's
   verdicts.

The asymmetry that makes this anti-hallucination, not just test-first: **the judged
cannot edit the judge.** The coder cannot edit the test that gates it; the evaluator
cannot edit the test that anchors it; if the contract itself is wrong, the fix must
happen where it is still cheap — the emit gate refusing the plan, or a deterministic
reopening of the OWNING unit, never a silent edit of a frozen artifact.

### DDD + TDD as one hallucination defense

A language model hallucinates in three directions, and each has a mechanical answer
in this pipeline:

| Hallucination channel | Closed by |
| --- | --- |
| **Inventing the domain** (facts not in the description) | The DDD tier: discovery must trace every entity, bound and status literal to the seed VERBATIM or record the deviation as a named Assumption; open questions surface as operator decisions, never silent choices. |
| **Planning a contradiction** (artifacts that freeze against each other) | The emit gates, rules (a)–(x): every duty owned by a path, prose never fighting the table, request-encoding agreement, signalling returns describing both branches, consumer closure, the correction value axis, promised mechanisms scheduled as duties, test artifacts separate from production files, handler registrations the framework can actually execute. A refused plan costs one rewrite; the same plan discovered mid-drain costs a whole run. |
| **Claiming success that did not happen** | The TDD tier: no agent report closes a unit. Each transition needs a machine witness — a revalidated red record, a weaver result, a wave verdict from the engine's own run, an evaluate diff with the test re-greened, a boot gate re-run by the orchestrator, and the terminal suite verdict at every exit. Even the cost rollup is read from backend session events, not from what agents say they did. |

And when reality breaks a promise anyway, the loop repairs at the right seam:
verdicts are attributed to the producing unit, blame on foreign files follows
`error_locations` to the true owner, a unit whose *peer* closed a type it must stub is
deferred while the closer is reopened, a cross-stage regression reopens the contract's
OWNER rather than charging the bystander whose test turned red — and every such routing
is pinned by a gauntlet case, so a fixed class stays fixed.

## Core mechanisms

### Plan-time contracts (`ast_hints`)

Every stage-1/stage-2 task may carry an `ast_hints` table — `package`, `implements`, `dependencies` (each collaborator pinned to the task that produces it), and `methods` (exact signature + return spelling). The board validates the table shape at emit time, and a **cross-task gate** rejects any plan that pins a collaborator whose own table does not spell the surface its consumers use. A tester writes assertions only against this table; a coder creates or edits exactly the pinned surface. Because the table is injected directly into the tester's and coder's messages, agents do not hunt the board for filenames.

The `FINAL-EVALUATION-seed002.md` §6 roadmap has since **shipped**: plan-content roots are now dead on arrival, refused at emit by stack-neutral plan-validity rules (full contracts live in `task-decomposition-dag`; every refusal class is pinned in the gauntlet): (a) every file duty an intent assigns must be owned by a task's `path`; (b) intents that externalize values imply a scheduled config unit; (c) pinned request-parameter types must agree with the body encoding the paired test mandates; (d) null-rejecting intents must table their initial-state `semantics`; (e) **prose must not fight the table** — an intent asserting an unconstructible shape (`private constructor` / `utility class`) while the table binds instance members, or calling a pinned producer's member in static form (`Type.member(`) while that table binds it as instance, are refused as impossible pairs (the 2026-11-12 drain froze its whole domain behind exactly this contradiction); (f) provider closure — every type a table constructor injects must have a named provider duty in the DAG; (g) composition-root visibility — the entry point must be the ancestor of every component package or declare its coverage as a scheduled duty; (h) config-surface completeness — every document the paired test pins, an enabled runtime reader's datasource keys in that reader's own document, and the stack's test-profile activation route; (i) stream egress — every published port names its consumer unit or declares the out-of-process boundary; (j) step-log claim coverage — every step log the execution strategy plans must be claimed VERBATIM by exactly one stage-2 unit, and the strategy's observability floor itself is unconditional (below); (k) consumer closure / source reachability — a unit whose table publishes a stream must be pinned by a CONSUMER (a wiring unit's own pin counts as production, not consumption) or declare its out-of-process boundary per unit (2026-11-16 F1: the reordering service was a registered island and the seed's core rule never ran); (l) shared literals have one owning unit — consumers pin the owner instead of re-spelling values; config readers whose URL forms differ need distinct keys; (m) signalling returns — a tabled `boolean`/`Mono<Boolean>` method without `semantics` naming both outcomes is refused (F2: the unowned false branch dropped samples while the API lied 202); (n) one registration mechanism per product — a type both factory-produced and self-registration-claimed is refused (F8); (o) a unit executing SQL/DML is refused when its paired test intent lacks the REAL-SUBSTRATE demand — the embedded substitute executing the actual migration DDL: a mocked database client verifies call shape, never schema fit (2026-11-16 second drain N1 — every production audit write died on `NULL not allowed for "AUDIT_ID"` while 186 tests stayed green); (p) an inbound adapter without one end-to-end request-path slice task is refused (the boot proves the graph resolves; only a driven request proves controller, store and schema agree); (q) at-least-once inbound over an append-only revision chain needs a named dedup identity on the receiving contracts or a strategy at-most-once segment (a network retry must not mint a domain revision); (r) a config unit enabling a migration runner must spell the PACKAGED (classpath:) location, never a CWD-relative `filesystem:` path into the project — portability is refused at EMIT only and never relitigated at the assembly gate against the config unit's own frozen test (the 2026-11-16 T4 livelock); (s) correction axis — a chain that dedups inbound over an append-only history that speaks of corrections must state the VALUE-AXIS decision beside the identity (payload inside, or excluded plus a named retry-vs-correction discriminator) and table both resend classes as test duties (PART III G2: a value-excluding identity silently reclassified every value-correction as a duplicate no-op while (q) stayed satisfied); (t) a strategy-promised mechanism ("... via \<mechanism\>") must appear UNNEGATED as some unit's install duty (dependency + enablement at wiring/boot) — the emit gate refuses the promise/duty disagreement using the strategy's own token, and the concrete mechanism shape belongs to the tech-stack skill (PART III G3); (u) no acknowledged outcome is unmetered — every step log the floor promises pairs with a metric or an explicit `uncounted_steps` reason, and every failure/drop outcome contracted in tabled `semantics` pairs with a counting meter or a declared `uncounted_failures` posture (PART III G4: audited-but-uncounted failures are how a losing pipeline reports a healthy dashboard); (v) config format follows the artifact kind — KEY/VALUE pairs tabled in a config unit are SEMANTIC PROPERTY PATHS, never a file layout; the runtime artifact is serialized in the native form of its file kind per the tech-stack skill (structured documents nest, flat key-value kinds spell dotted keys), and the assembly gate re-serializes a mismatched delivered document (shape moves; values and loader-based tests never do); (w) a stage-1 test task owns a test file — the tester writes its frozen test AT the task `path`, so a test task sharing an implementation task's path is refused at emit: one file cannot hold both the frozen test and the unit later woven over it, and a test class under the production root never sees the test-scoped dependencies (2026-11-17: every tester task of a 57-task plan was emitted on the production path; the import-closure guard stopped the drain at the first red close-out, zero agent sessions wasted beyond the plan itself); (x) a mapped inbound handler names the ONE registration mechanism its framework can execute — the stack's handler marker on its own class or a functional router owned by the wiring unit; forbidding the marker while the factory alone registers boots green and answers 404 (WebFlux maps only annotated classes — the 2026-11-17 e2e slice caught the impossible pair), refused at emit for the planned language. The assembly gate carries the matching delivered-time probes: request-path evidence in the delivered test tree, no embedded substitute spelled in the BASE config document (literal or placeholder-default) UNLESS a delivered test asserts that exact value — a test-witnessed base default is a planned, disclosed posture, and the probe goes silent for it (2026-11-17: the assembler obeyed the unwitnessed rule, broke the config unit's frozen test, and the terminal suite gate reopened the owner to undo it — rule (r)'s livelock doctrine applied to VALUES), and structured config documents spelled in their kind's native serialization (rule (v)) — with one sanctioned ADDITIVE route for legacy trees (create the missing slice, never edit an existing test).

### Red-phase checks and AST context extraction

Stage 1 is not just "write a test". The tester agent:

1. Loads the matching `tester-framework/<language-framework>/SKILL.md` (for example `java-junit5`).
2. Writes the test at the task `path`.
3. Runs only that test through `tester-framework/run-test-tool.py`, which parses the output and classifies it as `passed`, `compile_error`, `assertion_failure`, or `not_run`.
4. Persists the result with `read-write-file-ddd/writer-red-phase/write-red-phase.py` as `blackboard/red-phase/<id>.json`. The file must contain `{"executed": true}` for the orchestrator to proceed.

When at least four stage-1 tasks of the same domain still have no test file on disk, the engine opens a **tester batch session**: one `agent-tester` run writes up to four units, sharing a budget (3 calls for the first unit plus 4 per additional one) whose session timeout scales with the batch. Each unit still runs its own red probe, and the batch message carries each unit's collaborator table so testers share the cold start a per-unit session pays twenty times over. If the batch writes no test, the tasks fall back to ordinary per-task sessions; a thin batch red (passed, unrun, malformed) never quarantines the siblings.

If a test file is on disk but its red record was lost (a session killed mid-unit), `dispatchers.derive_red_phase()` re-runs the scoped command through `run-test-tool.py` and persists the verdict through the official writer — zero sessions spent re-observing a build result the engine can produce itself. A genuinely wrong red still falls through to a real session, because the re-derived record passes the same validation gate.

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

For Java/Spring Boot projects, the executable is the fat JAR located by `AST_TOOL_ROOT` and `AST_JAR_NAME` in `.env`. The bundled Java extractor is at `ast_tools/ast_extrator_java`; a fresh clone has no `target/` directory, so the dispatcher builds it with Maven on first use, within `TOOL_BUILD_TIMEOUT` seconds (default `900`). Point `.env` to the extractor you want to use.

A dispatcher failure is logged but does not block `agent-coder`; the context is treated as optional guidance.

### Green-phase code weaving

Stage 2 is not just "write the implementation": `agent-coder` never touches production code. It loads the skills from `coder-framework/` — the language's standard-best-practices base, then the framework overlay that wins on conflict — and records the pure method body and return type (`returns`) in `blackboard/coder-changes/<id>.json` (via `read-write-file-ddd/writer-coder-changes/write-coder-changes.py`, which sets `executed: true`). The orchestrator then runs the weaver as part of the stage 2 verification gate, before the build/test command:

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

Two safeguards keep repeated weaves clean:

- **Weave baseline**: before the first weave of a unit, the target file is snapshotted into `blackboard/weave-baseline/<id>/`. Before a *new* payload re-weaves the same file, the engine restores the pre-weave state, so retry payloads cannot merge onto the previous splice and accumulate duplicate constructors or vestigial methods. Cache hits (unchanged payload) never reach a re-weave.
- **Payload rejects don't burn attempts**: when the rejection comes from the weaver tool itself (the payload does not parse, no builder matched, unsupported grammar), the reason is prefixed and bounced back to the coder without counting a TDD attempt — the unit's code never ran, and a session on a tool rejection is pure waste. Genuine compile/assertion failures still consume attempts.

Coder batching mirrors the tester batching: when at least four stage-2 tasks of the same domain still have no payload, one `agent-coder` batch run produces up to four units (4 calls for the first plus 3 per additional), and if the batch writes no payload the tasks fall back to per-task sessions.

### Green-phase test gate

Immediately after weaving, the orchestrator re-executes the tester's scoped test command through the shared `tester-framework/run-test-tool.py` — no agent involvement. The gate is not run per unit: a woven task defers its gate while sibling payloads of the domain are still pending, so **one wave of full builds decides the whole domain** against a complete source tree, instead of one build per unit where every failure belongs to a peer that never ran.

Before running, the engine deterministically adds missing same-project imports to test files (a tester can reference a production type in another package without importing it; an added import never changes behavior). The name scanners read a **comment- and string-stripped view** of each file — an identifier mentioned in prose is not an import demand (an earlier build inserted a classpath-colliding `A` into a production file because a comment said "A lone late sample"). FQN resolution uses an **external type index** built once per build manifest and cached at `blackboard/external-index.json`.

The command is read from the `command` key that `write-red-phase.py` records in `blackboard/red-phase/<id>.json`; legacy records without a command get it rebuilt from the stage-1 task path for the detected framework. The verdict — pass or fail — is memoized in `blackboard/gate-cache/<id>.json` keyed by a fingerprint of the coder payload and both source trees: while nothing changes, the cached verdict is reused and the suite is not re-run. Runner output is normalized per stack so wave failures arrive **named with messages** (e.g. Surefire console summary lines are rewritten to `Class.method:line » Kind message`); the engine reads only normalized fields and never parses a toolchain's text. Gate outcomes:

| Result | Orchestrator behavior |
| --- | --- |
| `status: passed` | continue to the build gate, then mark the task complete (stage 3 `agent-evaluator` becomes ready) |
| `assertion_failure` / `compile_error` / `error` | retry the stage 2 coder with the compact failure log (up to `MAX_TDD_RETRIES` = 3 attempts, subject to the attempt ledger) |
| `not_run` (silent exit-0, or a `&&`/`$VAR` command refused by the argv-only guard) | treated as failure and retried: an unexecuted suite never passes the gate |
| still failing after 3 attempts | the task moves to `blackboard/error/` and its dependents are quarantined |
| no `command` recorded and none derivable from the stage-1 path | the gate is skipped with a warning; the build gate still applies |
| classification | patterns cover Maven/Surefire, Gradle, Jest/ts-jest, pytest, unittest, `go test`, and cargo; the tool ships its own suite in `run-test-tool-tests.py` |

**Runtime bean-graph attribution.** A Spring context boot can fail because of a bean another unit is supposed to provide. The runner normalizes such context-boot demands into structured `bean_demands`; the engine then:

- **defers** the booting unit while a pending peer owns the demanded bean (its payload stays woven — reverting it would open a hole in the shared test tree for the whole domain);
- applies the **materialized-bean rule**: once the demanded bean's *class* is on the tree, the failure is a registration gap someone can write in their own file (the plan's wiring unit) — the booting unit is charged instead of deferred, or nineteen innocent units deadlock on one boot failure;
- **charges** only own-bean or ownerless demands, capped and honestly recorded. Wave verdicts carry the attribution fields.

**WOVEN-CLEAN quarantine.** When a unit finally quarantines, the engine reverts only the payloads the evidence proves poisonous. An *adjudicated* `assertion_failure` — the module compiled and the suite completed with the payload woven — keeps that payload in the tree; blanket-reverting failed units was deleting a type ten peers import and freezing an entire domain.

**Rollback may not hole the delivered tree.** When a quarantine does revert its payload, the engine scans the domain's NON-test sources for references to the deleted artifact: consumers OWNED by a completed unit are reopened to their owner (their next gate defers at zero bill while the symbol's owner waits in `error/`, and the queue stops lying about being empty); consumers NOBODY owns (assembly-era files) are NAMED — a `[DANGLING-CONSUMERS: ...]` note in the pass log and appended to the quarantine record the operator reads. Without this, a quarantine rollback deleted a class a completed wiring file still imported, the delivered tree stopped compiling, and the board still reported 89/96 + boot green (seed-002 rerun, 2026-11-12 17:11).

Stage 3 reuses the same mechanism: `agent-evaluator` refactors against the test command recorded in `blackboard/red-phase/<T1-id>.json` (resolved through the task `dependsOn` chain), re-runs it through `run-test-tool.py` after every step, and persists an `evaluate-results` artifact via `writer-evaluate-results.py` — which refuses to write when the final test is not green. The hand-off back to the orchestrator is deterministic: (1) `evaluate_result_problem` checks that `blackboard/evaluate-results/<id>.json` exists, is `executed`, and reports `final_test.status == "passed"`; (2) the stage-3 verify step runs the final **global** compile/check gate for the domain project (`verify_project`, skipped under `--verify none`); (3) only then is the task moved from `blackboard/queue/` to `blackboard/complete/`. Any step failing sends the task to `blackboard/error/` with the reason. After the green hand-off, the engine appends `engine_diff` to the artifact: a ground-truth unified diff of every production source the session actually changed (computed by `refactor_audit.py` from before/after snapshots, not from the agent's self-reported `changes[]`).

### Import-closure audit and fatal checks

The whole test source set compiles on every run, so a single imported production type without a producer task keeps an entire domain permanently red. Two deterministic checks stop the pipeline before it spends agent runs on an impossible repair:

- Before draining, the pipeline scans each domain's test imports and aborts with a `task closure` error when an import has no producing task. `python3 orchestrators/closure.py` reports those gaps, and `python3 orchestrators/closure.py --emit` queues the missing stage-2 producer tasks (with matching stage-3 evaluators) through the validated queue writer.
- At every drain, recorded red-phase results are scanned for packages imported by tests that no task produces and the scaffold classpath lacks. That is a build-file problem stage 2 is not allowed to edit, so the run aborts with a fatal reason instead of retrying. Stale records from before a build-file rewrite are ignored: fixing the scaffold is enough for the run to continue.

The "known JDK types" inventory is **derived from the installed JDK** (jrt-filesystem probe, cached, with a fallback vocabulary) instead of a hand-enumerated list — a closure gate must not kill a fresh run because some `java.lang` type was never written down.

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

The gate is more than the smoke command — each stack's `STACKS` row carries its structural probes as DATA, and the gate refuses the *vacuous* green (2026-11-13 inspection, PART II):

- **Hollow-boot guard**: the composition root must see the main sources (its package an ancestor-or-self of every main package, or an explicit scan-coverage declaration), AND every context-discovering test (`@SpringBootTest`/slice-style annotation) must sit package-under the entry point. The upwards package search that locates the configuration IGNORES scan directives, so the test half is deliberately NON-WAIVABLE: the only repair is moving the composition root to the shared ancestor (a marker-only "fix" once booted the smoke test green while two slice units stayed unweavable-red forever — live at 13:45).
- **The gate is stage 4's ONLY contract**: a session's recorded `path` is never a completion criterion, because the mandated composition-root repair legitimately MOVES that file (`_missing_artifact_problem` exempts stage 4).
- **Late scheduling**: `ensure_tasks()` re-runs EVERY watch pass and once after a single-pass drain — on a fresh run the `services/` folder only exists mid-drain, and a launch-time-only scheduler silently ended whole drains having never booted the application (13:33 live shape).
- **Terminal tree verdict**: every terminal exit (`[exhausted]`, stuck-fatal, blocked) re-runs the boot gate over the DELIVERED bytes and prints `[tree   ] <slug>: GREEN|RED`; a domain with no completed boot reports `RED - NEVER BOOTED` instead of silence. Cached earlier verdicts and stale `target/` output can no longer be reported as the final state.
- **Config-surface probes**: the delivered-time machine halves of plan rules (v) and the substitute discipline — a structured config document spelled as flat dotted keys is RE-SERIALIZED (shape moves, values never), and a base document carrying the embedded substitute is refused — UNLESS a delivered test asserts that exact base value: a test-witnessed default is a planned, disclosed posture, and ordering the assembler to rewrite it would command it to break a frozen contract (2026-11-17: exactly that happened live; the terminal suite gate caught the red, charged the OWNER, and the owner restored the value at zero billed sessions — the (r) livelock doctrine, now applied to VALUES and pinned X5d/X5e).

The text writer that weaves config artifacts (`code-weaver-dispatcher/builders/_text_write_exec.py`) validates with `safe_load_all`: multi-document YAML — a base document plus each profile document separated by `---` — is a legal, Spring-consumable surface, and a plan that mandates it must stay weavable (a single-document `safe_load` check once made a correct config unit impossible: three burned attempts before the tool, not the plan, was fixed).

The tester agent keeps deciding *which* test command proves the unit red (it needs domain judgment); the orchestrator owns *re-running* it for green (pure mechanics). Both use the same generic script, so the red and green executions are identical commands parsed by identical regexes.

### Session cost budgets and compression

Every assistant turn re-sends the whole transcript, so a session's cost is driven by its number of tool calls. Every prompt therefore states an explicit budget (discovery, mapping and container 10 calls, tester 8, coder 6, evaluator, assembly and architect 12, database 14; a coder batch shares a budget that scales with its unit count, 4 + 3 per extra unit, and a tester batch 3 + 4 per extra unit), and on the Copilot backend a session streaming past twice its budget (plus a slack of 4 calls) is killed mid-run rather than left to burn tokens. Budgets cap one session; the *number* of sessions a unit may bill is capped by the attempt ledger (see [Scheduling and failure handling](#scheduling-and-failure-handling)) and by lifetime weave-reject bounce caps.

Because prompt size multiplies across every turn of every session, **all agent profiles and all skill documents are compressed to at most 450 tokens**, delegating language and framework syntax to the stack skills. Compression regressions — a doc teaching an invented payload key, or an approximate enum where the writer demands the canonical one — are pinned mechanically by the gauntlet's K-section (doc-vs-schema checks), and every writer rejection prints an `--emit-template` hint showing the true contract.

`python3 orchestrators/session_audit.py` reads the local Copilot session records and reports, per agent, the turns, tool calls, and tokens, flagging calls that left the agent's own inputs (skill folder listings, orchestrator or AST-tool source reads, other tasks' records, board-folder listings such as `ls blackboard/coder-changes`, `git`); use `--since-hours`, `--budget-report`, or `--json` to slice the view.

### Board status and observability

`python3 orchestrators/status.py` is a read-only, restart-surviving view of the board:

- queue / complete / quarantine counters, queue by stage, and the most recent completions;
- for every quarantined unit, its attempt-ledger state (budget left, grants used, whether its last failure has been shown to a coder) and quarantine reason — the exact questions the drain answers when relaunched, so the operator sees *why* the board is where it is without reading a log;
- whether an orchestrator process is currently running;
- a **token rollup** read from the backend's own session-state events: sessions, input and output tokens since launch, cost per completed unit, and a watchdog line for the largest single session (a runaway is visible continuously instead of by post-mortem).

Drain logs carry timestamps and a heartbeat so a stalled pass is distinguishable from a slow one.

## Gauntlet: engine regression suite

`gauntlet/` is the pre-flight for the pipeline itself: seconds of compute instead of hours of a live 80-unit drain discovering the same bug at agent-session prices.

```bash
python3 gauntlet/run_gauntlet.py            # skill-script + engine decision suites
python3 gauntlet/run_gauntlet.py --weaver   # + the Java weaver JUnit (needs Maven)
```

| File | Tests | Allowed vocabulary |
|---|---|---|
| `gauntlet/test_skill_scripts.py` | writer payload schema; run-test-tool normalization; multi-document YAML write gate; the sanctioned scaffold tooling (`repin-parent` surefire guardrail) and the skill-law content pins (tester substitute-credentials/aggregate-decode laws, packaged migration directory, composition-root placement check, WebFlux handler-marker law) | **compiler output text lives only here** — this tool owns syntax (57 cases) |
| `gauntlet/test_engine_decisions.py` | attribution, wave sharing, attempt ledger + grants, auto-grant, plan-validity refusals (reserved package segments, phase-order claim skip, consumer closure of published streams, signal-returns-need-semantics, registration XOR, real-substrate adapter pairing, request-path integration slice, ingress idempotency duty, correction value axis, promised-mechanism duty, floor pairing, stage-1 test-artifact path separation, handler-marker registration impossibility), rollback holes, assembly structural probes (incl. request-path evidence, base-document substitution discipline WITH the test-witnessed exemption, config native-format re-serialization), terminal tree verdicts, terminal suite gate + reopen attribution, observability floor + claims | structured fields only — no compiler strings (174 cases) |
| `ast_weaver_tools/.../JavaASTWeaver*Test.java` | weaver grammar (generics, supertypes, static reconcile, idempotency) | Java — it *is* the Java tool |

Two rules keep the engine stack-agnostic: orchestrator modules read only the runner's normalized fields (`status`, `missing_symbols`, `member_demands`, `classes`) and never parse a toolchain's text; and every incident class from the live drains has a pinned case here — silent payload-key drops (W), javac line shapes (G), receiver-vs-enclosing attribution (A/B), scheduling-hole aborts (A5-A6), rebuild storms (C), blind granted attempts and grant livelock (D/E), doc-vs-schema regressions (K, incl. multi-document YAML), red-recovery pins (H), import-repair pins (R), full-tree attribution and sibling-wave gates (A19-A26), contract-regression reopen (A25-A26), prose-vs-table plan refusals (G21-G24), rollback dangling-consumer surfacing and reopen (A27-A28), hollow-boot and slice-discovery structural gates (S1-S5), late assembly scheduling and NEVER-BOOTED terminal verdicts (T1-T5), gate-only stage 4, zombie-id supersede and ledger continuity (U1-U4), the unconditional observability floor and step-log claim coverage (V1-V8). **No merge without a case**: a fix that ships without a fixture here is how next week's incident is born.

## Repository layout

```text
.
├── orchestrators/                 # Pipeline implementation, split by responsibility
│   ├── orchestrator_opencode.py   # Entry point: OpenCode backend
│   ├── orchestrator_github.py     # Entry point: GitHub Copilot CLI backend
│   ├── pipeline.py                # Shared CLI shape and full phase order
│   ├── settings.py                # Repository layout, stages, schema, timeouts, call budgets
│   ├── workspace.py               # Seed and project-root resolution
│   ├── prompts.py                 # Agent prompt templates, batch messages, collaborator tables
│   ├── tasks.py                   # Task schema validation (ast_hints, observability claims) and ordering
│   ├── task_queue.py              # Queue files: read, index, emit, quarantine, cross-task gates
│   ├── ddd.py                     # Discovery, context-map and strategy gates
│   ├── assembly.py                # Stage 4: scaffold smoke-test detection, task emit, boot gate
│   ├── closure.py                 # Test-import closure audit; emits missing producer tasks
│   ├── refactor_audit.py          # Engine-computed diffs of what stage-3 sessions changed
│   ├── session_audit.py           # Per-session tool-call/token cost audit (Copilot records)
│   ├── status.py                  # Read-only board status, ledger states, token rollup
│   ├── verification.py            # Framework build/check gates + Docker access gate
│   ├── dispatchers.py             # Red-phase/AST/weaver dispatch, weave baseline, red recovery
│   ├── test_gate.py               # Green gate: import repair, external index, wave verdicts,
│   │                              #   bean_demands attribution, memoized verdicts, WOVEN-CLEAN
│   ├── attempt_ledger.py          # Cross-pass TDD attempt memory: billed-session grants
│   ├── agent_runners.py           # Subprocess plumbing and log tails
│   ├── tdd_engine.py              # execute_with_tdd, drain_queue, batching, deferrals
│   ├── opencode_backend.py        # ``opencode run`` phase runners
│   ├── copilot_backend.py         # Copilot CLI profiles and phase runners
│   └── telemetry.py               # Optional OpenTelemetry integration
├── gauntlet/                      # Engine regression suite (see above)
│   ├── run_gauntlet.py            # Pre-flight runner (--weaver adds the Java JUnit)
│   ├── test_skill_scripts.py      # Runner/writer normalization cases (owns compiler vocabulary)
│   └── test_engine_decisions.py   # Engine decision cases (normalized fields only)
├── seed/                          # Input business descriptions
├── ast_tools/                     # AST extractor executables (e.g. ast_extrator_java)
├── ast_weaver_tools/              # Code-weaver executables (e.g. ast_weaver_java)
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
│   ├── weave-baseline/            # Pre-weave file snapshots (retry re-weaves start clean)
│   ├── evaluate-results/          # Stage-3 refactor reports (final green test + engine diff)
│   ├── gate-cache/                # Memoized green-test verdicts keyed by source-tree fingerprint
│   ├── attempts/                  # Per-unit TDD attempt ledger (grants, billed sessions, last failure)
│   └── external-index.json        # Cached external classpath type index (per build manifest)
├── projects/                      # Generated source code
├── .opencode/
│   ├── agents/                    # OpenCode agent definitions (all <= 450 tokens)
│   └── skills/                    # Architecture, stack, coding, testing, and AST guidance
│       ├── tester-framework/      # Language/framework testing skills + run-test-tool.py
│       ├── coder-framework/       # Coder rules (java-springboot, java-standard-best-practices)
│       ├── assembly-framework/    # Per-stack boot skills (java-springboot, python-fastapi, typescript-nestjs)
│       ├── ast-dispatcher/        # Language detection and AST executable dispatch
│       ├── code-weaver-dispatcher/# Language detection and code-weaver dispatch
│       ├── read-write-file-ddd/   # Blackboard writers (red-phase, coder-changes, evaluate-results, ...)
│       ├── architect-practices/   # DDD and architecture skills
│       ├── tech-stack/            # Technology selection and migration skills
│       ├── tech-stack-architect/  # Stack-specific architecture guidance (java-reactive-patterns)
│       └── mcp-server-alternatives/ # Docker MCP scaffolding skills (Spring Boot, FastAPI, NestJS)
├── .github/
│   ├── agents/                    # Copilot agent profiles
│   └── skills/                    # Copilot-accessible skills (symlink to .opencode/skills)
├── mcp_server/                    # Docker image sources for the scaffolding MCP servers
└── *.md (root)                    # Recorded reports: *-seed002.md benchmarks, RUN-SUPERVISION-<date>.md live-drain
                                   # ledgers, PROJECT-INSPECTION-<date>.md delivered-artifact inspections
```

## Prerequisites

- Python 3.9 or newer (the orchestrators and the gauntlet use the standard library only; OpenTelemetry packages are optional).
- One configured agent backend:
  - [OpenCode](https://opencode.ai/) with access to the configured model, or
  - [GitHub Copilot CLI](https://docs.github.com/en/copilot) available as `copilot`.
- Docker when using the containerized MCP scaffolding servers. The pipeline checks daemon access before stage 0 and fails fast instead of spending agent runs; override with `--skip-docker-check`.
- The build tools required by the generated projects, such as Maven/Gradle, Node.js, or another stack selected during planning.
- Java 21 and Maven for the bundled Java AST extractor and code weaver. A fresh clone has no built JARs; the dispatchers compile both tool projects on first use within `TOOL_BUILD_TIMEOUT` seconds (default `900`).

Configure the AST extractor, the code weaver, and the MCP scaffolding images in `.env`:

```dotenv
# AST extractor: folder of the extractor project and its JAR name inside target/
AST_TOOL_ROOT=ast_tools/ast_extrator_java
AST_JAR_NAME=ast_extrator_java-0.0.1-SNAPSHOT.jar

# Code weaver: folder of the weaver project and its JAR name inside target/
WEAVER_TOOL_ROOT=ast_weaver_tools/ast_weaver_java
WEAVER_JAR_NAME=ast_weaver_java-0.0.1-SNAPSHOT.jar

# Seconds allowed to compile either tool when target/ is missing
TOOL_BUILD_TIMEOUT=900

# Docker images of the MCP servers used by the agent skills
SPRINGBOOT_MCP_IMAGE=caupolicanquerales/springboot_mcp_server:latest
SPRINGBOOT_MCP_PORT=8900
FASTAPI_MCP_IMAGE=caupolicanquerales/fastapi_mcp_server:latest
NESTJS_MCP_IMAGE=caupolicanquerales/nestjs_mcp_server:latest
```

## Quick start

### 1. Add a business description

Create a Markdown file in `seed/`. The first level-1 heading is used to derive the default output directory name.

The repository includes two examples:

- `seed/001_description.md`: a core banking platform covering Accounts, General Ledger, Payments, Treasury/FX, and Compliance/Risk.
- `seed/002_description.md`: a high-performance time-series telemetry ingestion pipeline — the benchmark used for the recorded evaluation runs.

### 2. (Optional) run the gauntlet

```bash
python3 gauntlet/run_gauntlet.py
```

### 3. Run with OpenCode

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

While a run is in flight, get the cumulative picture with:

```bash
python3 orchestrators/status.py
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
| `--verify MODE` | Verification mode: `none`, `typecheck`, or `build`; default: `typecheck`. |
| `--verify-scope MODE` | Verification scope: `task` (default) or `global`. |
| `--verify-timeout N` | Seconds allowed for each verification command; default: `300`. |
| `--limit N` | Stop after N tasks; `0` means no limit. |
| `--parallel N` | Concurrent domains during the drain; at most one task per project is in flight, so builds never share a `target/` directory. |
| `--emit FILE ...` | Validate and enqueue task JSON files without running the pipeline. |
| `--retry [ID ...]` | Move quarantined tasks from `blackboard/error/` back to the queue — all of them, or only ids matching the given patterns — then continue the run. |
| `--skip-docker-check` | Do not gate the queue drain on a reachable Docker daemon. |

OpenCode also supports `--no-auto` to omit automatic approval. The GitHub backend supports `--copilot-bin` and `--allow-tool`; their defaults can also be set with `COPILOT_BIN` and `COPILOT_ALLOW_TOOL`.

Run `python3 orchestrators/orchestrator_opencode.py --help` or `python3 orchestrators/orchestrator_github.py --help` for the complete CLI reference.

## The blackboard task model

A task is a small JSON contract containing everything an agent needs to perform one unit of work:

```json
{
  "id": "T2-007",
  "targetAgent": "agent-coder",
  "stage": 2,
  "dependsOn": ["T1-007"],
  "path": "src/main/java/com/example/treasury/fx/RateCalculator.java",
  "kind": "implementation",
  "layer": "domain",
  "feature": "fx-rate",
  "export": "com.example.treasury.fx.RateCalculator",
  "intent": "Compute the mid rate for a currency pair from pinned provider quotes.",
  "project": "treasury-fx",
  "ast_hints": {
    "package": "com.example.treasury.fx",
    "implements": [],
    "dependencies": [
      {"type": "ExchangeRateProvider", "task_id": "T2-004"}
    ],
    "methods": [
      {"signature": "midRate(String pair)", "returns": "java.math.BigDecimal"}
    ]
  }
}
```

Important conventions:

- IDs use `T<stage>-<number>` with stage `0`–`4`, for example `T0-023` or `T2-104`.
- `dependsOn` references earlier task IDs and defines the execution graph.
- `path` is relative to the domain project root, not the repository root.
- `project` is the domain slug and determines the generated project, filename suffix, and execution grouping.
- New queue filenames follow `<id>-<project>.json`, such as `T0-023-treasury-fx.json`.
- `ast_hints` (optional, required from the architect on planning stages) is validated structurally at emit time: its keys are exactly `package`, `implements`, `dependencies`, `methods`; dependencies pin each consumed type to its producing task; methods carry the exact signature and return spelling. A cross-task gate rejects a plan whose pinned collaborator's own table does not spell the surface its consumers use. Older boards without the table remain readable.
- `observability` (optional, stage-2 units): `{"step_logs": [...]}` — the VERBATIM execution-strategy step logs this unit OWNS and its stage-1 test must assert. The field, not intent prose, is the machine surface: vocabulary overlap in prose proves nothing ("samples", "ingress" appear everywhere in an ingestion plan) while a claim is checkable. Emit refuses plans that leave a planned entry unowned, double-claim one, or claim an entry the strategy never planned — and refuses the strategy itself if its observability floor (correlation key, step logs, audit trail, metrics, export) is absent or incomplete: the audit + logging floor is UNCONDITIONAL for every executable context, whether or not the business description asked for it. Boards without a strategy file (legacy, unknown stacks) skip the rule; the attempt-ledger contract hash ignores absent optional fields, so introducing this key never re-armed budgets on resumed boards.

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

With `--parallel N`, independent domains drain concurrently while at most one task per project is in flight, so two builds never share a `target/` directory. Work that is blocked by not-yet-finished siblings — a woven task whose domain is still being woven, a unit whose bean demand belongs to a pending peer, or an evaluator artifact pending while peer units remain queued — is deferred to a later pass instead of being marked failed.

Invalid tasks and failed executions are moved to `blackboard/error/` with an `error` field explaining the reason. Dependents of failed work are quarantined when they can no longer be resolved. Successful tasks move to `blackboard/complete/` using the same filename. After fixing the environment or the scaffold, relaunch with `--retry` to restore quarantined tasks to the queue. Re-emitting a task id SUPERSEDES its stale quarantine record — one id, one record across the board, because producers that resolve types through `error/` would otherwise defer live work behind a zombie.

### The attempt ledger

Stage 2 supports up to three implementation attempts (`MAX_TDD_RETRIES` = 3) when verification fails. The verification output is returned to the coder as focused feedback for the next attempt. These attempts are a **lifetime budget per contract**, recorded in `blackboard/attempts/<id>.json`:

- A later pass or a `--retry` restore of a unit whose task record, red record and AST contract are unchanged does **not** re-arm the budget from zero — it grants one informed attempt whose prompt already carries the previous failure, and a gate verdict whose normalized signature repeats a recorded failure quarantines the unit immediately instead of billing further coder sessions (a session costs a flat per-turn floor regardless of what the agent finds, so re-deriving a known failure is pure waste). The full budget returns only when the unit's contract actually moves. Up to `MAX_INFORMED_GRANTS` = 3 such grants exist.
- **Grant accounting is honest**: a grant is consumed only when the attempt actually bills a session. Replay closes that quarantine a unit at zero billed sessions return the grant — a mechanism that spends nothing must not eat the budget cap.
- A structural "does not override/implements a supertype" conflict in the unit's own file is deferred, not charged, while the supertype's producing task is still unresolved: the adapter cannot converge on a moving port.
- A weaver *payload rejection* (bad grammar, no builder) bounces back for re-emission without counting an attempt at all.

`python3 orchestrators/status.py` shows each quarantined unit's ledger state and whether a restore would advance, replay-close, or lock it.

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
- **Agent behavior:** edit `.opencode/agents/` and the matching `.github/agents/` profiles — keep every profile body at or under 450 tokens; the gauntlet's K-section pins doc-vs-schema truth.
- **Plan contracts:** the `ast_hints` rules live in `orchestrators/tasks.py` (schema) and `orchestrators/task_queue.py` (cross-task gate); vocabulary and emission duties in the architect skill and profiles.
- **Test conventions:** update `agent-tester` and the skills under `tester-framework/<language-framework>/`.
- **Red-phase record:** change `read-write-file-ddd/writer-red-phase/write-red-phase.py` or `orchestrators/dispatchers.py`.
- **AST extraction:** add builders under `ast-dispatcher/builders/` and configure `AST_TOOL_ROOT`/`AST_JAR_NAME` in `.env`; the dispatchers build the JAR automatically when `target/` is missing (`TOOL_BUILD_TIMEOUT`).
- **Code weaving:** add weavers under `code-weaver-dispatcher/builders/` and configure `WEAVER_TOOL_ROOT`/`WEAVER_JAR_NAME` in `.env`. Weaver grammar changes go with JUnit cases in `ast_weaver_tools`.
- **Green-gate behavior:** verdict normalization lives in `tester-framework/run-test-tool.py` (it owns all compiler vocabulary); attribution, deferrals, and WOVEN-CLEAN policy live in `orchestrators/test_gate.py` and `orchestrators/tdd_engine.py`. Add a gauntlet case with every behavior change.
- **Architecture rules:** update the skills under `.opencode/skills/architect-practices/`.
- **Technology choices:** update `.opencode/skills/tech-stack/`, the stack-specific guidance under `tech-stack-architect/`, and the MCP scaffolding configuration (images in `.env`, sources under `mcp_server/`).
- **Coding standards:** update the skills under `coder-framework/<language-framework>/`.
- **Application assembly:** edit the per-stack skills under `assembly-framework/<language>-<framework>/` and the detection rules in `orchestrators/assembly.py`.
- **Task closure:** tune gap detection and the auto-emitted producer tasks in `orchestrators/closure.py`.
- **Cost control:** change the per-agent tool budgets and hard-kill factor in `orchestrators/settings.py` (`AGENT_CALL_BUDGETS`, `BUDGET_HARD_KILL_FACTOR`) and audit real spend with `orchestrators/session_audit.py` and `orchestrators/status.py`.
- **Queue behavior:** change `orchestrators/task_queue.py` and `orchestrators/tdd_engine.py`; both backends reuse them.

Keep both backends' agent profiles aligned when changing the workflow, and run `python3 gauntlet/run_gauntlet.py` before and after — no merge without a case.

## Project status and evaluation runs

The pipeline is benchmarked against `seed/002_description.md` with the blackboard wiped clean between runs. The recorded reports live in the repository root:

| Report | Content |
| --- | --- |
| `PROJECT-REPORT-seed002.md` | First-run artifact inspection (2026-11-09): why the generated service compiled but could not be shipped. |
| `REPAIR-NOTES-seed002.md` | Contamination disclosure: operator code edits made before the "tune the process, not the artifact" directive. |
| `PROCESS-REPORT-seed002.md` | The tuning narrative: every incident, its root cause, the fix, and the gauntlet section that pins it (§1–§23). |
| `FINAL-EVALUATION-seed002.md` | The authoritative clean-run inspection: health probes, terminal-defect root-cause chains, per-agent scorecard, and the plan-stage fix checklist (all shipped). |
| `MULTI-STACK-AUDIT.md` | Stack-neutrality audit of agents, skills and orchestrators: the prose couplings and per-stack drift risks found by reading the whole instruction surface. |
| `RUN-SUPERVISION-2026-11-12.md` | The full-day rerun supervision: thirteen live root causes fixed under observation (static-vs-instance contract drift, constructor weaving, wave attribution, rollback holes, contract-regression reopen) with the board landing at 89/96 and one impossible test pair. |
| `PROJECT-INSPECTION-2026-11-13.md` | PART I: the post-mortem of the 11-12 tree (delivered non-compiling, "boot green" vacuous) + the implementation record of that morning's engine/skill fixes. PART II: inspection of the REGENERATED tree — machinery 100%, product ≈ a third of the seed's rules — the plan-vs-seed completeness finding and the floor/claim fixes it produced. |
| `RUN-SUPERVISION-2026-11-13.md` | The fresh validation drain (13:06–13:56): five root causes caught live, each stopped and fixed at its root (late assembly scheduling, multi-document YAML write refusal, marker-only hollow-boot fix, path-guard quarantining a correct composition-root move, zombie quarantine records), with the zero-burn economics ledger. |
| `PROJECT-INSPECTION-2026-11-16.md` | PART I–III: the three same-day drains' artifacts — from "green board, silently missing integrations" (F1–F6) to a delivered tree whose own e2e slice proves controller↔store↔schema agreement; per-run economics, defect attribution (F/N/G classes) and the dated post-drain addendum closing residuals G1–G4 at the plan tier (rules (s)/(t)/(u)/(v)). |
| `RUN-SUPERVISION-2026-11-16.md` | Three full live drains (71→84→102 units) and thirteen root causes stopped and fixed in place — phase-order claim hole, reserved-word package segment, silent `-q` green, PostgreSQL-dialect substitutes, an ungated cross-stage regression, a stage-0 tooling gap, prose-only invariants, sealed-type mocking, weaver packaging and dead compact constructors, a gate-vs-gate livelock, a misclassified green suite — plus the post-drain plan-rule factory pass. |
| `RUN-SUPERVISION-2026-11-17.md` | The fourth drain: it died twice and healed twice — every stage-1 test task emitted on the PRODUCTION path (new emit rule (w), live-fired against the real draft), a WebFlux handler forbidden from carrying its marker (emit rule (x)), the frozen-fixture physics laws (substitute credentials, aggregate decode), the container composition-root placement check, the packaged migration directory as the only canonical output, and the test-witnessed exemption for the base-document probe; 63/63, every repair closed at zero billed sessions. |
| `PROJECT-INSPECTION-2026-11-17.md` | The delivered artifact of 11-17: 131/131 suite, boot re-proven from the repackaged jar in a foreign cwd with classpath migrations and live HTTP contract curls; plan→mechanism→proof table per seed rule, day economics (56 sessions / 7.43 M tokens, the plan-phase burn bounded and attributed), and seven disclosed residuals H1–H7. |

The current headline (clean validation drain, 2026-11-17, wiped board and regenerated telemetry service): **63/63 units complete, zero quarantined, 131/131 frozen tests green, the application boots with the REAL domain context** — composition root at the ancestor package (enforced by a container placement check), packaged classpath migrations that travel with the jar (boot re-proven from a foreign cwd), the seed's reordering rule LIVE on the request path, every drop outcome counted and audited, and `assembly.detect` returning **zero problems**. ~56 billed sessions / 7.43 M input tokens, every repair closing at zero billed sessions, the plan-phase burn bounded and attributed by the watchdog. This drain also closed the last known failure family: the shape-defect PLAN (every test task emitted on the production path) now dies at emit under rule (w), the impossible handler registration under rule (x), the unwinnable frozen fixtures under the tester-skill laws, and the gate-vs-contract collision via the test-witnessed probe exemption — the same-day arc from `PROJECT-INSPECTION-2026-11-16.md` PART I ("green board, silently missing integrations") to `PROJECT-INSPECTION-2026-11-17.md` §1 ("every seed rule proven by the artifact's own tests AND a live request-path probe"). Residuals are named, not hidden: `PROJECT-INSPECTION-2026-11-17.md` §5 (inert double registration, a promise/duty direction rule (t) does not police, the silent terminal subscriber, the two-set migration seam, range-less metrics accepted unbounded by operator decision, the test-witnessed H2 boot default, and the plan-phase transcript size as the honest remaining lever).

This remains an experimental evaluator and orchestration project, not a guarantee of production-ready generated software. Agent runs can create and modify files, install project dependencies through their workflows, and execute build commands. Review generated code, migrations, security decisions, and test results before using them in a real environment.
