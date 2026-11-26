# Blackboard Evaluator Project

An experimental, agent-driven software factory that turns a business description into a domain-oriented codebase.

The orchestrator reads a seed document, discovers bounded contexts, plans the architecture, sets the security, performance and — when the description itself directs it — AI posture, creates database and application tasks, and coordinates specialized agents to scaffold, test, implement, and evaluate each unit of work. Agents do not call one another directly: they communicate through validated JSON files stored on a local **blackboard**.

The same workflow can run with either **OpenCode** or **GitHub Copilot CLI**.

Contents:

- [What the project does](#what-the-project-does)
- [How the orchestrator is designed](#how-the-orchestrator-is-designed) — the seven principles, the blackboard, the golden rule, where the money goes
- [How it works](#how-it-works) — pipeline, stages, agents
- [Core mechanisms](#core-mechanisms) — planning, resilience (R1–R6), verdict contract (O1–O5), red phase, weaving, test gate, assembly, attempts, cost, observability
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
- Designs each domain's security posture — threat model, authentication/authorization matrix, data classification, trust boundaries — as a machine-parsed `security-spec`. The phase runs for **every** domain and there is no flag to skip it; the one lawful omission is a `security_directive` on the domain's slice whose `quote` the engine finds **verbatim** in the business description file the slice names (discovery transcribes it, no agent decides it), and a waived domain is printed as `WAIVED` in the phase log and marked `SECURITY WAIVED by directive` in the terminal verdict written in abstract capability tokens. It authors no tasks and names no mechanism; the decomposition must claim each duty, and mapping tokens to real framework mechanisms stays the architect's job. The matrix is tabled against the plan: phase 1 declares every inbound surface in its `surfaces` table, the spec owes one row per declared name, and the enforcing unit must be wired into the adapter that IS that surface (see rule (y)). Duty closure now also covers the data tier: a PII `data_classification` row whose masking posture promises work must be discharged by at least one duty — prose agreement is not a claim (2026-11-25: the binding had existed only as convention).
- Designs each domain's performance posture — workload per declared surface, budgets, worst-case invariants — as a machine-parsed `performance-spec`, also unconditional; its budget promises close at the TEST tier too (rule (z7): every tabled measurement is asserted by a stage-1 test). Its distinguishing law is the wall-clock ban: `measurement.kind` comes from a CLOSED deterministic enum (query-count, config-key, status-code, payload-size, queue-depth, deterministic-count) because a limit provable only by a stopwatch flakes in CI and is a wish, not a gate contract; every budget and invariant is discharged by a duty the decomposition must claim, same channel as security's.
- Plans AI capability ONLY when the business description states it: discovery records an `ai_directive{required:true, quote}` whose sentence the engine re-finds VERBATIM in the seed file — the security waiver's mirror with flipped polarity: an AI capability is a product decision the user makes, never an agent's inference. The `ai-spec` tables model roles whose memory tier (`none|session|durable`) and technique (`sliding-window|rolling-summary|semantic-episodic`) are decided by triggers the gate enforces where provable (an approval pause forces durable; semantic recall forces the retrieval-scope guard; durable memory forces a persisted concept in the strategy), a CLOSED 14-token vocabulary covering single-agent boundaries, the multi-agent trio (delegation topology, loop termination, human approval) and the delivery-shape token — with three machine laws the artifact cannot dodge: delegation without a cycle bound is refused, an approval gate around no tool is ceremony, and naming SSE/websocket/gRPC in the spec is refused because TRANSPORT is phase 2's mapping, not a requirement. The mandatory `offline-model-port` invariant keeps the drain's defining economics intact: no test path may reach a live endpoint, and the offline stand-in must WIN WITNESSED (`@Primary` precedence, the bound proven by an assertion, never assumed).
- Breaks application work into dependency-aware test, code, and evaluation tasks — drafted **one file per bounded context, one planner session per context, and queued by the engine in a single `--emit` batch**, so the atomic cross-context checks still see the whole plan while no single output turn carries a 57-unit document (23,585 tokens) and no session carries another context's draft — each task carrying an **`ast_hints` contract table** (package, supertypes, pinned collaborators, exact method signatures, plus the shared-literal vocabulary fields `meters`, `routes` and `config`) that is validated at emit time — contradictory or under-specified plans are rejected before any agent session is billed.
- Runs each new test in **red phase**, records the result, and extracts **AST context** for the target class/method to guide the coder. A missing red record is re-derived deterministically by the engine; a session is never paid to re-observe a build result.
- Batches both stage-1 testers and stage-2 coders: one session writes up to four same-domain units, sharing a budget that scales with the batch.
- Processes tasks with an in-memory dependency graph instead of repeatedly searching the queue after every task.
- Groups ready work by domain to improve execution locality and make logs easier to follow; a domain's green test gate runs as **one wave** once all payloads are woven, and verdicts are memoized by source-tree fingerprint.
- Attributes green-gate failures to the owning unit — including **runtime bean-graph demands** — so a unit is never charged for a peer's missing bean.
- Gives every task a stable, readable filename such as `T0-023-treasury-fx.json`.
- Refuses to proceed when a discovered domain has no execution strategy: every later phase iterates *strategy* slugs, so an unplanned domain used to lose its database, **security**, and decomposition work in total silence (`ddd.validate_strategy_coverage`, a phase-1 post-check on both backends).
- Validates task schemas and dependencies, quarantines invalid work, and records failures; quarantined tasks can be restored with `--retry`, and a domain whose PLAN is obsolete (a strategy with no `surfaces` table, a security spec that arrived after its decomposition) is re-planned with `--replan <slug>`, which archives its strategy, its security/performance/AI specs and stage 1-3 records to `blackboard/archive/` and re-runs those phases — delivered sources are untouched.
- Audits test-import closure before draining, so a domain that can never go green stops the run early instead of burning agent calls.
- Keeps the plan phase inside a token budget. The monolithic architect became **two agents** (2026-11-20 split, following the `agent-ai-architect` / `agent-performance-architect` precedent): `agent-strategy-architect` runs phase 1 alone, and `agent-planner-architect` runs **one short session per bounded context** — its context's digest slice (duties pre-joined to their rule rows AND to their matched mapping-table rows, build coordinates extracted), the strategy, and a Python-built symbol table of the already-drafted contexts' exports; the **engine** claims the drafts (id-collision renumbering, dangling-pin refusal, both in-process), runs the single `--emit` batch itself (cross-context closure, the claim law and the shared-literal joins still see every file — at zero sessions), and routes a batch refusal to a bounded repair session carrying only the `ERR [id.field]` pointers. Phase 2 reads only the strategy and the digests; the profiles no longer restate rules (a)–(z) — the deterministic linter enforces them and cites them by letter, and the full contract ships once, in `task-decomposition-dag`. The carriers themselves are compressed (2026-11-20): each profile keeps only its own phase's law, example commentary is a caption, and rule letters appear only as inline cross-reference tags — what remains is schema, not narrative. `intent` is a specification, not an essay (40–80 words, **180 refused at planning**); refusals demand an **edit pass over the named task objects**, never a regenerated draft; each profile carries **exact skill paths for its own phase only** — a strategy session never pays for decomposition law (`--burn-report` measures it).
- Enforces per-agent tool-call budgets, kills runaway sessions, caps the number of *billed* sessions per unit through an attempt ledger with honest grant accounting, and keeps documents inside size caps the gauntlet actually enforces: per-family ceilings on the rulebooks and mapping tables (security rulebook <1000 words; performance <800; AI strategy <1400; architect tables capped per grounded row) and line/marker pins on the profiles — an uncapped doc is a cap waiting to be silently broken.
- Runs independent domains concurrently with `--parallel` while preserving stage order.
- Boots the generated application through a stage-4 assembly gate backed by the scaffold's own smoke test — with structural probes that refuse a vacuous green (composition-root visibility, request-path evidence, base-document substitution discipline with its test-witnessed exemption, config documents in their kind's native form) and a terminal tree verdict at every exit.
- Ships a **gauntlet** — a 551-case regression suite (372 engine decisions + 179 skill scripts) that pins every incident class observed during live drains — and a read-only board status tool with token rollups.
- Supports optional compilation/build checks and OpenTelemetry tracing.

## How the orchestrator is designed

The whole system follows from one sentence: **a deterministic program runs the
factory, language models are hired for one task each and paid per task, and they
never talk to each other — they leave validated files on a blackboard.** The rest
of this section unpacks that sentence; each principle exists because its absence
once cost a real run.

### Principle 1 — the engine decides, the model drafts

The orchestrator is plain Python: loops, JSON schemas, hashes, graph joins,
subprocesses. It never asks a model a question it can answer itself. A model is
invoked only where generation is genuinely needed — an intent paragraph, a test, a
method body — and every such invocation is a **session**: bounded inputs, a fixed
tool budget, a known set of output files. The roster is small and every seat has
one job: domain discovery, context mapping, strategy, the security/performance/AI
specs, database planning, per-context planning, container building, and in the
drain — testers, coders, evaluators, the assembler. Between sessions, the machine
runs at zero tokens.

The reason is cost asymmetry. A model that is also the referee turns every mistake
into a re-billed run; a model that only drafts turns every mistake into one refused
file, caught before anyone pays for it again.

### Principle 2 — the blackboard is the only telephone

```text
   operator input: seed/*.md (the only ground truth)
              |
              v
   +==============================+
   |     ORCHESTRATOR (python)    |   deterministic loop: hire, gate, judge -
   |  no LLM inside this box      |   no model referees its own work or anyone's
   +--------------+---------------+
       hires      |      reads back
      (billed)    v      (validated bytes, never claims)
   +==============================+
   |  agent = ONE LLM session     |   fresh context window, one bounded job,
   |  discovery · mapping · plan  |   then it dies: the session is re-read ONLY
   |  tester · coder · assembly   |   as the file it delivered, never as a
   +--------------+---------------+   transcript
                  | its ONE output file
                  v
   +=====================================================+
   |                     blackboard/                     |
   |  domain/ · context-map/ · complete/ · queue/        |
   |  ast-context/ · red-phase/ · coder-changes/         |
   |  weave-results/ · evaluate-results/ · attempts/     |
   |  snapshots/   (+ archive/ when a domain replans)    |
   +=====================================================+
      the ONLY shared memory: every handoff is a file with a schema,
      a producer, a consumer - and a gate that re-validates the BYTES
```

No agent ever calls another agent, sees another agent's transcript, or edits the
artifact it will itself be judged by. Agents start with a fresh context window, do
one bounded job, and die. Everything durable lives on the board. Three properties
fall out of this for free:

No agent ever calls another agent, sees another agent's transcript, or edits a
file another agent owns mid-task. Agents start with a fresh context window, do one
bounded job, and die. Everything durable lives on the board. Three properties fall
out of this for free:

- **Inspectable** — any question "what did the pipeline decide and why?" has an
  answer in a file, not in a scrollback.
- **Resumable** — the process can be killed at any millisecond; a relaunch re-reads
  the board and continues where it stopped (see R2/R5 below). Nothing is trapped in
  a model's memory.
- **Auditable** — a plan audit (like the 2026-11-26 one) can re-check every promise
  made by every artifact against every unit, mechanically, after the fact.

### Principle 3 — a claim is never a completion criterion

Every agent output is treated as a *promise about bytes*, and the engine checks the
bytes. The sequence for one unit through the drain:

```text
  tester session ----> test file + red record   -----> ENGINE re-runs the test,
                                                        re-validates the record
  planner session ---> task draft JSON          -----> ENGINE lints, claims ids,
                                                        joins it to every other draft
  coder session -----> PAYLOAD (never source)    -----> WEAVER splices it in, the
                                                        engine owns the source tree
  assembly session --> "the app boots"           -----> ENGINE boots it again with
                                                        its own smoke-test gate
  every exit --------> "done"                     -----> ENGINE re-runs the WHOLE
                                                        delivered suite
```

The party judged by a test can never edit it, and the party that claims success is
never the one that records it. "Trust, but verify" is too weak here: **verify, and
keep the receipt.**

### Principle 4 — the golden rule: agents agnostic, skills generic, orchestrator generic

The machine must build a Java service, a Python service or a TypeScript service
with the same code. So stack knowledge is allowed in exactly two places, and the
rule is enforced by gates, not by good intentions:

```text
   WHO SPEAKS IT            WHAT THEY MAY SAY                   WHERE STACK WORDS LIVE
   ----------------------   -------------------------------     ------------------------
   security/perf/AI specs   capability tokens only               no framework names EVER
                            ("bearer-jwt-proof", not Spring)     (a spec gate refuses leaks)
        |
        v   mapping = an architect decision, per stack
   tech-stack architect     mechanism IDENTIFIERS + config keys  spring-*.md tables,
   skills                   (this token = that class/property)   chosen by strategy pin
        |
        v   composition = a coder decision, from a table
   coder/tester skills      the actual DSL / idioms              tech-stack/spring-security
        |
        v
   orchestrator modules     NO stack words at all - only typed  stacks.py is the ONE
                            verdict fields, registry lookups,    toolchain registry; engine
                            filesystem facts, declared paths     modules read nothing else
```

Every violation of this rule has the same shape: a framework fact leaked one level
too high, and every later incident added a special-case branch to whichever private
copy of it the fixer happened to touch. The 2026-11-26 consolidation found five
drifted copies of the build-toolchain facts in the engine — after `stacks.py`, all
five consumers read one registry, and a merge golden-verified every decision
byte-identical. The gauntlet bans dead stack vocabulary in orchestrator sources
(SP16) and realization vocabulary in the specs, so the leak class cannot silently
return.

### Principle 5 — every law lives in three homes

A rule that lives only in prompt prose is a wish. A gate with no regression case
dies in the next refactor. So each law gets three homes, and an incident is only
closed when all three exist:

```text
   incident observed live  (supervised run STOPS on it - no silent workaround)
        |
        v
   root cause attributed to exactly ONE layer
   discovery | mapping | strategy | specs | planning | drain | engine | carriers
        |
        v
   fix written at that layer, for the whole CLASS of problem:
     1. PROSE   - the skill/profile states the law, in stack-neutral words
     2. GATE    - the engine refuses bytes that break it, at zero billed sessions
     3. PIN     - a gauntlet case proves the refusal still fires tomorrow
        |
        v
   551 pinned cases; "no merge without a case"
```

This is what breaks the classic loop of "keep fixing the orchestrator": the fix for
an incident is never a new special case around that incident — it is a generic law
(the class it belongs to), a generic gate, and a pin that keeps all three honest.

### Principle 6 — the plan phase is where mistakes are cheap

```text
   cost of one defect, same seed, found at:

   emit gate ......... 1 refused draft line + 1 bounded repair session (~free)
   red phase ......... 1 tester batch re-rolled, contract still open
   green phase ....... up to 3 billed coder attempts + quarantine bookkeeping
   mid-drain ......... a whole run: the 2026-11-18 board froze 11 units behind
                       contradictory contracts - three billed sessions each
```

Hence the wall: 26 letters of plan-validity rules (a)–(z) fire at lint AND at the
single `--emit` batch, before any test freezes — impossible pairs, unowned literals,
unclaimed duties, unschedulable registrations all die there. And hence the
direction of repair: when reality does break a promise mid-drain, blame is attributed
to the OWNING unit (typed verdict fields, never prose-scraping), and the reopening
moves the contract, not the victim.

### Principle 7 — arithmetic is never billed

The economics principle that reshaped the code: anything a machine can compute must
be moved OUT of sessions, and anything that can resume must not re-bill.

```text
   FREE (engine, deterministic)                 BILLED (one bounded session each)
   -------------------------------------------  --------------------------------
   task ids, renumbering, collision healing     drafting prose the machine cannot
   symbol tables, digest slicing, joins         write: intents, tests, bodies
   stage-3 synthesis, T1 table mirroring        ...one per bounded context, one
   build-manifest queueing (phase 1.5)          batch per up-to-4 units
   re-running tests, parsing verdicts           ...budgeted: 6-22 calls measured
   routing refusals to the owning draft         against live sessions, killed past 2x
   FACT/LAW/VERDICT resume (R2/R5): a killed
   run's compliant drafts resume at zero cost
```

When a measured behavior resisted moving off the bill, the answer was structural,
not exhortative: the planner's wall clock was dominated by the model *decoding* one
huge draft per turn, so contexts now draft **concurrently** against `{type, context}`
anchors the engine binds afterwards — a 222-task plan phase landed in 3m26s on three
billed sessions (2026-11-26) — after a week in which the same phase cost days
of relaunches, every one of them an invalidation storm or a cap-killed draft re-billed
whole.

### The shape of the code

```text
   orchestrators/
   ├── orchestrator_opencode.py / orchestrator_github.py   entry scripts (same pipeline)
   ├── settings.py stacks.py prompts.py family_paths.py    SHARED KERNEL: budgets, the
   │                                                       one stack registry, the briefs,
   │                                                       the folder bootstrap
   ├── orchestration/    pipeline.py + cli_args, run_phases, plan_gates,
   │                     plan_flow, drain_flow             WHEN things run, in order
   ├── task_creation/    task_queue.py + plan_drafts, plan_board,
   │                     plan_wiring, plan_laws            how a PLAN comes to be
   ├── task_contract/    tasks.py + task_identity, task_signals,
   │                     task_rules                        what a TASK record IS
   ├── backends/         opencode_backend, copilot_backend how a SESSION talks to a tool
   └── kernel modules    ddd, tdd_engine, test_gate, assembly, closure, agent_runners,
                         verification, attempt_ledger, status, telemetry, ...
```

Each family keeps its root module as the public facade (callers import `pipeline`,
`tasks`, `task_queue` exactly as before) and a README that is a **failure-home map**:
symptom → the module that owns it. The splits were proven zero-behavior by goldens
that compare record digests and byte-identical outputs, never by "looks the same".

### What this design deliberately is not

- **Not an agent chat room.** There is no orchestrator LLM making plan-time calls in
  a loop; the intelligence is hired per task, bounded, and file-mediated.
- **Not prompt engineering with retries.** Every refusal is an `ERR [id.field]`
  pointer demanding an EDIT of the named object — regenerate is the expensive
  fallback, edit is the designed path.
- **Not a framework demo.** Nothing in `orchestrators/` may know Spring, Maven or
  pytest; those names live in skills and in the generated project, where a swap of
  stack changes one table, not the engine.

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
  Security planning (one spec)        principals, the authorization matrix,
              |                       data classification, trust boundaries and
              v                       the duties - as capability tokens only
  Performance planning (one spec)   workload per declared surface, budgets with
              |                     DETERMINISTIC measurements (the enum has no
              v                     wall-clock kind), worst-case invariants
  AI planning (only on a VERBATIM   roles + memory tier/technique, the closed
              |                     14-token vocabulary, offline-model-port
              v                     invariant; transport names refused)
  Application task decomposition  ONE session per bounded context: the ROOT pass
              |                   drafts first (singletons, root gate), sibling
              |                   contexts draft CONCURRENTLY and pin each other
              |                   by {type, context} anchors the engine binds to
              |                   renumbered ids before the batch; per unit a
              |                   stage-1 TEST + stage-2 CODE + stage-3 REFACTOR
              v                   triple, all pinned to the SAME ast_hints table
   Plan validation + emit gates   rules (a)-(z) + spec-claim/writable-channel gates:
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

Before the drain, the planning specialists create the DDD and architecture artifacts:

- `domain-boundary-discovery-specialist` writes one domain boundary file per subdomain.
- `domain-context-mapping-specialist` writes the corresponding context maps.
- `agent-strategy-architect` (phase 1) writes execution strategies — including each domain's `surfaces` table of inbound surfaces, the join key the security phase is measured against, the persistence strategy and the unconditional `observability` floor — and emits the one scaffold task; it never reads the decomposition contract.
- `agent-planner-architect` (phase 2) decomposes the work into tasks, **one session per bounded context**: it reads TWO Python-sliced inputs - the context's strategy slice (phase 1 filtered to its context) and its digest slice (every duty arrives COMPLETE: surface/test_duty/measurement joined onto it, matched mapping-table cells attached; no rules map, no spec prose) - plus the symbol table of the drafted contexts, loads the DAG **QUICKREF** by default (the full SKILL.md only when an `ERR` pointer cites a shape the map lacks), writes one draft file and lints it (`--lint`); the engine claims ids, emits the batch and routes refusals to bounded repair passes. Every unit carries its `ast_hints` contract table, and mapping a capability token onto a real mechanism is this phase's job — from the digest's rows, never from recall. The domain ships ONE scaffold and ONE build-manifest task, and since the 2026-11-25 restructure the manifest is not scheduled by ANY session: the ENGINE queues it at plan start (PHASE 1.5) from the stack table's *Build coordinates* rows filtered against the planned capability set (`plan_build_manifest`), the ONE config unit and the ONE root admission gate belong to a dedicated **ROOT pass** (the reserved pseudo-context `Root & Infrastructure`, drafted before the bounded contexts, whose ids every context pins through the symbol table), and the old `missing_coordinates`/`config_paths` gap channels are DELETED — arithmetic and singletons are never billed to a session. In a board draft the session may also omit the engine-derivable half of every unit: stage-3 records are synthesized and stage-1 tables mirrored at claim (R4). Because a module's test compile pulls the whole module's classpath in every stack (Maven, Gradle, npm, pip alike), every stage-1/2 task must reach that manifest transitively through `dependsOn` - a purely structural machine gate (`_manifest_order_errors`), fired at lint AND at emit, with zero framework vocabulary in the check.
- `agent-database-architect` selects storage technologies and queues database tasks.
- `agent-security-architect` designs the access-control and data-protection posture per domain and writes `blackboard/complete/security-spec-<slug>.json` — requirements and capability tokens only, one authorization row per surface phase 1 declared; it queues nothing.
- `agent-performance-architect` sizes the load side per domain and writes `blackboard/complete/performance-spec-<slug>.json` — workload keyed verbatim to `surfaces[].name` (or a reasoned exemption), budgets carrying a `measurement` from the closed deterministic enum, worst-case invariants, duties; no product, library or key name may appear in it. Unconditional, like security.
- `agent-ai-architect` plans AI capability per domain — and runs ONLY on the engine-verified `ai_directive` quote. It writes `blackboard/complete/ai-spec-<slug>.json`: model roles with statefulness + memory technique, capabilities from the closed 14-token vocabulary keyed verbatim to surfaces/flows, deterministic measurements, the mandatory offline-port invariant, duties. The gate enforces what the artifact can prove (termination, scoping, durable triggers); the prompt-contract home is a SOURCE TYPE, never a template file. It queues nothing and names no framework, vendor or transport.

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
| **Planning a contradiction** (artifacts that freeze against each other) | The emit gates, rules (a)–(z): every duty owned by a path, prose never fighting the table, request-encoding agreement, signalling returns describing both branches, consumer closure, the correction value axis, promised mechanisms scheduled as duties, test artifacts separate from production files, handler registrations the framework can actually execute — and the shared-literal class (rule (z)): a meter name, route or property path two contracts spell differently, a slice that cannot construct the guard it imports, or a unit planned onto a path no writer owns. A refused plan costs one rewrite; the same plan discovered mid-drain costs a whole run (2026-11-18 proved it: five frozen-contract deaths, three billed sessions each). |
| **Claiming success that did not happen** | The TDD tier: no agent report closes a unit. Each transition needs a machine witness — a revalidated red record, a weaver result, a wave verdict from the engine's own run, an evaluate diff with the test re-greened, a boot gate re-run by the orchestrator, and the terminal suite verdict at every exit. Even the cost rollup is read from backend session events, not from what agents say they did. |

And when reality breaks a promise anyway, the loop repairs at the right seam:
verdicts are attributed to the producing unit, blame on foreign files follows the
runner's typed `blamed_files`/`stack_files` fields joined to the task registry (the
engine deleted every prose-scraping decision path on 2026-11-25 — see the
[verdict contract](#the-verdict-contract-o1o5)), a unit whose *peer* closed a type it
must stub is deferred while the closer is reopened, a cross-stage regression reopens
the contract's OWNER rather than charging the bystander whose test turned red — and
every such routing is pinned by a gauntlet case, so a fixed class stays fixed.

## Core mechanisms

### Plan-time contracts (`ast_hints`)

Every stage-1/stage-2 task may carry an `ast_hints` table — `package`, `implements`, `dependencies` (each collaborator pinned to the task that produces it), and `methods` (exact signature + return spelling), plus three optional **vocabulary keys**: `meters` `[{name, duty: owns|uses}]`, `routes` `[{method, path, duty: serves|uses}]`, and `config` `[{path, kind: value|list|map, fields?}]`. The board validates the table shape at emit time, and a **cross-task gate** rejects any plan that pins a collaborator whose own table does not spell the surface its consumers use. A tester writes assertions only against this table; a coder creates or edits exactly the pinned surface. Because the table is injected directly into the tester's and coder's messages, agents do not hunt the board for filenames.

### Rule (z): shared literals are tabled, not prose

Meter names, request paths and property paths are literals used by two or more contracts — the registering unit, the recording units, the frozen test pair. While they lived only in `intent` prose, one board carried BOTH spellings as frozen law (the facade registered `telemetry.validation.failed` while the plan and the consumer's test said `telemetry.samples.validation_failed`; a controller test posted `/ingress/packets` while the chain, the intent and the slice said `/telemetry/ingress`), and no payload can satisfy a contradicted pair — the coder between them died 3/3 while every per-unit gate stayed green. The fields make the vocabulary visible; the emit gate joins it:

- **z1** every meter name `owns`ed by exactly one unit; every `uses` matched VERBATIM (a near-miss spelling is refused NAMING the closest tabled one); tabled names must exist in the strategy's observability floor, and once the domain carries the fields, every floor meter must have an owner.
- **z2** every (method, path) `serves`d by exactly one inbound unit; `uses` cite it verbatim.
- **z3** a route-shaped literal or floor meter spelled in a staged unit's OWN text while its table omits it is refused — prose may never be a shared literal's only home.
- **z4** one unit, one table: the T1/T2 twins carry IDENTICAL `ast_hints` (against a delivered twin, shared keys must agree; either side may ADD vocabulary keys), so a frozen test and its implementation can never be written from two spellings.
- **z5** one property path, one shape: the binding record owns kind and element fields, the config writer cites them verbatim (relaxed-binding canonicalization makes `secretHash` and `secret-hash` one literal, as the runtime reads them); two kinds, differing fields, or a dotted child under a tabled list prefix are refused.
- **z6** a guard's world is visible to the surface it guards: a unit pinning a guard that cites its served route must also pin every project product the guard's table declares — a slice importing that chain builds it from the container, and an untabled bean is NoSuchBeanDefinition at every slice boot.
- **z7** budget-assertion closure (2026-11-25): every performance budget the spec tables with a deterministic `measurement` must be cited by at least one stage-1 test — the measurement text is quoted INTO the refusal. Enforcement without proof is a limit that regresses silently; the cold6 audit found two budgets proved nowhere, and the join now fires at lint (inside the drafting session's own budget) and at the batch.

Two sibling emit gates close the adjacent classes: the **writable channel** (a stage-1/2 `path` must be a language source or a configuration document — no agent authors template files, so a `prompts/system.st` unit is a duty without a channel and dies at zero sessions), and **planning-spec claims** (every performance/AI duty is discharged inside a stage-2 unit by spelling its `spec_ref` + `capability` verbatim, the (y)-family channel; unclaimed duties also stop a resumed board, with `--replan` as the remedy).

The `FINAL-EVALUATION-seed002.md` §6 roadmap has since **shipped**: plan-content roots are now dead on arrival, refused at emit by stack-neutral plan-validity rules (full contracts live in `task-decomposition-dag`; every refusal class is pinned in the gauntlet): (a) every file duty an intent assigns must be owned by a task's `path`; (b) intents that externalize values imply a scheduled config unit; (c) pinned request-parameter types must agree with the body encoding the paired test mandates; (d) null-rejecting intents must table their initial-state `semantics`; (e) **prose must not fight the table** — an intent asserting an unconstructible shape (`private constructor` / `utility class`) while the table binds instance members, or calling a pinned producer's member in static form (`Type.member(`) while that table binds it as instance, are refused as impossible pairs (the 2026-11-12 drain froze its whole domain behind exactly this contradiction); (f) provider closure — every type a table constructor injects must have a named provider duty in the DAG; (g) composition-root visibility — the entry point must be the ancestor of every component package or declare its coverage as a scheduled duty; (h) config-surface completeness — every document the paired test pins, an enabled runtime reader's datasource keys in that reader's own document, and the stack's test-profile activation route; (i) stream egress — every published port names its consumer unit or declares the out-of-process boundary; (j) step-log claim coverage — every step log the execution strategy plans must be claimed VERBATIM by exactly one stage-2 unit, and the strategy's observability floor itself is unconditional (below); (k) consumer closure / source reachability — a unit whose table publishes a stream must be pinned by a CONSUMER (a wiring unit's own pin counts as production, not consumption) or declare its out-of-process boundary per unit (2026-11-16 F1: the reordering service was a registered island and the seed's core rule never ran); (l) shared literals have one owning unit — consumers pin the owner instead of re-spelling values; config readers whose URL forms differ need distinct keys; (m) signalling returns — a tabled `boolean`/`Mono<Boolean>` method without `semantics` naming both outcomes is refused (F2: the unowned false branch dropped samples while the API lied 202); (n) one registration mechanism per product — a type both factory-produced and self-registration-claimed is refused (F8); (o) a unit executing SQL/DML is refused when its paired test intent lacks the REAL-SUBSTRATE demand — the embedded substitute executing the actual migration DDL: a mocked database client verifies call shape, never schema fit (2026-11-16 second drain N1 — every production audit write died on `NULL not allowed for "AUDIT_ID"` while 186 tests stayed green); (p) an inbound adapter without one end-to-end request-path slice task is refused (the boot proves the graph resolves; only a driven request proves controller, store and schema agree); (q) at-least-once inbound over an append-only revision chain needs a named dedup identity on the receiving contracts or a strategy at-most-once segment (a network retry must not mint a domain revision); (r) a config unit enabling a migration runner must spell the PACKAGED (classpath:) location, never a CWD-relative `filesystem:` path into the project — portability is refused at EMIT only and never relitigated at the assembly gate against the config unit's own frozen test (the 2026-11-16 T4 livelock); (s) correction axis — a chain that dedups inbound over an append-only history that speaks of corrections must state the VALUE-AXIS decision beside the identity (payload inside, or excluded plus a named retry-vs-correction discriminator) and table both resend classes as test duties (PART III G2: a value-excluding identity silently reclassified every value-correction as a duplicate no-op while (q) stayed satisfied); (t) a strategy-promised mechanism ("... via \<mechanism\>") must appear UNNEGATED as some unit's install duty (dependency + enablement at wiring/boot) — the emit gate refuses the promise/duty disagreement using the strategy's own token, and the concrete mechanism shape belongs to the tech-stack skill (PART III G3); (u) no acknowledged outcome is unmetered — every step log the floor promises pairs with a metric or an explicit `uncounted_steps` reason, and every failure/drop outcome contracted in tabled `semantics` pairs with a counting meter or a declared `uncounted_failures` posture (PART III G4: audited-but-uncounted failures are how a losing pipeline reports a healthy dashboard); (v) config format follows the artifact kind — KEY/VALUE pairs tabled in a config unit are SEMANTIC PROPERTY PATHS, never a file layout; the runtime artifact is serialized in the native form of its file kind per the tech-stack skill (structured documents nest, flat key-value kinds spell dotted keys), and the assembly gate re-serializes a mismatched delivered document (shape moves; values and loader-based tests never do); (w) a stage-1 test task owns a test file — the tester writes its frozen test AT the task `path`, so a test task sharing an implementation task's path is refused at emit: one file cannot hold both the frozen test and the unit later woven over it, and a test class under the production root never sees the test-scoped dependencies (2026-11-17: every tester task of a 57-task plan was emitted on the production path; the import-closure guard stopped the drain at the first red close-out, zero agent sessions wasted beyond the plan itself); (x) a mapped inbound handler names the ONE registration mechanism its framework can execute — the stack's handler marker on its own class or a functional router owned by the wiring unit; forbidding the marker while the factory alone registers boots green and answers 404 (WebFlux maps only annotated classes — the 2026-11-17 e2e slice caught the impossible pair), refused at emit for the planned language; (y) **security duty claim coverage** — every duty in the domain's `security-spec-<slug>.json` must be claimed inside a unit of the domain's per-context drafts (the batch the engine emits): the unit's intent carries BOTH the duty's `spec_ref` token (`AZ-03`, `SI-01`, …) *and* its `capability` token (`tenant-scoped-query`, …), the chosen mechanism is named in the same sentence, and a token the spec never declares is refused too — an id without its capability is a citation, not a mapping. Either way the rule ships in no unit while every per-unit gate stays green (the same completeness hole (j) closed for step logs). Coverage alone is not placement, and a 2026-11-18 probe proved the difference: a plan whose every duty was claimed shipped an entry adapter with NO guard on its path — the claim lived in an island unit the adapter never pinned — and every gate stayed green. So (y) has three placement refusals: **(y1)** the claim sits on the stage-2 unit that enforces it (a token living only in a tester's or an evaluator's intent implements nothing); **(y2) reach** — the unit that IS a surface (its intent names the strategy's `surfaces[].name`) must pin the enforcing unit in `ast_hints.dependencies` and carry it in `dependsOn`, or the predicate belongs on the unit that performs the lookup, because the drain orders units only by `dependsOn` and testers assert only against pinned tables — an unwired guard is implemented after the frozen pair it would have changed; **(y3) assertion at the surface** — that adapter's own stage-1 test carries the row id and its cross-owner case, since a permission rule proven only on its predicate's unit test is a rule no request ever meets. A declared surface no inbound unit names is refused outright (ownership): the join cannot be dodged by silence. **(y1-row) coverage is not scheduling** (2026-11-26 audit: 3 of 8 authorization rows hid behind another duty's `covers` and reached NO unit): every `authorization_matrix` row must also be spoken at the unit that IS its surface entry — row id beside the covering duty's capability — and the digest join INHERITS the covered row's `test_duty`/`surface` onto the duty when its own row states none, so a cross-owner case cannot die in transit between the spec and the session. The spec's own language is gated before it ever reaches emit — `ddd.validate_security_spec` refuses realization vocabulary (a framework or library name, an annotation, a framework-suffixed class, a file name, a package path, a property-style path, a task id, a board folder) wherever it appears in the design content, because mapping a capability token onto a stack's real mechanisms is the architect's decision with the tech-stack skill, not the security step's; For Java that decision is not left to recall either: `tech-stack-architect/spring-security-architect` tables every declared capability token against its Spring Boot 3 mechanism, build coordinates, config keys and wiring order, and the table is machine-pinned against the token vocabulary and against Boot's own `spring-configuration-metadata.json`. The chain DSL and the `spring-security-test` configurers are NOT in that planning file: they live one tier down in `tech-stack/spring-security`, the coder/tester-tier skill the java framework skills point at (the two files must never share a skill `name` — same-id skills shadow each other in the loader). It also refuses a row that discharges no duty, an ownership-blind IDOR row, `restricted` data allowed on any egress surface, a `unit_kind` or capability token outside its closed set, and — the join back to phase 1 — a declared strategy surface with no authorization row, an invariant owned by a context the strategy never declared, a `principals[].source` that traces to no entry of the domain slice, and an empty classification table over a `persistence.data_model` that names persisted concepts. The claim gate skips a domain with no spec, a batch that stages no application task (the scaffold and database steps emit stage 0 only and cannot answer a decomposition duty), and a project whose decomposition has not landed yet. A board whose decomposition PREDATES its spec is the one shape the emit gate structurally cannot police — its units are already frozen — so the pipeline now reads the live board itself (`task_queue.security_claim_gaps`) and stops with `security claim gap(s)` plus the remedy `--replan <slug>` instead of printing a hint and draining on over an unenforced permission table; the same phase stops on a spec that leaves an `open_questions` entry, because an undecided posture is an unprotected surface and only phase 1 can answer it. The assembly gate carries the matching delivered-time probes: request-path evidence in the delivered test tree, no embedded substitute spelled in the BASE config document (literal or placeholder-default) UNLESS a delivered test asserts that exact value — a test-witnessed base default is a planned, disclosed posture, and the probe goes silent for it (2026-11-17: the assembler obeyed the unwitnessed rule, broke the config unit's frozen test, and the terminal suite gate reopened the owner to undo it — rule (r)'s livelock doctrine applied to VALUES), and structured config documents spelled in their kind's native serialization (rule (v)) — with one sanctioned ADDITIVE route for legacy trees (create the missing slice, never edit an existing test).

### Plan robustness primitives (R1–R6)

2026-11-25 stopped the "fix a skill → the next launch dies" loop by moving four
behaviors from law text into machine structure; 2026-11-26 finished the job
(R5's prose-hash coupling proved the loop had merely changed shape, R6 healed a
stage-0 destruction found only by auditing the emitted queue):

- **R1 — snapshot and auto-revert.** The plan phase snapshots its binding inputs
  (strategy, specs) before any session runs and re-validates them at every mutation
  boundary. A session's rule (t) text amendment — same schema shape, file still
  passes its own gate — is accepted; anything that restructures an input is rolled
  back to the phase-1 bytes and the run continues. A desperate repair can no longer
  poison the NEXT launch (a live death: an invented strategy key killed a cold run at
  its shape gate after a fully paid plan).
- **R2 — content-hash freshness.** A draft is kept only when the FACT hashes (strategy,
  specs) it was claimed under still match the inputs on disk (a `.draft-meta.json`
  sidecar stamps them). mtimes re-billed compliant drafts whenever a doc was resaved;
  a killed run's compliant drafts RESUME at zero sessions, and touch-churn re-bills
  nothing. (2026-11-26: the contract SKILL.md is NO LONGER a hashed input — prose is
  law, not fact; see R5.)
- **R3 — refusal routing.** Batch refusals carry `ERR [id]` pointers, ids carry blame,
  blame routes to the ONE owning draft file: each bucket gets its lines, its files,
  its own repair rounds (a no-op exhausts ITS bucket and lets the others keep their
  turns — never a whole-domain fatal). The 2026-11-25 cold runs measured the effect:
  routed repairs cost 56–176K where whole-domain repair storms used to spend 500K+ per
  round.
- **R5 — FACT/LAW/VERDICT resume machine.** The sidecar records the claim VERDICT and
  the LAW fingerprint: `fresh` skips the session, `unjudged` (no sidecar, a `LAW_VERSION`
  bump, or a pre-split sidecar) re-VALIDATES bytes for FREE at the claim gate, `rejected`
  escalates to ONE real re-draft (counted), and `exhausted` after `MAX_REDRAFTS=2` stops
  loudly — a refusal storm can no longer replay across launches, and a rejected draft can
  never launder as fresh. Skill-prose edits are physically incapable of re-billing a plan
  (two of them re-drafted eight sessions on 2026-11-26 before this split).
- **R6 — stage-0 self-heal by export marker.** The build manifest never overwrites a
  board record (collision-safe ids, never-write-over guard); a manifest-without-scaffold
  board is healed from the phase-1 agent's OWN draft file (`[heal] ... zero sessions`);
  and stage-0 identity is the EXPORT MARKER everywhere — the scaffold/manifest shape
  collision silently deleted the domain's only boot task on 2026-11-26, and the emitted
  queue looked healthy until a plan audit found it.
- **R4 — machine-enforced draft economy.** A board draft may omit what the engine can
  derive: stage-3 records are SYNTHESIZED at claim from the code side, stage-1 tables
  are MIRRORED from their stage-2 twins, and `uses_meters`/`uses_routes`/`uses_config`/
  `claims_steps` references expand into the tabled entries they pin. A session can no
  longer make a draft expensive — or inconsistent — by its writing style.

### The verdict contract (O1–O5)

The same day, the execute/drain side stopped being a semantic recovery layer. The
orchestrator used to reverse-engineer what agents meant from compiler prose, file
naming conventions and post-processor patches — so ANY skill edit that shifted tool
output phrasing or file layout silently inverted a defer/charge decision. The law now:
**every decision that can bill a token binds ONLY to typed verdict fields, registry
lookups, or filesystem facts.**

- **O1 — versioned verdict schema.** `run-test-tool.py` stamps every output with
  `verdict_version` and normalizes the toolchain grammar there (the tool owns syntax):
  `problem_kinds`, `member_demands`, `bean_demands`, `mock_impossible`,
  `package_symbol_demands`, `blamed_files`, `stack_files`, `unit_match`, failures'
  `class`. The engine's phrase tables (`SUPERTYPE_CONFLICT_PHRASES`,
  `CASCADE_PHRASES`, `is_cascade`, `error_locations` scanning, the `symbol:`/`location:`
  regexes) are DELETED, and every cache door (memo, wave, verify) refuses pre-schema
  verdicts — a stale cached verdict costs a rebuild, never a wrong decision. Build
  verification output (`verify_project`) is normalized through the TOOL's own parser,
  so deferral reads fields, not the reason string.
- **O2 — registry attribution.** Ownership answers "which task declares this path /
  exports this type" (queue+complete+error records joined by exact declared identity);
  the fuzzy `_norm_stem`/`_matches_class`/`_selector_of` guessers are gone and the
  selector→class join is the tool's typed `unit_match` — an ambiguous match falls to
  the unit's own scoped build (a compile, never a misattribution).
- **O3 — structure from the contract.** Supertype names ride the verdict's typed
  `supertypes`; port materialization is registry+filesystem, not source-grammar regex.
- **O4 — one canonicalization boundary.** `canonicalize_tree()` is the ONLY place the
  engine admits to touching the tree (wrapper chmods, import repair), every fingerprint
  is taken after it, cache writes are atomic (`os.replace`), and a killed build's
  poisoned output heals across stacks — Maven dumpstreams, Gradle test-results,
  truncated `.tsbuildinfo` — through the one `heal_interrupted_build` boundary.
- **O5 — shared-tree deferral is arithmetic.** While sibling payloads are unwoven the
  module-wide build poisons every verdict; the untangling survives but now reads the
  pending-export registry and typed fields, never CamelCase tokens scraped from prose.

Detection vocabulary that still lives engine-side (`_suite_command` shapes,
`BUILD_FILE_NAMES`, JDK inventories) is derivation/whitelist data, not blame — the
deferred R5 pass moves it to stack-skill data the same way.

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

Before running, the engine's canonicalization boundary (`canonicalize_tree`, O4) deterministically adds missing same-project imports to test files (a tester can reference a production type in another package without importing it; an added import never changes behavior) — and because EVERY verdict fingerprint is taken after that boundary, the engine's own repair can never masquerade as an agent's tree change. The name scanners read a **comment- and string-stripped view** of each file — an identifier mentioned in prose is not an import demand (an earlier build inserted a classpath-colliding `A` into a production file because a comment said "A lone late sample"). FQN resolution uses an **external type index** built once per build manifest and cached at `blackboard/external-index.json`.

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

Every assistant turn re-sends the whole transcript, so a session's cost is driven by its number of tool calls. Every prompt therefore states an explicit budget (discovery, mapping and container 10 calls, tester 8, coder 6, evaluator and assembly 12, `agent-strategy-architect` 14 and `agent-planner-architect` 22 per bounded-context session — both re-measured on 2026-11-26 against live sessions, after the brief collapsed every input into ONE pre-concatenated file (strategy slice + digest slice + symbol table + quickref + the resolved stack skills, read fully once) and capped the lint loop at THREE runs; the planner's mapping tables are still loaded only when its digest slice lists `unmapped_duties` — the matched rows ride the slice itself — and bounded-context sessions now run as a capped concurrent wave (`settings.PLAN_PARALLEL`), because a session's wall clock is dominated by the model DECODING its 40–85KB draft, not by its tool calls), database 12 (14 was needed only to hunt skill folders; the profile now gives exact paths), security 8, performance 8, AI 8; a coder batch shares a budget that scales with its unit count, 4 + 3 per extra unit, and a tester batch 3 + 4 per extra unit), and on the Copilot backend a session streaming past twice its budget (plus a slack of 4 calls) is killed mid-run rather than left to burn tokens. Budgets cap one session; the *number* of sessions a unit may bill is capped by the attempt ledger (see [Scheduling and failure handling](#scheduling-and-failure-handling)) and by lifetime weave-reject bounce caps.

Because prompt size multiplies across every turn of every session, every profile and skill is written telegraphically and delegated by tier (planning facts in architect tables, bodies and test DSL in the coder/tester tier), and the docs whose size is a live risk carry **gauntlet-pinned caps** — the ones raised this cycle (architect mapping tables, AI rulebook) were raised only by new grounded rows or gate-enforced vocabulary, each with the growth recorded in the check's own name. Compression regressions — a doc teaching an invented payload key, or an approximate enum where the writer demands the canonical one — are pinned mechanically by the gauntlet's K-section (doc-vs-schema checks), and every writer rejection prints an `--emit-template` hint showing the true contract.

`python3 orchestrators/session_audit.py` reads the local Copilot session records and reports, per agent, the turns, tool calls, and tokens, flagging calls that left the agent's own inputs (skill folder listings, orchestrator or AST-tool source reads, other tasks' records, board-folder listings such as `ls blackboard/coder-changes`, `git`); use `--since-hours`, `--budget-report`, or `--json` to slice the view.

`--burn-report` answers the *why*: it attributes every tool call in a session to `size × the turns that re-sent it` (a 5k-token skill loaded on turn 1 of a 12-turn session costs ~60k; the same skill on turn 10 costs 10k), and prints input/output/cache-read totals plus the worst single-turn output. `python3 orchestrators/session_audit.py --burn-report --role planner --since-hours 96` (roles `strategy` and `planner` after the 2026-11-20 split; `architect` still matches historic monolith sessions) is the check to run after any prompt, skill or emission-shape change — output tokens are the expensive class, and the plan phase is where they are spent.

### Board status and observability

`python3 orchestrators/status.py` is a read-only, restart-surviving view of the board:

- queue / complete / quarantine counters, queue by stage, and the most recent completions;
- for every quarantined unit, its attempt-ledger state (budget left, grants used, whether its last failure has been shown to a coder) and quarantine reason — the exact questions the drain answers when relaunched, so the operator sees *why* the board is where it is without reading a log;
- whether an orchestrator process is currently running;
- a **token rollup** read from the backend's own session-state events: sessions, input and output tokens since launch, cost per completed unit, and a watchdog line for the largest single session (a runaway is visible continuously instead of by post-mortem).

Every session log carries a `[live]` heartbeat — turn opens/closes and each counted tool call with elapsed time — so a healthy multi-minute drafting turn is never again mistaken for a stall (2026-11-25 supervision fix), and drain logs carry timestamps and per-pass heartbeats for the same reason.

## Gauntlet: engine regression suite

`gauntlet/` is the pre-flight for the pipeline itself: seconds of compute instead of hours of a live 80-unit drain discovering the same bug at agent-session prices.

```bash
python3 gauntlet/run_gauntlet.py            # skill-script + engine decision suites
python3 gauntlet/run_gauntlet.py --weaver   # + the Java weaver JUnit (needs Maven)
```

| File | Tests | Allowed vocabulary |
|---|---|---|
| `gauntlet/test_skill_scripts.py` | writer payload schema; run-test-tool normalization; multi-document YAML write gate; the sanctioned scaffold tooling (`repin-parent` surefire guardrail), the skill-law content pins (tester substitute-credentials/aggregate-decode laws, packaged migration directory, composition-root placement check, WebFlux handler-marker law) and the security pins (reference schema keys equal to `ddd.SECURITY_SPEC_KEYS`, no engine mechanics or restated schema inside the rulebook, IDOR / duty-closure / token-form laws, profile-body equality, one-skill allow-list and one-file write scope) and the architect-consumption pins (the split's phase isolation: the strategy profile carries no decomposition law and the planner profile no strategy law; digest ingestion; rule (y); the 26-letter restatement ban — the refusal classes live in the skill and the ERR-pointer linter, not in the resident profiles), and the Spring mechanism table (every capability token mapped, unrealizable tokens marked as NO mechanism, EVERY framework-backed row naming the identifier the intent must spell - a bare paraphrase fails the case - Boot property keys verified against the configuration metadata on disk, grant present in the architect profile, and the TIER SPLIT enforced: no execution DSL in the planning file, the idioms present in the coder/tester-tier `tech-stack/spring-security` the framework skills point at, and the skill-name-collision law), and the (z)-family carrier pins (SE/PF: vocabulary PARITY across engine, skill, schema, architect table and profile — one hand-maintained list in five places is the R1 disease wearing a vocabulary hat; every cited Boot property key and framework class verified against the configuration metadata and the jars ON DISK, absent jars skip rather than pass; the writer-scope, cap and tier-split laws of the performance and AI tables; the memory-tier and delivery bodies pinned at both tiers; the writable-channel and stub-precedence laws) | **compiler output text lives only here** — this tool owns syntax (179 cases) |
| `gauntlet/test_engine_decisions.py` | attribution, wave sharing, attempt ledger + grants, auto-grant, plan-validity refusals (reserved package segments, phase-order claim skip, consumer closure of published streams, signal-returns-need-semantics, registration XOR, real-substrate adapter pairing, request-path integration slice, ingress idempotency duty, correction value axis, promised-mechanism duty, floor pairing, stage-1 test-artifact path separation, handler-marker registration impossibility), security spec gate (language-separation leak scan, deny-by-default, IDOR, disclosure, duty closure, token and unit_kind enumerations), scaffold identity by export marker, security duty-claim coverage (id + capability pair) with its three phase-order skips, the phase-1 surface table and the spec↔strategy join, the (y1)/(y2)/(y3) placement refusals, the risk register (a control cited or an accepted posture with a residual, and the pipeline printing every entry), the always-secure default with its one verbatim-quote waiver (SB/SC: coverage gate, paraphrase refused, unverifiable waiver means required), `--replan` archiving, and the stack-isolation law over the Spring security skills (no servlet identifier inside a WebFlux code span - the pin carries a self-test proving a line-scoped check would have missed it), rollback holes, assembly structural probes (incl. request-path evidence, base-document substitution discipline WITH the test-witnessed exemption, config native-format re-serialization), terminal tree verdicts, terminal suite gate + reopen attribution, observability floor + claims, the rule-(z) joins with their near-miss and false-positive guards (SF1–SF20, incl. the self-tests proving a check can fail), the performance-spec and AI-spec gates (PG: deterministic measurement enums, the wall-clock refusal, verbatim surface keying, the closed 14-token vocabulary, topology termination / approval-ceremony / memory-tier / semantic-scoping laws, the transport-free law, the spec_ref discharge rule), and the planning-duty claim channel with its --replan remedy | structured fields only — no compiler strings (372 cases) |
| `ast_weaver_tools/.../JavaASTWeaver*Test.java` | weaver grammar (generics, supertypes, static reconcile, idempotency) | Java — it *is* the Java tool |

Two rules keep the engine stack-agnostic — and since the 2026-11-25 verdict contract
the first has teeth: orchestrator modules bind every decision ONLY to typed verdict
fields, registry lookups and filesystem facts (prose survives for display), which SP16
pins as a dead-vocabulary ban plus behavior doors (a pre-schema memo is refused; an
ambiguous typed selector falls to the scoped build); `orchestrators/stacks.py` is the ONE stack-toolchain registry — markers, wrappers, verify commands, scoped-test shapes — and no engine module may read a build marker or command shape itself (five private copies had drifted behind every incident before the 2026-11-26 consolidation, which also removed one ecosystem's FILE NAMING from the generic migration gate; consumer decisions were golden-verified byte-identical); and every incident class from the
live drains has a pinned case here — silent payload-key drops (W), javac line shapes (G), receiver-vs-enclosing attribution (A/B), scheduling-hole aborts (A5-A6), rebuild storms (C), blind granted attempts and grant livelock (D/E), doc-vs-schema regressions (K, incl. multi-document YAML), red-recovery pins (H), import-repair pins (R), full-tree attribution and sibling-wave gates (A19-A26), contract-regression reopen (A25-A26), prose-vs-table plan refusals (G21-G24), rollback dangling-consumer surfacing and reopen (A27-A28), hollow-boot and slice-discovery structural gates (S1-S5), late assembly scheduling and NEVER-BOOTED terminal verdicts (T1-T5), gate-only stage 4, zombie-id supersede and ledger continuity (U1-U4), the unconditional observability floor and step-log claim coverage (V1-V8), the security spec laws, duty-claim coverage and the id+capability mapping pair (S1-S25), the surface table, the spec↔strategy join and the placement laws (Z1-Z17), and `--replan` (with the doc pins Q1-Q20, including the architect's consumption of the spec). Shared-literal drift and its writable-channel cousin (SF1–SF20), the planning-spec gates and claim law (PG1–PG19), and the tier/parity/grounding locks across every new carrier (SE1–SE11, PF1–PF13) are pinned the same way. **No merge without a case**: a fix that ships without a fixture here is how next week's incident is born — and since 2026-11-19 the pins audit the fixers too: three same-day defects in NEW code (a law block before its binding, a needle broken by a line wrap, an assertion disagreeing with its own refusal) died at this suite rather than at a drain.

## Repository layout

```text
.
├── orchestrators/                 # Pipeline implementation, split by responsibility
│   ├── orchestrator_opencode.py   # Entry point: OpenCode backend
│   ├── orchestrator_github.py     # Entry point: GitHub Copilot CLI backend
│   ├── family_paths.py            # sys.path bootstrap for the family folders below
│   ├── settings.py                # Repository layout, stages, schema, timeouts, call budgets
│   ├── workspace.py               # Seed and project-root resolution
│   ├── prompts.py                 # Agent prompt templates, batch messages, collaborator tables
│   ├── ddd.py                     # Discovery, context-map, strategy, security/performance/AI spec gates and the directives
│   ├── assembly.py                # Stage 4: scaffold smoke-test detection, task emit, boot gate
│   ├── closure.py                 # Test-import closure audit; emits missing producer tasks
│   ├── refactor_audit.py          # Engine-computed diffs of what stage-3 sessions changed
│   ├── session_audit.py           # Per-session tool-call/token audit + --burn-report attribution
│   ├── status.py                  # Read-only board status, ledger states, token rollup
│   ├── verification.py            # Framework build/check gates + Docker access gate
│   ├── stacks.py                  # ONE stack-toolchain registry (markers, commands, wrappers)
│   ├── dispatchers.py             # Red-phase/AST/weaver dispatch, weave baseline, red recovery
│   ├── test_gate.py               # Green gate: import repair, external index, wave verdicts,
│   │                              #   bean_demands attribution, memoized verdicts, WOVEN-CLEAN
│   ├── attempt_ledger.py          # Cross-pass TDD attempt memory: billed-session grants
│   ├── agent_runners.py           # Subprocess plumbing and log tails
│   ├── tdd_engine.py              # execute_with_tdd, drain_queue, batching, deferrals
│   ├── telemetry.py               # Optional OpenTelemetry integration
│   ├── orchestration/             # pipeline family (root: pipeline.py - phase ORDER)
│   │   ├── pipeline.py            #   thin entry glue: stamped logging, CLI re-export, sequence
│   │   ├── cli_args.py            #   shared argparse shape
│   │   ├── run_phases.py          #   phase ORDER: entry gates, DDD, strategy, specs, drain call
│   │   ├── plan_gates.py          #   skip/reason/risk-surfacing helpers
│   │   ├── plan_flow.py           #   planning loop: sessions (serial root + parallel wave),
│   │   │                          #     claims, routed repair, ONE batch emit
│   │   └── drain_flow.py          #   watch/single-pass drain, breakers, terminal tree
│   ├── task_contract/             # tasks family (root: tasks.py - record contract)
│   │   ├── tasks.py               #   validate() + stable re-export surface
│   │   ├── task_identity.py       #   record schema/shape: ids, exports, ast_hints, stage-0 families
│   │   ├── task_signals.py        #   prose-vs-table signals from unit intent
│   │   └── task_rules.py          #   mechanized plan rules + batch consistency join
│   ├── task_creation/             # task_queue family (root: task_queue.py - queue ENTRY)
│   │   ├── task_queue.py          #   claim/lint/emit/routing top layer + re-exports
│   │   ├── plan_drafts.py         #   FACT/LAW/VERDICT state machine, sidecars, snapshots
│   │   ├── plan_board.py          #   queue records: index, ids, quarantine, stage-0 recovery
│   │   ├── plan_wiring.py         #   deterministic rewrites: expand/hydrate/mirror/wire, anchors
│   │   └── plan_laws.py           #   every plan-time law check as pure verdict functions
│   └── backends/                  # CLI adapters (the `backend` parameter of pipeline.run)
│       ├── opencode_backend.py    #   ``opencode run`` phase runners
│       └── copilot_backend.py     #   Copilot CLI profiles, JSON events, budget kill
├── gauntlet/                      # Engine regression suite (see above)
│   ├── run_gauntlet.py            # Pre-flight runner (--weaver adds the Java JUnit)
│   ├── test_skill_scripts.py      # Runner/writer normalization cases (owns compiler vocabulary)
│   └── test_engine_decisions.py   # Engine decision cases (normalized fields only)
├── seed/                          # Input business descriptions
├── ast_tools/                     # AST extractor executables (e.g. ast_extrator_java)
├── ast_weaver_tools/              # Code-weaver executables (e.g. ast_weaver_java)
├── blackboard/
│   ├── domain/                    # Discovered domain boundaries (optional security_directive waiver / ai_directive trigger)
│   ├── context-map/               # DDD context maps
│   ├── queue/                     # Tasks waiting to run
│   ├── complete/                  # Completed tasks, execution strategies, security/performance/AI specs
│   ├── error/                     # Invalid or failed tasks with error details
│   ├── archive/                   # A domain's retired PLAN (--replan): strategy, specs, stage 1-3 records
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
│   ├── agents/                    # OpenCode agent definitions (bodies mirrored byte-identical; size/marker pins)
│   └── skills/                    # Architecture, stack, coding, testing, and AST guidance
│       ├── tester-framework/      # Language/framework testing skills + run-test-tool.py
│       ├── coder-framework/       # Coder rules (java-springboot, java-standard-best-practices)
│       ├── assembly-framework/    # Per-stack boot skills (java-springboot, python-fastapi, typescript-nestjs)
│       ├── ast-dispatcher/        # Language detection and AST executable dispatch
│       ├── code-weaver-dispatcher/# Language detection and code-weaver dispatch
│       ├── read-write-file-ddd/   # Blackboard writers (red-phase, coder-changes, evaluate-results, ...)
│       ├── architect-practices/   # DDD, context mapping, the decomposition DAG, and the security/performance/AI strategy rulebooks (+ spec schemas)
│       ├── tech-stack/            # Technology selection, migration, and the stage-1/2 Spring idioms (security, performance, AI composition)
│       ├── tech-stack-architect/  # Architect-tier stack guidance (java-reactive-patterns, spring-security-architect, spring-performance-architect, spring-ai-architect)
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
| `--lint FILE` | Validate ONE planning draft file against the single-file law (schema, dangling forward pins); the batch laws — duty claims, step-log ownership, the shared-literal join, provider closure — are DEFERRED to the engine's batch `--emit`, then exit. This is the planner agent's finish gate. |
| `--retry [ID ...]` | Move quarantined tasks from `blackboard/error/` back to the queue — all of them, or only ids matching the given patterns — then continue the run. |
| `--replan SLUG ...` | Archive one or more domains' PLAN (execution strategy, security/performance/AI specs, stage 1-3 records) to `blackboard/archive/` and re-run the strategy, security, performance, AI and task phases for them on this launch. The remedy the pipeline prints when a strategy names no inbound surface or a spec predates its decomposition. Stage 0 and stage 4 records, and all delivered sources, stay. |
| `--plan-only` | Run every PLAN phase (discovery through the planner sessions and the batch `--emit`), then STOP before the docker gate and the drain with exit 0 - the supervised way to measure plan cost: zero execution sessions billed, the queue holds the finished plan. Under the R2/R5 resume machine a relaunch re-validates compliant drafts for FREE (a law bump re-judges bytes without re-billing sessions), so a killed or refused plan phase never pays twice. |
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
- `ast_hints` (optional, required from the architect on planning stages) is validated structurally at emit time: its required keys are `package`, `implements`, `dependencies`, `methods`; dependencies pin each consumed type to its producing task; methods carry the exact signature and return spelling. The optional vocabulary keys `meters`, `routes` and `config` carry the shared literals (see rule (z)) — one owner per name/route, one shape per property path, cited VERBATIM by every consumer, joined by six emit checks. A cross-task gate rejects a plan whose pinned collaborator's own table does not spell the surface its consumers use. Older boards without the fields remain readable (planning-time enforcement only).
- `observability` (optional, stage-2 units): `{"step_logs": [...]}` — the VERBATIM execution-strategy step logs this unit OWNS and its stage-1 test must assert. The field, not intent prose, is the machine surface: vocabulary overlap in prose proves nothing ("samples", "ingress" appear everywhere in an ingestion plan) while a claim is checkable. Emit refuses plans that leave a planned entry unowned, double-claim one, or claim an entry the strategy never planned — and refuses the strategy itself if its observability floor (correlation key, step logs, audit trail, metrics, export) is absent or incomplete: the audit + logging floor is UNCONDITIONAL for every executable context, whether or not the business description asked for it. Boards without a strategy file (legacy, unknown stacks) skip the rule; the attempt-ledger contract hash ignores absent optional fields, so introducing this key never re-armed budgets on resumed boards.
- `execution-strategy-<slug>.json` (written by `agent-strategy-architect`, phase 1 of the split): the domain's plan — `bounded_contexts`, `modules`, `layers`, `build_order`, `module_layout`, `persistence`, the `observability` floor, `risks`, and `surfaces`: ONE entry per inbound surface (`{name, kind, context, operations, traced_from}`, `kind` in `http|consumer|job|cli|internal-call`). The `name` is a JOIN KEY, not a label — the spec's row and the enforcing unit's intent both copy it, which is what makes rule (y2) checkable. A bounded context that receives nothing from outside declares itself in `contexts_without_inbound` WITH a reason: silence is not a decision. `ddd.validate_strategy` is phase 1's post-check on both backends, so the file cannot land without its surfaces table; a strategy written before the contract existed stops the run with the `--replan <slug>` remedy.
- `security-spec-<slug>.json` (written by `agent-security-architect` into `blackboard/complete/`, one per domain): the domain's access-control and data-protection contract — `principals`, `trust_boundaries`, `authorization_matrix` (one row per entry of the strategy's `surfaces` table, its `surface` field copying `surfaces[].name` verbatim, each carrying `ownership_rule`, `decision_point`, `effect_on_deny` and a `test_duty`), `data_classification` (class, PII/secret flags, at-rest/in-transit protection, log/error/export visibility), `invariants`, `secrets`, `error_policy`, and `duties` — the handoff that says which rule needs discharging, with what capability and in what shape. The byte contract is the skill's `references/security-spec.schema.json`, and the artifact is engine-gated, not merely documented: `ddd.validate_security_spec` refuses a row whose `default` is not deny, a row addressed by client-supplied ids with no ownership predicate (the IDOR law), `restricted` data allowed on any surface, a rule that discharges no duty, a dangling `spec_ref`, a capability token that is not an abstract kebab token, and any realization name — the language law that keeps this phase's output stack-agnostic instead of merely claiming to be. It carries no top-level `id` and queues no task, so the queue index, status board and drain never mistake it for work, and the security step writes exactly one file. It is checked by the orchestrator after the session ends (both backends pass `ddd.validate_security_spec` as the phase post-check) and the agent is never given a self-validation command: the judged party is not its own witness. Its inputs are routed deliberately too — the execution strategy arrives through the read tool, because the reader refuses files that carry no `schema_version`, while the boundary slice and context map go through the reader so their own gates run first.
- `performance-spec-<slug>.json` (written by `agent-performance-architect`, one per domain, unconditional): `workload` (one entry per declared surface name, verbatim, or a reasoned exemption), `budgets` (each with a `measurement` from `PERFORMANCE_MEASUREMENT_KINDS` — there is no wall-clock member in that enum by design), worst-case `invariants`, and `duties` (`unit_kind` from `PERFORMANCE_UNIT_KINDS`). `ddd.validate_performance_spec` refuses paraphrased surface keys, off-plan exemptions, non-deterministic measurements, and budgets or invariants that discharge no duty; the pipeline prints its risk register every launch and stops on its open questions. The decomposition claims each duty (spec_ref + capability verbatim in a stage-2 unit) or the emit gate refuses; the mapping to pools, semaphores and cache mechanics lives in `tech-stack-architect/spring-performance-architect` (honest `no framework mechanism` cells where Boot supplies nothing).
- `ai-spec-<slug>.json` (written by `agent-ai-architect` — which runs ONLY when the slice's `ai_directive{required:true, quote}` survives the verbatim check against the seed file): `model_roles` (statefulness + `memory_technique`, the tier decided by triggers the gate enforces where provable: an approval-bound role is durable, a durable role's concept must exist in `persistence.data_model`, semantic memory requires the retrieval-scope guard), `capabilities` keyed verbatim to surfaces/flows from the CLOSED 14-token vocabulary (`AI_CAPABILITY_TOKENS`) with deterministic `AI_MEASUREMENT_KINDS` proofs, `duties` whose `spec_ref` may cite ONLY rule rows (roles and assumptions are context — a duty discharging them has no token to match), and the mandatory `offline-model-port` invariant. `ddd.validate_ai_spec` additionally refuses delegation topologies without a `loop-budget-cap` invariant, approval gates around nothing, and TRANSPORT names (SSE/websocket/gRPC — the protocol is phase 2's mapping onto the concrete surface). Every token maps in `tech-stack-architect/spring-ai-architect` — identifiers grounded against the installed jars by the gauntlet, never recalled — and composes in `tech-stack/spring-ai`, split into `### Reactive` and `### Blocking` blocks exactly like the chain DSL precedent; the prompt contract's home is a Java SOURCE TYPE, because the writable-channel gate refuses template files for any unit.

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
- A structural supertype conflict in the unit's own file is deferred, not charged, while the supertype's producing task is still unresolved: the adapter cannot converge on a moving port. The classification is the runner's typed `problem_kinds` verdict — the engine reads no phrase (O1).
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
- **Agent behavior:** edit `.opencode/agents/` and the matching `.github/agents/` profiles — keep the bodies byte-identical across backends (pinned), respect each document's size cap, and remember the K-section pins doc-vs-schema truth: a profile that teaches what the writer/gate does not accept fails the suite.
- **Plan contracts:** the `ast_hints` rules live in `orchestrators/task_contract/tasks.py` (schema) and `orchestrators/task_creation/task_queue.py` (the cross-task gate, the rule-(z) joins `_shared_literal_errors`, the writable-channel gate `_writable_channel_errors`, the planning-spec claim gate `_planning_claim_lines`); vocabulary and emission duties in the architect skill and profiles.
- **Security posture:** the requirements laws live in `.opencode/skills/architect-practices/security-strategy/SKILL.md`, the byte contract in its `references/security-spec.schema.json`, and the machine gates in `orchestrators/ddd.py` (`validate_security_spec`, the key list, the leak vocabulary) plus `orchestrators/task_queue.py` (`_security_claim_errors`, the scaffold's export marker). Changing a key, an enum, or the allowed vocabulary means changing the skill, the reference, the gate and the Q/S gauntlet pins together — the pins exist precisely so that a rename on one side fails a case instead of blinding a gate. Mechanism naming for a stack belongs to the tech-stack skills and the architect, never to this phase.
- **Performance posture:** same triangle for `performance-strategy` + its schema + `ddd.validate_performance_spec` (closed `PERFORMANCE_MEASUREMENT_KINDS` — adding a kind means touching skill, schema, gate and the PG/SF pins together; a timing kind is the refusal this enum exists to keep).
- **AI posture:** `ai-strategy` + schema + `ddd.validate_ai_spec` (`AI_CAPABILITY_TOKENS`, `AI_UNIT_KINDS`, `AI_MEMORY_TECHNIQUES`, the directive witness `ai_required`/`validate_ai_directives`) + the claim gate; and because the vocabulary lives in five carriers, **PF12 parity is the merge check** — engine, skill table, schema enum, architect mapping table and profile list must agree exactly. Mechanisms map in `tech-stack-architect/spring-ai-architect` (grounded against the installed jars by PF8) and compose in `tech-stack/spring-ai`.
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
- **Queue behavior:** change `orchestrators/task_creation/task_queue.py` and `orchestrators/tdd_engine.py`; both backends reuse them.

Keep both backends' agent profiles aligned when changing the workflow, and run `python3 gauntlet/run_gauntlet.py` before and after — no merge without a case.

## Project status and evaluation runs

The pipeline is benchmarked against `seed/002_description.md` — and, from 2026-11-26, a second subject: `seed/003_description.md`, an AI chat-agent service that exercises the `ai_directive` path — with the blackboard wiped clean between runs. The recorded reports live in the repository root:

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
| `PROJECT-INSPECTION-2026-11-18.md` | The security layer's first live drain and the defect class it exposed (§A1–A6), then the response: rule (z) — shared literals (meters, routes, property paths) tabled with one owner and cited VERBATIM, joined by six emit checks, a twin-table identity and a writable-channel gate (B5–B6); the anti-convergence closure at every message surface (B5–B6); the two new stack-agnostic planning agents — `agent-performance-architect` (unconditional load floor, deterministic measurements) and `agent-ai-architect` (directive-triggered, 14-token closed vocabulary, memory/delivery/topology laws) — with spec gates, claim channels, architect-tier mapping tables grounded against the jars on disk, composition-tier bodies, and vocabulary-parity pins across all carriers (B7–B21). Five live roots diagnosed as plan-tier frozen contracts, not coder failures; the 11-unit board left frozen as the class's exhibit. |
| `PROJECT-INSPECTION-2026-11-20.md` | The architect split: the monolithic `agent-architect` became `agent-strategy-architect` (phase 1) + `agent-planner-architect` (phase 2, ONE session per bounded context); the (a)–(z) invariant wall moved out of the resident profiles into `task-decomposition-dag` and the deterministic `--lint`/`--emit` tier (every refusal an `ERR [id.field]` pointer, edit-not-rewrite remedy); the phase-2 digest now attaches each duty's matched mapping-table row and the tables' build coordinates and slices per context (zero table loads when the slice maps — 27/27 on the live board); the engine claims drafts (id renumbering, dangling pins), emits the batch itself, and routes refusals to bounded repair passes. Static carrier measurements, four new-code defects found and pinned (X1–X4), and the next drain's `--burn-report --role planner` as the authority on what it was worth. |
| `PROJECT-INSPECTION-2026-11-26.md` | The seed-003 validation: twelve live root causes stopped and fixed at their layer (discovery cohesion + per-slice directives, mapping wiring closure, planner budgets + the one-file brief, the FACT/LAW/VERDICT resume machine after two skill-prose invalidation storms, routed-repair caps, stage-0 self-heal after a silent scaffold destruction, the `stacks.py` toolchain consolidation, death-shim ordering, depth-asserting goldens); the engine re-org into four importable families (golden-verified byte-identical); the parallel planner with `{type, context}` sibling anchors (final plan pass: 3m26s, 3 billed sessions, 222 tasks); and the second plan audit's four findings closed at the root — authorization-row closure in the claim gate, covered-row test-case inheritance in the digest, the commitments channel through the phase-2 digest, and the one-trust-domain-one-credential-home law — with the gauntlet landing 179+372 green and the residuals named: the queued plan predates the last laws (replan pending), and the seed-003 drain is the next experiment. |

The current state (2026-11-26): the redesigned loop met its test subject. On a fresh
AI-domain seed (`003`), the plan phase now completes with **zero operator firefighting in
the final pass** — 222 tasks in 3m26s across 3 billed sessions (parallel context waves,
anchor-bound sibling pins, routed repairs) — because every failure class of the previous
weeks was moved from law prose into machine structure: the FACT/LAW/VERDICT resume machine
makes a skill edit physically incapable of re-billing a plan; stage-0 self-heals from the
agent's own draft; one registry answers every stack-toolchain question; and a two-round
audit of the emitted queue caught what all the gates had missed (three authorization rows
scheduled only through another duty's `covers`, a map-adjudicated serialization posture
invisible to decomposition, split-brain credential stores) — each fixed generically at the
channel that lost it: the row-closure gate, the digest's commitments field, the spec's
trust-domain law. The engine itself was restructured the same day: four family folders
behind unchanged public imports, every split proven byte-identical by goldens that now
assert depth. Gauntlet: **551 cases green**. Residuals, named: seed 003's queue predates
the last three laws (the designed `--replan` closes that), and the execute side — the
O1–O5 verdict contract — still awaits its first live drain on this seed.

Preceding state (2026-11-25): the orchestrator itself was the subject. A cold
plan-phase family on `seed/002_description.md` (runs cold4–cold6) proved the new
resilience and verdict machinery end to end: **103 tasks queued, zero defective tasks
shipped** — every machine-checkable dimension audited from the delivered bytes
(structure, floor coverage, security/performance bindings, statuses, draft economy,
cross-context flows) — while refusal-to-repair collapsed to routed per-context rounds
(56–176K vs the old 500K+ storms), a killed run's paid drafts RESUMED at zero sessions
twice, and the full plan landed ~3.4M input tokens with ~13% of the waste attributable
to two bugs found and fixed inside the family (the z3 twin-mirror livelaw, and the
no-op guard that fataled a healthy batch while another bucket still had rounds). The
execute-side verdict contract (O1–O5) is suite-pinned but awaits its first live drain.
Preceding state (2026-11-18/19): the 11-18 drain delivered a booting service but quarantined 11 units whose five roots proved to be **contradictory frozen contracts, not coder failures** — the defect class rule (z) now refuses at emit. The board is held as the exhibit; the fixes are complete and pinned (465 gauntlet cases), and a fresh validation drain is the next experiment. The previous clean headline (2026-11-17, wiped board and regenerated telemetry service): **63/63 units complete, zero quarantined, 131/131 frozen tests green, the application boots with the REAL domain context** — composition root at the ancestor package (enforced by a container placement check), packaged classpath migrations that travel with the jar (boot re-proven from a foreign cwd), the seed's reordering rule LIVE on the request path, every drop outcome counted and audited, and `assembly.detect` returning **zero problems**. ~56 billed sessions / 7.43 M input tokens, every repair closing at zero billed sessions, the plan-phase burn bounded and attributed by the watchdog. This drain also closed the last known failure family: the shape-defect PLAN (every test task emitted on the production path) now dies at emit under rule (w), the impossible handler registration under rule (x), the unwinnable frozen fixtures under the tester-skill laws, and the gate-vs-contract collision via the test-witnessed probe exemption — the same-day arc from `PROJECT-INSPECTION-2026-11-16.md` PART I ("green board, silently missing integrations") to `PROJECT-INSPECTION-2026-11-17.md` §1 ("every seed rule proven by the artifact's own tests AND a live request-path probe"). Residuals are named, not hidden: `PROJECT-INSPECTION-2026-11-17.md` §5 (inert double registration, a promise/duty direction rule (t) does not police, the silent terminal subscriber, the two-set migration seam, range-less metrics accepted unbounded by operator decision, the test-witnessed H2 boot default, and the plan-phase transcript size as the honest remaining lever).

This remains an experimental evaluator and orchestration project, not a guarantee of production-ready generated software. Agent runs can create and modify files, install project dependencies through their workflows, and execute build commands. Review generated code, migrations, security decisions, and test results before using them in a real environment.
