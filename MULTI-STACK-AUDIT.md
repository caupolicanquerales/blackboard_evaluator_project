# Multi-Stack Coupling Audit — orchestrator process vs. language/framework portability

Date: 2026-11-12. Scope: `orchestrators/*.py` (23 modules, ~6.7k lines, Python),
`.opencode/skills/**` (dispatchers + skills), `.opencode/agents/*.md`, `ast_tools/`,
`ast_weaver_tools/`, `mcp_server/`. Note: there is no `prompt.ts`; the prompt layer is
`orchestrators/prompts.py`.

## 1. Verdict

**The process skeleton is language-agnostic and provably so.** The queue/DAG, stage
machine, budgets, red/green gates, wave caching, quarantine/revert, feedback templates
and the blackboard protocol operate exclusively on task JSON records, blackboard files
and subprocess commands — never on a language (`tdd_engine.py:104-123` is explicitly
designed this way: "ownership comes from the task records themselves... in every
layout and language").

**But a non-Java end-to-end run stops at four hard points (§3)** - three remain open
and are scheduled as tranches in §6/§8; the fourth (P0-4, the architect's skill
permission allow-list) was found during the fix pass and is already closed (§10).
Several engine heuristics would additionally misbehave (fatal-abort or misattribute)
on Python/TypeScript trees even after the hard points are fixed - Tranche 2.

## 2. What is already neutral (works for any stack as-is)

| Concern | Where | Evidence |
|---|---|---|
| Toolchain output parsing | `.opencode/skills/tester-framework/run-test-tool.py` | Correct boundary: tool owns syntax, engine reads normalized fields (`status`, `member_demands`, `problem_kinds`, `bean_demands`, `classes`). Patterns cover javac, tsc, pytest, go, jest, cargo, unittest. |
| Blame / cascade attribution | `test_gate.py:366-401` | `SOURCE_EXT` + `CASCADE_PHRASES` are deliberate multi-toolchain tables ("not Maven-only", line 368). |
| Green-gate mechanics | `test_gate.py` (wave gate, fingerprints, memos) | Content-fingerprint based; `_tree_wide_failure` "speaks only the runner's status contract". |
| Build/typecheck verification | `verification.py:43-92` | Detection table: Maven, Gradle, Flutter, Angular, npm/tsc, Go, Cargo, Python. |
| Assembly gate | `assembly.py:11,37-76` | "Stacks are DATA": `STACKS` registry row + probe + skill per stack; no structural `if stack == ...` elsewhere. |
| Stage 0 scaffolding | `mcp-server-alternatives/` | 3 MCP servers: Spring Boot, FastAPI, NestJS. |
| Closure strategies | `closure.py:161-178` | `gaps()` dispatch: `_java_gaps`, `_python_gaps` (stdlib AST), `_ts_gaps`; unknown stack ⇒ `[]` (never fabricates work). |
| Test-name normalization | `test_gate.py:760-781` | `_ident_tail`/`_norm_stem` handle Java, Go, Python, TS conventions. |

## 3. Hard blockers (process cannot complete a non-Java unit)

### P0-1. The coder payload has no executor outside Java
The stage-2 loop is *payload → code-weaver splices it into the tree → green gate*.
`code-weaver-dispatcher/builders/` is a proper Strategy+Registry, but
`python_weaver.py`, `typescript_weaver.py`, `go_weaver.py` are stubs —
`build()` returns `None` ("No code-weaver executable is registered … yet").
Only `java_weaver.py` runs a real tool (`ast_weaver_java`, JavaParser). Every
non-Java unit would bounce as `weave-reject` twice (`dispatchers.py:377`,
`MAX_WEAVE_REJECT_BOUNCES = 2`) and then quarantine.
`ast_tools/` and `ast_weaver_tools/` contain **only** `ast_extrator_java` and
`ast_weaver_java`.
Mitigating: the AST-context side degrades gracefully (neutral `usage_lines` fallback,
`ast-dispatcher/builders/base.py:115-142`), so only the weave side dead-ends.

### P0-2. `tester-framework/` and `coder-framework/` skills are Java-only
- `tester-framework/` has only `java-junit5`.
- `coder-framework/` has only `java-springboot` + `java-standard-best-practices`.
The agent profiles say: *"read `tester-framework/<key>/SKILL.md`; none ⇒ stop"*
(`agent-tester.md:42`) and *"read `coder-framework/<lang>-standard-best-practices`
then `<lang>-<framework>` … none ⇒ stop"* (`agent-coder.md:29`).
A Python/TS run therefore halts at **stage 1**, before the weaver even matters.
The per-stack skill pack the architecture delegates framework rules to is
half-populated: scaffold, tech-stack and assembly skills exist for all 3 stacks;
tester and coder skills exist for Java only.

### P0-3. Engine symbol classification is Java-vocabulary (fatal misfires)
`tdd_engine._resolvable_types` / `_unresolvable_missing` (`tdd_engine.py:52-101`):
- declarations scanned with `\b(?:class|interface|enum|record)\s+[A-Z]` — invisible
  to Python `def`/snake_case, TS `type`/`const`/`function`, Go types;
- the JDK subtraction (`java|javax|jakarta`, `JAVA_LANG_NAMES`, `JDK_TYPES`) has no
  Python-builtins / TS-globals / Go-predeclared equivalent.
Result: legitimate stdlib names read as "scheduling holes" ⇒ `FatalPipeline` aborts
a healthy non-Java run. Also `tdd_engine.py:613` attributes via
`name.removesuffix(".java")` — `.py`/`.ts` basenames won't match their owner,
so blame lands on the wrong unit.

### P0-4. The architect could not even LOAD the non-Java tech-stack skill (found + fixed 2026-11-12)
`agent-architect.md` carried `skill: "*": deny` with allow-entries for
`java-springboot3` + `java-reactive-patterns` ONLY - while its own role text promised
"the matching `tech-stack/*`". A Python/TS seed would have failed at strategy Phase 1
on a permission denial, before any of P0-1..P0-3 could even surface. Fixed during the
observability pass: `python-fastapi` and `typescript-nestjs` added to the allow-list (§10).

## 4. Soft couplings (correct results, degraded or wrong-default behavior)

1. `test_gate.command_from_test_path` / `_synthesized_command` / `_suite_command` /
   `_compile_probe_command` / `_selector_of`: shapes hardcoded for
   maven/jest/go/pytest only. Unknown degrades to per-unit scoped run (slower,
   correct). **Exception**: `_synthesized_command` (line 581) defaults to a *pytest*
   command for any unmatched project — a bogus guess on Rust/unknown stacks.
2. `test_gate.repair_test_imports` (Java-only) and `external_type_index` (JVM-only)
   correctly guard on `src/main/java` / `pom.xml` ⇒ no-op elsewhere (graceful), but
   non-Java stacks get no deterministic import repair.
3. `ensure_wrapper_executables` chmods only `mvnw`/`gradlew`.
4. `prompts.py` prose coupling: `_unit_brief` (184-192) parses
   `package x.y;`/`import … ;` grammar and counts `src/main/**.java` (neutral
   fallback exists); `_coder_contract` vocabulary (`kind record/exception`,
   `extends/implements`, `annotations`) is the Java weaver's schema — honest only
   while the Java weaver is the sole executor; `FEEDBACK_TEMPLATE_CODER` quotes
   javac phrasing (fields it reads are normalized, so it travels).
5. `closure.py` Java vocabulary in `_kind_hint`, `TYPE_POSITIONS`, JUnit-annotation
   blocklist; `_build_task` defaults `layout` to `"java"` when absent.
6. `ARCHITECT_TASKS_PROMPT`'s `ast_hints` vocabulary (`implements`) is Java-leaning;
   the prompt already says "as your language spells it".
7. `tech-stack-architect/` has only `java-reactive-patterns`.

## 5. Per-stack support matrix

| Piece | Java | Python (FastAPI) | TypeScript (NestJS) |
|---|---|---|---|
| Scaffold (stage 0) skill + MCP | ✅ | ✅ | ✅ |
| tech-stack skill | ✅ | ✅ | ✅ |
| tech-stack-architect skill | ✅ | ❌ | ❌ |
| tester-framework skill | ✅ `java-junit5` | ❌ | ❌ |
| coder-framework skill | ✅ ×2 | ❌ | ❌ |
| AST extractor builder (real) | ✅ JAR | stub | stub |
| Code-weaver executor (real) | ✅ JAR | stub | stub |
| run-test-tool patterns | ✅ | ✅ | ✅ |
| closure gap strategy | ✅ | ✅ | ✅ |
| assembly STACKS row + probe + skill | ✅ | ✅ | ✅ |
| verification table row | ✅ | ✅ | ✅ |
| plan-validity emit validator (stack-neutral data) | ✅ (§7.3) | ✅ | ✅ |
| architect skill permission loads the stack | ✅ | ✅ (fixed §10) | ✅ (fixed §10) |
| observability + export design duty (agnostic rule + concrete mechanisms) | ✅ (§11) | ✅ (§11) | ✅ (§11) |
| observability TEST-surface section in the tester skill | ✅ `java-junit5` | ⏳ lands with tranche 1 | ⏳ lands with tranche 1 |
| java version pin (desc-named wins; default 21) | ✅ (§9) | n/a | n/a |

## 6. Fix plan (execution order)

**Tranche 1 — skills (P0-2):** author the missing tester/coder framework skills,
keeping the *generic* skills generic (a generic skill that mixes in Java grammar gets
split: generic rules stay in `<lang>-standard-best-practices`-style skills, framework
grammar goes to `<lang>-<framework>`). Add:
`tester-framework/python-pytest`, `tester-framework/typescript-jest`,
`coder-framework/python-standard-best-practices`, `coder-framework/python-fastapi`,
`coder-framework/typescript-standard-best-practices`, `coder-framework/typescript-nestjs`.

**Tranche 2 — engine data tables (P0-3 + soft #1, #3):** introduce a single
language-profile table (declaration regex, stdlib blocklist, source suffixes,
test-command shapes, wrappers) consumed by `tdd_engine` and `test_gate` —
replace the scattered Java-only constants; suffix-agnostic basename attribution.

**Tranche 3 — executors (P0-1):** implement real weaver builders
(`python_weaver` via stdlib `ast` text-splice writer, `typescript_weaver` via a
text-splice writer honoring the payload schema), mirroring `_text_write_exec.py`'s
contract (argv + `{"status":…}` on stdout) — the dispatcher already accepts any
non-JVM executor without touching the orchestrator.

**Tranche 4 — remaining prose couplings** (§4.4) after 1-3 land.

## 7. Cross-reference: FINAL-EVALUATION-seed002.md (executed 2026-11-12)

This audit was executed **starting from the §6 next-session checklist** of
`FINAL-EVALUATION-seed002.md`. Status of every checklist item after this fix pass:

| §6 item | Fix | Where | Closes |
|---|---|---|---|
| 1. Plan-validity rules (a)-(d) in the decomposition skill | "Plan validity (emit-refused)" section, stack-neutral wording; `semantics` added to the methods entry shape | `architect-practices/task-decomposition-dag/SKILL.md` (one edit; `.github/skills` is a symlink) | D1, D2, D3, L1-L4 (plan stage) |
| 2. Architect profile restates (a)-(d) as emission duties | Duties §4 extended identically in BOTH copies | `.opencode/agents/agent-architect.md`, `.github/agents/agent-architect.agent.md`; `prompts.py` ARCHITECT_TASKS_PROMPT (invariants + ast_hints shape) | same |
| 3. Emit-time validator | `tasks.plan_consistency()` (unowned file artifacts, config-unit rule, request-encoding pair rule) wired into `task_queue.emit_tasks`; `validate(planning=True)` refuses null-rejecting intents without `semantics`; `validate_ast_hints` accepts the optional note | `orchestrators/tasks.py`, `orchestrators/task_queue.py` | D1/D2/D3 die at EMIT with named reasons, zero coder sessions |
| 4. Database-architect handoff rule | Runtime-namespace + consuming-unit + locations-align rule in the GENERIC skills (generic wording, no vendors) AND "in the same way" per stack in `tech-stack/java-springboot3` (spring.flyway.locations in application.yml), `python-fastapi` (alembic.ini/settings), `typescript-nestjs` (DataSource/ConfigModule); also in DATABASE_PROMPT | 2 architect skills + 3 tech-stack skills + `prompts.py` | D3 step 3, L3 |
| 5. Assembly gate marker→ALIGNMENT | `_migration_alignment_problems()`: configured locations (row data `locations_keys`/`locations_props_globs`/`classpath_roots` - still one row per stack) must physically contain the db/migrations scripts; empty or absent folder = gate red with the actionable line. Smoke-verified: D3 repro red, classpath/filesystem aligned green | `orchestrators/assembly.py` | D3 step 4-5, L3 |
| 6. Tester taste rule (persistence slice; boot-wide reserved) | Generic half in agent-tester profile (BOTH copies: "the persistence-slice test the stack skill names"), concrete half in `tester-framework/java-junit5` (@DataJpaTest/@DataR2dbcTest; @SpringBootTest forbidden for unit gates). `semantics` notes made contract clauses for tester AND coder (coder profiles, both copies) | profiles + stack skill | L5, D3 blast radius; D1 enforcement chain |
| 7. Gauntlet section G fixtures | G11-G20: Flux-vs-array REJECT, both aligned pairs ACCEPT, config-less plan REJECT + with-config-unit ACCEPT, unowned-file REJECT, null-reject-without-semantics REJECT + with-semantics ACCEPT, methods shape still enforced | `gauntlet/test_engine_decisions.py` | regression pins for all of the above |

**Definition of done (eval §6):** gauntlet is GREEN (74/74 engine + 41/41 skill-scripts);
the D1/D2/D3 shapes now die at emit with named reasons. The board must be wiped and the
seed re-run (§19 protocol) to confirm a fresh drain before closing the evaluation.

## 8. Remaining from the multi-stack audit (not in the seed-002 checklist)

1. Tranche 1 (P0-2): author `tester-framework/python-pytest` + `typescript-jest` and
   `coder-framework/python-{standard-best-practices,fastapi}` + `typescript-{standard-best-practices,nestjs}`
   - mirror the java skills' structure; keep the generic rules generic. The new tester
   skills MUST each carry the observability capture section that `java-junit5` gained
   (§11): `caplog` record fields / jest structured spies as the assertable surface, never
   formatted-string assertions.
2. Tranche 2 (P0-3): per-stack language profiles for `tdd_engine` declaration scan +
   stdlib blocklists (today JAVA_LANG_NAMES-only ⇒ false "scheduling holes" abort
   non-Java runs) and suffix-agnostic blame attribution (`tdd_engine.py:613`).
3. Tranche 3 (P0-1): real weaver executors for Python/TS (the dispatcher already
   accepts any argv+JSON executor per the `_text_write_exec.py`/yaml precedent).
4. §4 soft couplings: `_synthesized_command`'s pytest default, wrapper chmod list,
   `_unit_brief` grammar branch.
5. Operator: rebuild + push `SPRINGBOOT_MCP_IMAGE` from the updated MCP source (§9) -
   the `javaVersion` pin is inert until the image carries the new parameter.
6. Validation of the closed holes: a fresh non-Java seed smoke once tranche 1 lands
   (P0-4 was permission-only; its fix has not yet been proven by a full python/TS drain).

## 9. Java version drift — seed-002 pom pinned 17 while the seed named 21 (fixed 2026-11-12)

Chain of causes (all verified in the last run's records):
1. `seed/002_description.md:5` names "Java 21 / Spring Boot 3 WebFlux", yet the strategy
   (`execution-strategy-telemetry-ingestion-processing.json`) recorded
   `language: "Java 17+"` claiming "the business description names no explicit versions".
2. The floor came from `tech-stack/java-springboot3/SKILL.md` ("Java 17+"), which read as
   the stack's default; downstream coder/assembly skills restated "Java 17+".
3. The scaffold task passed "Java 17+" through, and `generateSpringBootProject` in the
   Spring Boot MCP server had NO `javaVersion` parameter at all - the Initializr request
   never sent one, so the pom always received the generator's own default: 17. The skill's
   "drift => regeneration with corrected params" was impossible to satisfy.

Fixes (rule: description-named version wins VERBATIM; otherwise the DEFAULT is Java 21):
- `tech-stack/java-springboot3`: "Java 21 default; a named version is the pin; '17+' is a
  Boot-3 minimum, never an emitted value; one exact number in strategy, intent and manifest".
- `coder-framework/java-springboot`, `assembly-framework/java-springboot`: restated the same
  way (pin-honoring, no more "17+").
- `orchestrators/prompts.py` ARCHITECT_STRATEGY_PROMPT (generic, all stacks): verbatim rule +
  "no named version => stack-skill default (Java: 21)" + "floor is never a pin, generator
  default is never a decision"; the scaffold intent template now carries "language version
  <exact number>".
- `.opencode/agents/agent-architect.md` + `.github` mirror: version duty restated.
- `mcp_server/.../InitializrMcpTool.java`: new optional `javaVersion` tool parameter, default
  21 (`mcp.initializr.default-java-version`), validated, and actually sent to start.spring.io.
- `mcp-server-springboot` skill: pass the pin EXACTLY; pom `<java.version>` must EQUAL the
  pin; stale image without the parameter => report `STALE_MCP_IMAGE`, never an unpinned scaffold.

Operator action: rebuild and push `SPRINGBOOT_MCP_IMAGE`
(`caupolicanquerales/springboot_mcp_server:latest`) from the updated source - until then the
container stage stops with STALE_MCP_IMAGE instead of silently producing 17.

## 10. P0-4 closure — architect skill permissions made non-Java planning impossible (fixed 2026-11-12)

While wiring the observability duty (§11) into the architect profile, its `skill:`
permission block was found to allow only the Java tech-stack skills while the role text
promised "the matching `tech-stack/*`" - on a FastAPI or NestJS seed, Phase 1 would have
died on a permission refusal before stage 0 even mattered. Fixed:
- `.opencode/agents/agent-architect.md`: `python-fastapi: allow`, `typescript-nestjs: allow`
  added (the database-architect profile already allowed all three - the gap was architect-only).
- No engine change was needed; this was pure profile coupling to the first-supported stack.

## 11. Observability as a runtime contract — new architect responsibility (added 2026-11-12)

The pipeline previously treated logging as agent discretion: nobody PLANNED audit trails,
step logs, correlation or metrics, so nothing tested them (and D3-style "prose duties"
could have smuggled them in). Two follow-up turns made observability a designed,
decomposed, TESTED contract - agnostic rule at the top, concrete mechanisms per stack,
same rule same way across all three.

**Generic layer** (no vendors, no frameworks):
- `architect-practices/task-decomposition-dag/SKILL.md`: new section "Observability is a
  runtime contract (design it before decomposing)": every data/process-owning context's
  strategy carries an `observability` object - step logs + correlation key, audit-trail
  records (actor, action, outcome, timestamp), named metrics with bounded tags - AND an
  `export` entry: the machine-readable schema + sink through which EXTERNAL tools
  (Elasticsearch-class log management, Prometheus-class metrics) consume the events.
  Decomposition rules: audit = tabled port + infrastructure adapter + migration (database
  step's) when queryable; correlation = one middleware unit; meters declared in the
  consuming unit's `ast_hints`; levels/formats/sampling/sink properties = CONFIG-unit
  literals (emit validator rule (b) already forces the unit to exist); business units
  never scatter raw logger calls for contractual facts.
  Division of labor: **the app writes the contract, the platform ships it** - default sink
  is a local append-only structured destination; a direct push endpoint only when the
  description names one, and then the boot gate must still pass with the tool absent
  (same offline rule as external databases).
- `orchestrators/prompts.py`: ARCHITECT_STRATEGY_PROMPT asks for the `observability`
  object incl. `export`; ARCHITECT_TASKS_PROMPT got the matching invariant bullet.
- `.opencode/agents/agent-architect.md` + `.github` mirror: OBSERVABILITY DESIGN DUTY
  restated (identically in both copies).

**Concrete layer - the same rule, each stack's own idiom:**
- `tech-stack/java-springboot3`: SLF4J-only + one logger per planned step; structured
  output as config decision; **Elasticsearch-consumable export**: Boot >= 3.4 native
  `logging.file.name` + `logging.structured.format.file: ecs` (ECS JSON lines, ingested
  verbatim by Elastic Agent/Filebeat) + rolling-policy keys; below 3.4 the
  `logback-spring.xml` + `logstash-logback-encoder` equivalent; direct-to-cluster
  appenders only when named, off under the test profile; correlation via `WebFilter` +
  reactor context (never trusting MDC across reactive threads); audit port/adapter/
  append-only table via expand-only Flyway; Micrometer through `actuator`, bounded tags
  only; test surfaces: `ListAppender`, `SimpleMeterRegistry`, recording port fakes.
- `tech-stack/python-fastapi`: dictConfig/structlog rotating **JSON-lines file** sink
  (path/rollover as settings-object keys) tailed by Filebeat/Fluent-Bit/Vector;
  contextvars correlation; Protocol audit port + adapter + Alembic; `caplog` FIELD
  assertions; no direct elasticsearch handler unless named.
- `tech-stack/typescript-nestjs`: pino file-transport **NDJSON** sink via ConfigService
  keys; AsyncLocalStorage requestId also carried explicitly in audit records; audit port
  token + TypeORM append-only entity + migration; jest spies/recording providers;
  direct transports only when named, off under the boot test.

**Tester/coder chain (the design must be provable):**
- `agent-tester.md` + mirror: observability units are ordinary units - assert the CAPTURED
  structured surface (record fields, meter values, correlation keys), never formatted
  strings; an untabled meter name or audit field is a plan hole to report.
- `tester-framework/java-junit5`: new "# Observability units" section: `ListAppender`
  field assertions, `registry.get("tabled.meter.name")...count()`, ArgumentCaptor on the
  audit port with every tabled field asserted, forbidden text-equality assertions.
- `coder-framework/java-springboot`: implement ONLY what the task tables; a logger field
  appears only where an intent names the step.

**Scope note:** the Python/TS tester skills from Tranche 1 must ship with their own
"# Observability units" sections mirroring `java-junit5` (§8.1); until then the generic
agent-tester rule is the binding contract for those stacks. The emit validator needs no
new rule: sink keys are config-unit literals, so existing rule (b) already refuses plans
that assign the export without scheduling its owner.

Verification for this section: `prompts.py` asserts + gauntlet remained green after every
edit (74/74 engine + 41/41 skill-scripts).
