# Blackboard process evaluation — seed/002_description.md
Run date: 2026-11-09 · Backend: GitHub Copilot CLI 1.0.106 · Model: claude-sonnet-5.5
STATUS: orchestrator STOPPED by operator request at end of run-10. Queue 0, complete 61,
quarantined 23. Final numbers in §7-§8.

## 1. Token economics observed
- Baseline per `copilot -p` call: ~30k input tokens (dominated by tool-schema + system prompt
  cache writes), 1 premium request. Cost driver = number of TURNS per session, which the
  engine caps by per-agent tool-call budgets (6–12) with hard-kill at 2×+4.
- Whole day-run (10 restarts): **159 agent sessions = 159 premium requests**. Calls/session:
  min 2, avg 5.3, max 15 (batch coder, within its scaled budget). 12 over-budget WARNINGS,
  **0 hard-kills, 0 timeouts, 0 runaway sessions** — the budget architecture held all day.
- Deterministic engine-side work (mvn gates, AST dispatch, red-phase reruns, repair passes,
  the YAML weave) costs zero agent tokens — the design is sound.
- Cost attribution: initial full pipeline (discovery→plan) ≈ 12 sessions; TDD waves ≈ 147.
  Each restart/resume spent ZERO re-billing of completed work (skip-agent/red-record reuse),
  so the crash/repair cycles did not double-pay.

## 2. Defects FIXED in the process (scripts only, benchmark-legitimate)
1. `tdd_engine._unresolvable_missing` — scheduling-hole detector saw only file stems; nested
   types (`IngestResult` in `IngestPacketUseCase.java`) caused false FATAL aborts of the drain.
2. `closure.gaps` — same stem-blindness; `--emit` would queue bogus producers for names that
   exist as nested declarations (and did: T2-026 duplicated the architect's nested
   `WindowQuery` → later withdrawn).
3. `test_gate.JAVA_LANG_NAMES` — missing `NoSuchMethodException` (java.lang, never importable);
   closure reported it as a gap.
4. `test_gate.repair_test_imports` — only covered test tree and only ADDED imports. Now also:
   MAIN tree; reroutes `import p.Inner;` → `import p.Outer.Inner;` (the only legal form for
   nested types — the most common tester/coder javac failure in this run); reroutes
   wrong-package imports of uniquely-owned types; idempotent.
5. `test_gate._failure_detail` — retry log truncated to 3 missing + 3 blame lines with no
   ordering; coders received peer-unit lines first and re-emitted unchanged payloads
   (observed verbatim in T2-018). Now: 6 missing + up to 10 blame lines, and lines naming the
   retried unit's own file/exported type are ranked FIRST.
6. `prompts.FEEDBACK_TEMPLATE_CODER` — coder was never told that a test blaming a missing
   constructor/method on ITS OWN exported type is its own work even when the test belongs to
   another unit. Rule added (delegating overloads/accessors; never re-emit identical payload).
7. `task_queue.send_to_error` — crashed the watch loop (FileNotFoundError): a task mid-gate can
   be swept to error/ by `quarantine_dependents` while its own `finalize` failure also
   quarantines it; the loser of the race unlinked a file that no longer exists. Now idempotent
   (`missing_ok=True`). Observed killing run-7 on T2-027/T4-001.
8. `code-weaver-dispatcher/builders/yaml_weaver.py` + `_text_write_exec.py` — NEW builder:
   configuration units (`application.yml`) were unschedulable ("no builder matched language
   'yaml'"), which burned 3+3 coder sessions on T2-013 and cascade-quarantined its dependents
   (T2-015, T2-018) twice. The weaver for a config payload is now a validated full-text write
   (tab check + YAML parse when PyYAML present); zero agent sessions. Verified weaving the
   recorded T2-013 payload with status ok.
9. `tester-framework/run-test-tool.py` — `_follow_message` returned only the FIRST line after a
   Surefire failure header, which for AssertJ is the exception class name. Retry feedback for
   assertion-level failures was therefore unusable ("AssertionFailedError:") and coders
   exhausted attempts blind. Now collects the expected/actual block (capped, stops at stack
   frames). A/B verified on a real failure sample: old message = class name; new = the actual
   diff (`status=OK` vs `status=VALID`). Note: the skill's own test-suite has 6 pre-existing
   errors (identical before/after this change).
10. `test_gate` gate-memo invalidation — `_fingerprint` got an explicit `memo_version` key;
    without it, verdicts cached BEFORE the §9 parser upgrade kept being replayed ("cached
    verdict") into retry feedback forever, silently defeating the upgrade. One-time forced
    rebuild per unit on version bump (mvn only, zero tokens).
11. `test_gate._failure_detail` also now prefers failures with a NAMED test over anonymous
    exception-line entries (3 shown instead of 2).

## 3. Process-level weaknesses — OBSERVED, not fixed (judged as-is)
W1. **Code-weaver merge semantics create frankenstein files.** Successive payloads for a unit
    merge members without replacing the file: `WindowBufferService.java` ended with two
    constructors, a lost `implements` clause, unbound pattern variables (`validated`/`backfilled`),
    and a stale `bufferTimeout(int,int)` call. Weave reported `status=ok` every time.
W2. **Skip-agent + stale payload**: a unit with a recorded payload goes straight to weave+gate;
    after ANY other unit's file changes, the memo re-runs the build (correct) but the payload is
    never reconsidered — dead payloads can only be superseded by a fresh coder attempt after a
    gate failure, so W1 artifacts persist across attempts.
W3. **Watch-mode defer spin**: deferred tasks are re-attempted every 5s poll; observed 4374
    `[wait]` lines in ~10 minutes (CPU churn, zero tokens). A backoff/registration of "waiting
    until tree changes" would be cleaner.
W4. **`--emit` from closure inherits the architect's package placement from test imports**
    rather than from the plan; when a tester assumed a wrong package it emitted a duplicate
    producer (this caused the WindowQuery incident; root detector fix landed, emit-side
    placement heuristic is still naive).
W5. Batch coder session (budget 4+3·units) showed 15 calls vs hard-kill 12+? — check batch
    arithmetic: `max(budget+4, budget*2)`; for 4 units budget=16, hard=32 fine; single budget 6
    → hard 12: a 15-call session observed was a batch (legal). No change.

## 4. Agent-capability findings — NOT fixable in scripts (this is the evaluation signal)
A1. **Architect omissions (missing tasks).** For PulseStream the DAG never produced:
    `IngestResponse` (referenced by DeviceAclMapperTest), a top-level/nested decision for
    `WindowQuery` (interface-nested record vs consumers in other packages — Java requires
    outer-qualified imports the testers didn't know), and left ports' collaborator surfaces
    implicit. Sanctioned recovery (`closure.py --emit`) worked but is a post-hoc patch of the plan.
A2. **Testers invent cross-unit APIs.** T1-014 assumed package `domain.policy` (does not exist);
    T1-016/T1-023 invented different constructor shapes for `TelemetrySample`
    (`(String,String,Instant,double,int)` vs canonical 7-arg vs `(double,Instant,long)` orderings);
    T1-023 stubbed the use-case port returning the REST DTO (layer inversion that contradicts
    T1-016's frozen expectations — an irreconcilable test-vs-test contract conflict; the engine
    has NO arbiter for this class of defect; resolution requires either a test edit (forbidden to
    agents) or a plan-level rule (ports speak domain types)).
A3. **Coders under-deliver with degraded logs** (pre-fix evidence): 3×3 attempts burned on
    "payload unchanged" while the actionable line sat below truncation; and pattern-variable
    pseudocode shipped as valid payload. Expect a materially better convergence rate with §2.5–2.6;
    measure attempts-to-green per unit on the next clean run to confirm.
A4. **Budget vs reality for the container stage**: T0 scaffold used 7 calls/10 budget — fine;
    assembly not yet reached this run.

## 5. Operator-contamination disclosure (edits made BEFORE the "process only" directive)
The generated service tree is NOT fully agent-authored. The operator hand-fixed, to break a
livelock and to keep the day's budget: `WindowBufferService` (rewrite), `implements` clauses in
`IngestPacketService`/`BackpressureEventBroadcaster`/`R2dbcTelemetrySampleRepository`, additive
overloads/accessors in `TelemetrySample`, `IngressPacket(+RawSample)`, `TelemetryEvent`,
`IngestPacketUseCase`, `IngressPacketRequest`, `TelemetrySampleEntity.fromDomain`→static, port
default methods in `QueryTelemetryWindowUseCase`, `TelemetryWindowController` call routing,
ONE frozen test edited (`TelemetryWindowControllerTest`, the A2 conflict above), red-phase
`T1-014` regenerated, T2/T3-026 emitted+withdrawn, T2/T3-027 emitted.
**Consequence:** units {T2-003/004/005/008/009/013/015/016/017/019/020/021/022/023/027} results
this run are partly operator-assisted; do not score them as autonomous.

## 6. Recommendation
To get a clean signal from the tuned process: `--force` rerun of seed 002 into a fresh output
dir (new projects/ + fresh blackboard), then measure per stage: sessions, calls/session,
attempts-to-green, quarantines, hard-kills. Expect §4 defects to reappear as quarantines instead
of silent operator patches — that is the signal, not a regression. If A2 (test-vs-test conflict)
reappears, the process needs a PLAN-STAGE invariant (ports return domain types; DTO shapes pinned
by the producer unit, consumers must import through outer type) added to
`domain-driven-architecture`/`task-decomposition-dag` skills and the tester agent profile.

## 7. Final run result (10 runs, all fixes active)
Terminal state: **61 / 84 units complete** (73%), queue drained, 23 quarantined,
then process stopped by operator.
- Stage 0 container: 5/5 green. Stage 1 tests: 25/25 green.
- Stage 2 coders: 14/25 green (incl. T2-013/027 via the new YAML builder / emit path).
- Stage 3 evaluators: 11/25 green (each tracks its T2).
- Stage 4 assembly: 0/1 — T4-001 was attempted and gated RED while its domain had
  quarantined units (correct engine behavior: assembly cannot claim boot over broken wiring).
Full-suite `test-compile` remained green from the §5 tree onward; every later failure was
assertion-level or weave-parse-level, never scheduling again.

## 8. Analysis of the 23 quarantined units
Of the 11 quarantined T2 units, **7 were cascade victims** ("dependsOn T2-XXX not
resolvable"), i.e. they were NEVER given an attempt of their own: T2-015, T2-016, T2-018,
T2-022, T2-023, T2-024, T2-025 (+ their 7 T3 evaluators). The four REAL failures, each
after 3 fresh attempts WITH the upgraded feedback (full assertion diffs):
- **T2-009 `QueryTelemetryWindowUseCase`** — 11 tests, 1 assertion failing per attempt:
  reactive-window semantics in the interface default contract. The coder iterated but never
  converged → agent-capability (A3): subtle Reactor timing assertions exceed the current
  coder's convergence under a 6-call budget.
- **T2-010 `TelemetrySampleRepository`** — killed by `code-weaver failed: Payload member
  does not parse ... expected one of ";" "@" ...` — the Java weaver's grammar rejects the
  payload format for an interface member with `default`+generics. This is a TOOLING gap in
  the AST/weaver JAR (W6), not agent judgment: feedback repeated verbatim, coder reformatted
  twice, still unparseable. → escalate to the weaver-tool owner.
- **T2-021 `DeviceAclMapper`** — assertion with `errors=1` (Mockito strict-stubbing style
  error) on `status=OK` vs `status=VALID` mapping: the mapper test and the (operator-aligned)
  controller test disagree on the DTO's status vocabulary — residue of the A2 test-vs-test
  conflict; the coder cannot edit either test.
- **T2-027 `IngestResponse`** — closure-emitted unit whose contract came from a single test's
  usage; its assertion error stayed opaque across 3 attempts (same Mockito error class).
Process lesson (W6, new): a non-parsing weaver payload should bounce BACK to the coder with
the javaparser message as actionable feedback BEFORE burning a full attempt; today the weave
failure consumes the attempt identically to a test failure.
Recommendation for next seed runs (unchanged + new):
1. Plan-stage invariant in `task-decomposition-dag`/assembly skill: ports speak DOMAIN
   types; REST DTOs live in interface layer only (prevents A2 conflicts like status=OK/VALID).
2. Weaver tool: actionable error channel for payload-parse failures (W6).
3. Consider 2 extra attempts for units whose failures are 100% peer-attributed before their
   first own-attempt (cascade victims): today they are quarantined without ever running.

## 9. Stack-agnosticism audit of `orchestrators/` (2026-11-09, follow-up)
Audited every Python file for language/framework coupling, since the pipeline is meant to
run Java/Spring, NestJS/TypeScript, FastAPI/Python (and the weavers also register Go).

**Already agnostic (verified, unchanged):**
- `dispatchers.py` — `BUILD_MARKERS` for 8 stacks; package-internal detection is pure
  path-segment logic ("no grammar, no extension assumptions"); run-test-tool owns syntax.
- `test_gate.py` core — `FILE_REFERENCE_RE` covers javac/tsc/go/pytest/kotlinc shapes;
  `SOURCE_SUFFIXES` multi-language; `_synthesized_command` falls back across
  pom.xml → package.json → go.mod → pytest.
- `verification.py` — typecheck/build commands per stack: maven, gradle, flutter, angular,
  node, go, cargo, python. `assembly.py` — three smoke-test detectors + skill map + a
  graceful "assembly not scheduled" fallback.
- `tasks.py`, `task_queue.py`, `workspace.py`, `ddd.py`, `settings.py`, `pipeline.py`,
  both backends — no stack assumptions found.

**Coupling FIXED in this pass (scripts):**
1. `closure.py` — the engine's own recovery recommendation was **Java-only**: the scanner
   parsed `import p.X;` and `_build_task` hardcoded `src/main/java/<pkg>/<Name>.java`, so on a
   Python/Nest project the fatal hint "close it with closure.py --emit" recommended a silent
   no-op. Now: `gaps()` dispatches by stack —
   - **python**: stdlib-AST scanner (`from pkg.mod import Thing`, `import pkg.mod`), only for
     modules rooting in the project's own top-level packages; third-party ignored; the emitted
     task extends the existing module file or creates a new module anchored at the nearest
     existing package (e.g. `src/app/services/pricing.py`).
   - **typescript**: named imports from RELATIVE specifiers only (`@nestjs/*` ignored); missing
     file → new `src/.../<name>.ts`; missing named export → producer task extends the resolved
     file; paths normalized.
   - **unknown stacks (go/rust/flutter…)**: return no gaps — closure never fabricates work it
     cannot ground; the DAG still holds those producers accountable via `_pending_symbols_of`.
   Gap dicts carry a `layout` key; `_build_task` derives path + layer from real path segments
   for every layout. Java behaviour verified unchanged against the live seed-002 project.
2. `prompts.py` `_unit_brief` — the coder's "main_sources_present" fact counted only
   `rglob("*.java")` (always 0 on other stacks, misleading the coder). Now falls back to the
   language-neutral `source_files` scan excluding test dirs.

**Remaining language-specific parts (accepted, documented):**
- `test_gate.repair_test_imports` is a Java strategy (package/import grammar, nested-type
  reroute); on other layouts it no-ops safely (`src/main/java` absent). Python/TS import
  repair is feasible but needs per-stack resolution rules — future work, not a correctness
  hazard (worst case: the stack's own compiler reports it and the loop reacts).
- `_unresolvable_missing` subtracts `JAVA_LANG_NAMES`/`JDK_TYPES` — purely subtractive,
  harmless elsewhere; its "type-shaped token" gate means lowercase module names (python) never
  trigger the loud abort — they flow through bounded retries instead (acceptable: python
  toolchains fail at import time, per test, not per suite).
- `closure._kind_hint` vocabulary is Java-leaning ("record", "port interface") — affects only
  the intent's prose, not scheduling.

**Verification log:** Java live-project gaps unchanged (`[]`); python/TS synthetic fixtures
produce correct producer tasks with sane paths; go fixture produces none. All modules
`py_compile` clean. Pipeline intentionally left stopped after this audit.

## 10. Script fixes derived from both reports (follow-up pass)
Every P0/P1 in the PROJECT report traced to a process gap; the ones owned by SCRIPTS are now
fixed (agent-capability items stay in §4 as evaluation signal):

1. W1 - **weave accumulation** (`dispatchers._reset_stale_weave`): the first weave of a unit
   snapshots the target file to `blackboard/weave-baseline/<task>/…`; every later re-weave
   (payload newer than result) restores that baseline first, so retry payloads splice onto the
   unit's true pre-state instead of merging into the previous weave. Kills duplicate
   constructors, dropped class headers and vestigial same-named void methods (P1-11 family).
   Verified: simulated merge artifact removed on second weave; cache-hit weaves untouched.
2. T2-010 class - **payload rejections no longer burn TDD attempts**
   (`dispatchers` marks tool-shaped weave failures with `weave-reject:`,
   `tdd_engine.execute_with_tdd` bounces them back to the coder for free, capped by
   `settings.MAX_WEAVE_REJECT_BOUNCES = 2`). Verified: bounce-converge (2 sessions,
   attempts untouched) and cap-then-quarantine (3 attempts + 2 bounces max).
3. P0-4 / recommendation 1 (mark variant) - `quarantine_dependents` appends
   `[WOVEN-UNVERIFIED: … suspect this file]` to the error reason whenever a cascade victim
   already has a payload spliced into the tree (the exact T2-018 deadlock carrier). The next
   operator sees the hazard in `blackboard/error/` instead of bisecting a hung suite.
4. W3 - **watch backoff** (`pipeline.run`): passes that produce nothing grow the poll interval
   geometrically to 60 s; `[wait]` lines dedupe per task+reason for 5 minutes
   (`tdd_engine._log_wait`). Same 10-minute window that logged 4374 waits now logs ~1 per unit.
5. P0-2 - **assembly gate fails orphaned schema** (`assembly._schema_wiring_problems`):
   non-empty `db/migrations/*.sql` with no stack-appropriate runner (flyway/liquibase/
   spring.sql.init; alembic; ORM migrations tooling) is a structural gate failure with an
   actionable line - the assembly agent (the only stage allowed to touch wiring) must wire it.
6. P0-3 - **assembly gate fails ambiguous boot entries** (`assembly._detect_java`): >1
   `@SpringBootApplication` or an entry without `public static void main` is reported the same
   way. Live check on this project's tree flags both real instances of these defects.
7. A2 upstream - **plan-stage invariants added to the architect prompts** (`prompts.py`):
   ports speak domain types only (never interface DTOs), every shared collaborator surface has
   exactly one producing task, operational values bind through the config unit; the T0 scaffold
   intent must now require a single composition root, test-runner timeout guardrails and a
   schema migration runner when the plan owns SQL.
8. closure dispatch detection no longer misses nested Python packages (rglob, not glob).
9. **`assembly.py` is now registry-driven (stack-agnostic engine):** a `STACKS` data table
   carries each stack's skill path, composition-root probe (globs + marker + launch
   requirement + excludes) and schema-runner markers/globs/hint. Composition-root uniqueness
   and orphaned-migrations checks are evaluated GENERICALLY from the row for every stack -
   no structural rule branches on a stack name anymore. Detectors are pure probes (smoke test
   + command only). Adding a framework = one STACKS row + one probe + one skill. An unprobed
   ecosystem is distinguished from a scaffold defect in the log ("known ecosystem (pom.xml)
   but no smoke-test contract" vs "stack not registered"), and a probe returning an
   unregistered stack reports a problem instead of raising KeyError. Verified: same two
   structural problems on the live Java tree; synthetic Nest fires duplicate-bootstrap +
   orphaned-migrations; synthetic FastAPI passes when alembic is wired, fails on duplicate
   `FastAPI(` mains; golang probe degrades with an actionable message.

All orchestrators compile; Java closure behaviour re-verified unchanged (`gaps == []`);
Python/TS agnosticism fixtures still produce 2 correct producer tasks each.

## 11. Clean-run validation (rerun of seed 002 after the user emptied the blackboard)
Run started 2026-11-09 ~19:00 local, fully autonomous (operator edits forbidden this run).

### 11.1 Incident: environment version drift at stage 0 (caught, stopped, fixed IN THE PROCESS)
- Discovery/mapping/strategy/database ran normally (6 sessions, avg 2-7 calls).
- T0-001 container FAILED once and stopped the pipeline by design, exposing two process bugs:
  B1: start.spring.io no longer serves Spring Boot 3.x (seed mandates it); the skill said
      "tell the user, ask for another version" = halt in headless mode.
      FIXED: `mcp-server-springboot/SKILL.md` now defines headless version-drift fallback
      (regenerate with default GA, keep all params, record deviation; never halt to ask).
  B2: the FIRST failure regenerated with h2 but ALSO pinned bootVersion=3.5.7 -> 400 -> stop:
      the old profile rule only listed `data-jpa/postgresql/flyway` (not `data-r2dbc`), and
      the h2/dependency guidance lived in the generic profile with Spring vocabulary.
      FIXED + generalized per the AGNOSTIC RULE (see 11.2): container profiles now state a
      NEUTRAL contract - "the skill defines the embeddable in-process substitute and the
      regenerate-once rule" - and each of the three mcp-server-alternatives skills now
      carries its own Scaffold Verification section with its stack's vocabulary
      (h2 for Spring; sqlite/in-process URL defaults for FastAPI and Nest).
- Cascade guard (P0 lesson from the previous run): `task_queue.ScaffoldUnresolved` aborts
  the drain with the scaffold's OWN error line the moment a queued task depends on a
  quarantined stage-0, instead of scattering 124 quarantine records. Verified live: the
  unit test fired with the real message; relaunch after the skill fix produced a green
  scaffold (pom.xml + mvnw + src + context test) on retry.

### 11.2 Rule adopted (user directive): updates to agents must be stack-agnostic
Agent PROFILES and orchestrator prompts carry rules and contracts only; every stack
vocabulary (artifact ids, tool names, engines) lives in ONE skill per stack. Applied to:
`agent-container` profiles (both copies), `mcp-server-{springboot,fastapi,nestjs}` skills,
and the architect T0 requirement in `prompts.py` (names removed, points to the stack skill).

### 11.3 Observations in flight (this clean run's own evaluation signal)
- Architect decomposition expanded (39 T1 units vs 25): the new invariants (one producer
  per shared surface) visibly worked; the extra units are collaborator pins, not noise.
- First testers STILL assume packages/factories ("TelemetrySample in intake.domain",
  `unvalidated(...)`) - A2 remains live. Watch: whether repair_test_imports + hole
  detection converge these, or they surface as bounded quarantines (the honest signal).
- Database architect budget overrun (14/10) -> raised to 14. Recheck after drain.
- Token rate (through stage-0 + first testers): sessions=1/session, calls avg ~4, no kills.

### 11.4 Incidents during the clean drain (each: stopped, fixed IN PROCESS, resumed)
I1 - T1-005 red close-out raised the foreign-package fatal: tester invented package
     `telemetry.ingestion.domain` for two types scheduled in `telemetry.intake.domain`.
     FIXED (tdd_engine._tester_close_out + drain scan): before aborting, the deterministic
     import repair now runs, the red record is re-derived (dispatchers.rerecord_red_phase,
     same run-test-tool|write-red-phase pipe the tester used), and only a gap SURVIVING the
     reroute aborts. Required repairing the reroute rule itself (test_gate): it previously
     refused packages not declared anywhere - exactly the invented-package case. Now a
     name with a UNIQUE home sharing >=3 package segments is rerouted regardless of the
     inventing package existing, and queued-but-unwoven producers count as homes (schedule
     overlay from task paths). Verified live: gap cleared, T1-005 finishes free via
     resume-skip. A2 behaviour itself stays a REPORT signal (testers still invent).
I2 - Pipeline closure gate flagged `NoSuchFieldException` and `AssertionError` as unclosed
     imports: the hand-grown java.lang blocklist was incomplete (third exception in three
     runs). FIXED (test_gate.JAVA_LANG_NAMES): full java.lang throwable inventory added,
     single source for closure + hole detector. gaps=0 after.
Budget notes: container 12/10 (regenerate-once flow is legitimately one call longer);
tester 9-10/8. Left as warnings: budgets never stop sessions (hard kill = 2x+4 is the only
cut, never fired); raising budgets would only loosen runaway protection.

### 11.5 Incident I3 - mvnw lost its exec bit (stopped, fixed IN PROCESS, resumed)
Mid-T2, 6 units began failing their gates with `status=not_run; EXEC_ERROR: [Errno 13]
Permission denied` - the scaffold's `mvnw` arrived from the docker mcp_workspace without +x.
Every chargeable signal pointed at the CODERS, and 3 charged attempts x 6 units (~18
sessions) plus 26 cascade quarantines burned before the pattern was caught. Fixed:
- `test_gate.ensure_wrapper_executables`: engine-side bit restore (mvnw/gradlew) invoked
  before every gate command and the assembly gate - tooling hygiene, bit only, never text.
- springboot skill: "verify mvnw is executable after moving the scaffold out of the
  mcp_workspace" (root-cause rule at the scaffold stage).
- `tdd_engine`: a `not_run` gate result now ABORTS the drain as an environment fault
  (FatalPipeline) instead of charging coder attempts; `green_test_result` no longer
  memoizes not_run verdicts; the 7 poisoned gate-cache memos were swept.
- `--retry` restored all 32 quarantines; the 6 affected units re-enter via skip-agent
  (payloads already on disk, zero new coder sessions for the fix itself).

### 11.6 Incident I4 - dependency types flagged as scheduling holes (fixed IN PROCESS)
Closure gate aborted on `InOrder` / `Qualifier`: mockito/Spring types used by tests with
fully-qualified names or a forgotten import. The closure's "qualified use" subtraction only
knew `java|javax|jakarta`, and the hand-list approach (I2) cannot cover the ecosystem.
Fixed with two general mechanisms:
- closure: ANY dotted chain now qualifies its segments (`(?<=[a-z0-9_$])\.` etc.); a used
  name whose simple name is provided by the DEPENDENCY CLASSPATH is never a producer gap.
- `test_gate.external_type_index`: builds a simple-name -> FQCN index ONCE per pom.xml by
  scanning the project's own resolved classpath (mvn dependency:build-classpath + zip
  listing of every jar; cached at blackboard/external-index.json, 15,388 types in this
  project). Non-JVM stacks return {} (their strategies are import-path based already).
- `repair_test_imports` now also ADDS unambiguous dependency imports (one candidate FQCN
  => `import org.mockito.InOrder;`); ambiguous simple names stay for the agents to resolve.
Verified: gaps=0, repair touched exactly the 1 file with the real missing import, second
pass idempotent. Also fixed: `repair_test_imports` was missing its `return repaired` in
this refactor (silent None -> the I1 closeout reroute check could never see repairs).

### 11.7 Wave-gate implementation (process change, agnostic) - and its first tuning
Proposals 1+2+3 from the bottleneck analysis implemented in process scripts:
- run-test-tool now emits `classes` ({identifier: passed|failed}) parsed per toolchain
  (surefire per-class lines, pytest PASSED/FAILED, jest PASS/FAIL, go ok/FAIL). Stack
  parsing stays in the tool; the engine consumes a neutral map (test_gate has no
  toolchain regexes).
- `test_gate.wave_gate_verdict`: one module-wide suite run adjudicates every unit's
  green gate via that classes map, cached per tree state; scoped per-unit run remains
  the fallback for unrecognized command shapes, ambiguous selectors and non-T2 stages.
- `_suite_command`/`_selector_of`: generalize the SAME four toolchain shapes
  `_synthesized_command` produces (mvn -Dtest= / go -run / npx jest <pat> / pytest <path>).
- Content-based fingerprints (sha1 of bytes): the first mtime variant STILL rebuilt per
  weave (even byte-identical bounce re-weaves) - measured 5 full-suite builds in 3
  minutes; after the fix a compile-broken tree costs [gate] wave compile probe
  (mvn -q test-compile | go vet | tsc --noEmit | pytest --collect-only) instead of a
  suite boot: two-unit verdict path measured at 9.9 s (probe + cache hit) vs ~4-6 min
  per unit before. Probe results cache as the shared compile_error verdict.
- gate-cache wave files pruned to the last 5; memo_version 3 (content fingerprint).

## 12. Big-O evaluation of the task selection/search loop (measured, board N=81 D=47)
Variables: N queued tasks, D done, S source files (~110), C source bytes (~150 KB),
E external-index entries (15,388 / 1.3 MB JSON), A attempts per pass (A≈N when the wave is
open), P passes/hour (watch backoff 5s→60s ⇒ 60–720).

### Selection/search core - NOT the bottleneck
| operation | complexity | measured |
|---|---|---|
| heap seed + pop/push (`ready`, `task_sort_key`) | O(N log N) per pass | <1 ms |
| `eligible` / dependency graph build | O(N + edges) | <1 ms |
| `read_queue` / `load_index` / `complete_task_ids` | O(N)/O(N+D)/O(D) JSON | 3.0 / 5.2 / 1.6 ms |
| `load_valid_tasks` (validate + dirty re-loops) | O(N(N+D)) worst, O(N+D) typical | 11.3 ms |
| `_pending_symbols_of` / `_queued_main_file_owners` | O(N) glob+parse per gate failure | 1.4 ms |
| `_sibling_payloads_pending` | O(N) per attempt ⇒ **O(N²) per pass** | 2.1 ms → 170 ms |

### The real cost: constant work repeated per attempt, not the search
Per deferred stage-2 attempt (no agent, no maven): measured ~310 ms:
| cost | why it repeats | measured |
|---|---|---|
| **weave dispatcher subprocess** | spawned per attempt even when `_cached_success` will short-circuit INSIDE it (the orchestrator pays python+imports startup ~143 ms to be told "no work") | **143 ms/attempt → 11.6 s/pass** |
| **`repair_test_imports`** | full main+test read + regex O(S·C), AND re-parses the 1.3 MB external-index JSON O(E), on EVERY gate call although the tree did not change since the previous unit's call | ~150 ms/attempt → 12 s/pass |
| **`_tree_fingerprint`** | hashed ~3x per attempt (memo read, wave lookup, memo write): O(S+C) each | 11.8 ms x3 |
| gate hot path total (repair+fingerprint+wave lookup) | | 164 ms |

Per full pass: **~25 s of bookkeeping for N=81**, i.e. effective O(N·(S + C + E)) where
O(S + C + E) once per pass would be correct - the algorithms are linear/heap-clean, the
loop re-does whole-domain scans per unit. With P passes this dominates idle wall time and
competes with builds during active waves.

### Ranked bottlenecks + concrete fixes (process side, stack-agnostic)
B1. **Dispatcher subprocess per no-op weave** (biggest): mirror `_cached_success` in the
    orchestrator (payload mtime vs weave-result mtime vs target exists) and SKIP the
    subprocess when nothing would be applied. Saves ~11 s/pass now; saves ~143 ms per
    future re-weave check.
B2. **Whole-tree repair + 1.3 MB index re-parse per gate**: cache `external_type_index`
    in-process keyed on (cache-file, mtime); gate `repair_test_imports` behind the tree
    fingerprint it was last run for (repair is a function of tree bytes - if the
    fingerprint is unchanged since the previous attempt's repair, it is provably a no-op).
B3. **Triple fingerprint hash per attempt**: compute once per attempt, pass down to memo/
    wave/memo-write.
B4. **O(N²) sibling scan**: one pass-level pre-compute of "payloadless T2 ids per project"
    reused by all attempts in the pass (O(N) once).
B5. Maven probe/suite costs are algorithmically sound since the wave gate (one probe per
    tree state, one suite per compile-green state); retries make k states ⇒ O(k) builds -
    bounded by MAX_TDD_RETRIES, not addressed here.

Note for the record: this analysis refutes the "selection algorithm is slow" hypothesis -
the heap/graph work is sub-millisecond; the wall-time sink is per-attempt re-derivation of
tree-wide facts (startup subprocess + full-tree scans). All four fixes are pure process
code and keep stack neutrality.

### 12.1 B1-B4 implemented (stage-agnostic, measured after)
All fixes are caches/short-circuits on GENERIC layers every stage passes through - no
toolchain vocabulary added anywhere; correctness is always "recompute when bytes move".
| hot cost (per attempt) | before | after | mechanism |
|---|---|---|---|
| weave dispatcher subprocess | 143 ms | 0.16 ms | `dispatchers._weave_up_to_date` mirrors the skill's `_cached_success` in-process; skipped unless payload/target moved since apply |
| repair_test_imports full scan | ~150 ms | 3.1 ms | gated on the content fingerprint it last ran on (`_REPAIR_STATE`); unchanged tree = provable no-op |
| external type index | 12.6 ms | 0.03 ms | in-process memo keyed (manifest, mtime), seeded from the file cache; benefits T1/T2 gates + closure equally |
| tree fingerprint | 11.8 ms x2-3 | 3.5 ms x1 cached | stat-signature tier over byte-hash + os.walk with build-dir PRUNING (old rglob("*") enumerated all of target/) |
| sibling payload scan | 2.1 ms/task (O(N²)/pass) | 0.00 ms cached | `dispatchers.payloadless_t2_ids` per-generation cache; invalidated at drain start, after every stage-2 session, and on revert; shared by gate deferral AND batch selection |
| verification (T3 typecheck / T2 build fallback) | full mvn per attempt | 1 build per tree-content | `verification._VERIFY_MEMO` keyed (root, mode) on content fingerprint; stub-verified: 1 real run, cache replays, payload/content moves invalidate |
| per-attempt bookkeeping total | ~310 ms | ~10 ms | - |
| per-pass (N=81, deferred wave) | ~25 s | ~1 s | - |
Regressions proven: cross-package import repair still fires (fixture, idempotent);
dispatcher skip flips to False when the payload is rewritten; verify memo replays
identical verdicts and re-runs after content change. Report-only note: these caches are
per-process by design (a restarted orchestrator rebuilds them on first pass).

## 13. T2 token-blowup investigation and the session-count fixes (2026-11-10)
Operator hypothesis: after the T1 wave, tester/coder contexts saturate because new
`blackboard/ast-context` and `blackboard/coder-changes` files are unnecessary at that
stage. Tested against the clean run's own records (`~/.copilot/session-state/*/events.jsonl`,
111 pipeline sessions 16:05-18:35):

- **Hypothesis REJECTED as the mechanism.** Input tokens per turn are FLAT at ~19-22K
  across the whole run (first tester with an empty board and the last with 41 contracts
  cost the same per turn). A single coder reads exactly ONE contract file (1.5-6.2 KB,
  its mandatory anti-hallucination input per its profile); testers touch the folders only
  as minor scope noise; prompts total 5-10K chars - the engine never embeds directory
  contents. Zero tester sessions exist after 17:01: no tester runs during T2/T3 at all
  (red re-derivation is deterministic). Largest single consumer in the window was an
  interactive IDE chat (93 calls, 4.56M input tokens) - dashboard contamination, not pipeline.
- **The real driver: session COUNT times the per-turn floor.** T1 wave: 42 sessions =
  5.90M input, 41/41 complete. T2 wave to the stop: 63 sessions = 6.94M input, 0 complete.
  47 singles covered 22 distinct units, EVERY one carrying retry feedback: T2-030 billed
  7 sessions, T2-006 6, pairs 60-90 s apart. Mechanisms: (1) `MAX_TDD_RETRIES` re-armed
  per pass, (2) the (correct) wave/compile-probe gate made attempts sub-minute, removing
  the accidental wall-time throttle on attempt burning, (3) revert-on-quarantine discards
  the payload so the next restore re-derives blind and rediscovers the identical failure,
  (4) batch-of-4 sessions explored out of scope (peer-source cats, `ls coder-changes`,
  queue greps: +27-36K/turn) and the same units then paid single retries anyway,
  (5) cross-unit contract conflicts ("does not override a method from a supertype" where
  the supertype is a still-queued peer's port) charged the adapter's attempts although no
  adapter payload can converge on a moving port.

### 13.1 Fixes implemented (engine scripts, stack-agnostic)
1. **Attempt ledger** (`orchestrators/attempt_ledger.py` + `tdd_engine.execute_with_tdd`):
   attempts and weave-reject bounces persist per unit in `blackboard/attempts/<id>.json`
   and are consumed for the unit's LIFETIME under its CONTRACT (task record + red record +
   AST contract bytes). A moved contract re-arms the full budget; an exhausted unit that
   comes back with an unchanged contract gets exactly ONE informed attempt, never a fresh
   3-session storm. Green clears the ledger.
2. **Failure-signature skip**: gate failures are digit-normalized (line/col/test counts
   move, defects do not). Two consecutive attempts - or a restored attempt vs the ledger -
   with the same signature quarantine on the spot; the remaining paid sessions are not
   burned. With the payload still on disk (WOVEN-UNVERIFIED restore) the memo replay makes
   this a ZERO-session close-out.
3. **Informed re-derivation**: a restored unit whose payload was reverted starts its first
   session with the previous failure injected as feedback (same FEEDBACK_TEMPLATE_CODER
   channel as in-run retries) instead of re-exploring from zero.
4. **Peer-supertype attribution** (`_blocked_by_peers` + `_peer_supertype_conflict`):
   own-file structural blame whose message names a supertype conflict, where a still-queued
   (or quarantined) peer owns the supertype's export, now DEFERS instead of charging
   attempts. Once the port producer lands green the adapter is re-charged normally.
5. Audit extended: `board_bulk_read` flags folder enumerations (`ls blackboard/queue`,
   `ls coder-changes`, ...) as scope violations (reporting aid; the ledger is enforcement).

### 13.2 Verification
Synthetic harness (`execute_with_tdd` driven with stubbed invoke/verify, temp blackboard):
17/17 checks - identical-repeat stops at 2 sessions not 3; different failures still use
the full 3; cross-pass restore bills 1 informed session; contract move re-arms fully and
starts blind (correct); payload+memo replay close-out bills 0 sessions; bounces are
lifetime-capped; green clears; supertype conflict defers with the peer queued and charges
once the peer resolves. All orchestrators py_compile; audit re-run on the live session
records (flags the real 17:0x batch enumerations, does not flag own-record reads).
Expected effect measured against the clean run: T2-030's 7 sessions become ~2 (attempts
would have deferred under fix 4 from the start); the 47-session retry wave caps at ~24.

## 14. The generics-echo deadlock: root cause and the neutrality-correct fix (2026-11-10)

**Symptom.** run12 replayed to fatal in ~1 min: 63 blocked units, the 10 quarantined T2
producers holding every missing symbol. Only 3 quarantine reasons were genuine: T2-006,
T2-030, T2-037; the other 7 were `dependsOn T2-006` collateral.

**Root cause (T2-006, and it was never the coder).** The weaver's new-file path builds the
class shell from the payload export: `PayloadNames.simpleTypeName` STRIPS the parameter clause
(`Box<T>` -> `Box`), `TypeSkeletons.shell` names an AST declaration with the stripped string,
and nothing re-declares the parameters. So a payload for `BoundedEventChannel<T>` always emitted
`class BoundedEventChannel` while its members used `T` -> javac `cannot find symbol: class T`
FOREVER. The coder had already found the only lever it could see (declared `<T>` in `export`,
run11 attempts 2-3); the weaver silently ignored it; identical-signature quarantine + 7 collateral
+ 63 blocked units. The process made a coder pay for a tool bug it cannot fix.

**Fixes (all in process/tool code, stack-specific parts in the Java tool/skills only):**
1. `PayloadNames.typeParameters(export)`: balanced-`<>` parse, top-level comma split, bounds
   preserved. Also repairs a latent crash: `simpleTypeName`/`packageOf` used lastIndexOf('.')
   BEFORE cutting generics, so an export with a qualified bound (`V extends java.io.X`) threw.
2. `TypeSkeletons.shell/create`: class/interface shells declare the payload's type parameters
   (enum cannot be generic per JLS; records ride their header path).
3. `TypeDeclarations.findOrCreate`: an existing shell WITHOUT parameters is upgraded once by a
   payload that declares them; a shell that already has parameters keeps its own (re-weave
   idempotent: parameter count never grows).
4. Regression tests in `JavaASTWeaverGenericShapesTest` (3): new-file generic class compiles and
   survives re-weave; existing plain shell upgraded once; multi-parameter + bounded export
   splits parameters, not words. 56/56 green; fat JAR rebuilt; dispatcher smoke on the real
   T2-006 shape weaves `class BoundedEventChannel<T>`.
5. `tasks.exported_product` now strips the parameter clause before the identity split (the
   producer/missing-symbol matching of closure/gate/blame uses the bare head name; Java-flavored
   examples that leaked into orchestrators were reverted).
6. Coders learn the convention where it belongs: the two coder skills
   (`java-springboot`, `java-standard-best-practices`) spell the Java shape; the shared agent
   profiles and `prompts.py` (WEAVER SHAPE + feedback template) stay STACK-AGNOSTIC: "declare
   the parameters in `export`, spelled as the language writes them; your stack skill gives the
   shape". (Operator correction: the first pass put `Box<T>` examples into agent-coder.md and
   prompts.py - reverted; the §9 audit rule holds.)
7. Self-inflicted crash found while resuming: `test_gate._failure_detail` used
   `tasks.exported_product` without importing tasks -> NameError killed the drain. Fixed; queue
   was not corrupted (a crash is not a verdict: 0 new quarantines, 83 units stayed queued).

**Resume evidence (run13).** T2-006 restored by `--retry`: ONE informed session (ledger cap,
not 3), coder re-declared `export = BoundedEventChannel<T>`, and the fixed weaver wove
`public class BoundedEventChannel<T>` - first time in 13 hours of runs. T2-037: one informed
session, re-emit, weave, recorded test. Remaining quarantine reasons now charge only the units
that own the blamed file; peers defer.

## 15. The gate-fallback storm, the payload-grammar gaps, and the self-healing drain (2026-11-10, run12-run26)

Operator directive driving this pass: "no real progress in T2/T3, stuck for several seconds per
attempt, tokens fine but performance terrible - inspect the orchestrators and task selection."

### 15.1 Where the seconds went (measured, not inferred)
Task SELECTION was exonerated again (heap/deferral sub-ms, §12 holds). The stall was in the
GATE VERDICT path - run12/13 replayed to fatal because every unit re-derived a whole-tree fact:
- one `mvnw test-compile` on this tree = 13.6 s (measured); a recorded-test rerun = 15-30 s;
- run13 log: after ONE wave build, ~30 units each fell back to their own scoped Maven run
  (36 reruns + 5 probes ≈ 10+ min per tree state, repeated per weave - the storm);
- cause: `wave_gate_verdict` shared only `status=compile_error`; a decisive module failure
  WITHOUT per-class evidence (surefire boot crash, toolchain error) returned None => per-unit
  rebuild of byte-identical output.
Fixes (test_gate.py, toolchain-neutral - speaks only the runner's status contract):
- `_tree_wide_failure`/`_shared_verdict`: decisive non-pass status + zero class evidence =
  TREE fact -> shared with every unit, cached per fingerprint, served before the command-shape
  gate (a cached fact needs no selector);
- decisive compile PROBE skips the suite boot entirely (saves a full `mvnw test` per broken state);
- a scoped fallback that discovers a tree-wide failure PRIMES the wave cache (siblings free);
- memo_version + wave stamp bumped to v5 whenever verdict SCHEMA changes (v4 caught run16/17's
  stale-cache false hole abort - a schema bump is the only honest invalidation).
Result (run16+): scoped per-unit reruns 36 -> 0 per pass; whole drain replays in seconds.

### 15.2 Two payload-grammar holes that made convergence IMPOSSIBLE (not slow - impossible)
1. Generic export dropped by the weaver (§14) - fixed there.
2. `implements`/`extends` had NO payload field. T2-037's frozen test demands
   `isInstanceOf(TelemetryStreamGateway.class)`; the coder invented an `implements` key; Jackson
   ignoreUnknown silently dropped it; no number of retries could converge. Fixed:
   - CoderChangesPayload: optional `extends` (string) / `implements` (list) via @JsonProperty;
   - SuperTypeWeaver: additive, idempotent (simple-name identity), interfaces route `implements`
     to extended types, exception placeholder replacement only; wired into JavaASTWeaver;
   - writer validates the shapes (a malformed guess now ERRORS with the field named instead of
     being dropped - the silent-drop was the root disease);
   - 58/58 weaver tests (new: adapter implements, exception extends-replace, idempotent re-weave);
     CLI smoke wove `class ReactorTelemetryStreamGateway implements TelemetryStreamGateway`.

### 15.3 Attribution without toolchain vocabulary (operator neutrality correction #2)
First cut of "the gap sits on MY exported type" parsed javac text in tdd_engine - the operator
rejected it: orchestrators must be generic, run-test-tool owns syntax. Final shape:
- run-test-tool extracts `member_demands: [{member, owner, kind}]` from ALL toolchains it already
  parses: javac `symbol: method|constructor|class` paired with `location: class T` AND
  `location: variable v of type T<...>` (the form run16 proved mandatory), tsc TS2339,
  AttributeError, go field/method-undefined; `[ERROR]` log prefixes normalized;
- tdd_engine reads the FIELD: `_own_type_member_demand` (owner == exported_product; `class`
  demands only when the member is not resolvable elsewhere = genuinely nested),
  `_unresolvable_missing` subtracts conditional demands (kills run16's OverflowException false
  hole abort), `_failure_detail` renders "YOUR TYPE X MUST PROVIDE: ..." FIRST (run23: the
  coder fixed publish/overflow but never saw the `offer` demand buried under 6 foreign missing
  symbols - the demand must lead the feedback or it is invisible);
- test blame now claims for the test's OWN implementer first (`_own_test_file` via the T1 index
  entry): the RecordTelemetryServiceTest `incompatible types` pair-defect charged T2-010 (whose
  type merely appears as the argument) for 3+grant sessions while T2-025 - whose payload owns
  the method signature - deferred forever. Charged-correct: T2-025 now moves line-by-line.
- `_blocked_by_peers` precedence: own-type demand > pending-peer deferral > own-file structural
  > test-attribution (demand-shaped only; conversion-shaped blame with no owner defers).

### 15.4 The informed-attempt semantics that actually converge (attempt-ledger v2)
- run15 lesson: a restored unit WITH payload got a "granted informed attempt" that ran BLIND
  (skip-agent replay) and burned the grant with 0 sessions - the failure was never shown.
- run18 lesson: gating the re-ask on `sig == last_sig` missed near-miss signatures (tree moved
  slightly) and burned grants the same way. Final rule: the grant's FIRST act is a FREE
  re-verification: green -> close unbilled (the §13.1 win kept); failure already SHOWN
  (fed == sig) -> close zero-session; otherwise -> the granted attempt runs INFORMED by the
  replay's own verdict. `fed` (attempt ledger) marks every failure actually delivered.
- auto-grant (pipeline watch loop): after STUCK_PASSES_FATAL, instead of exiting, the drain
  restores qualifying quarantined units BY ITSELF: budgeted units (consumed < cap - the
  same-signature break had ended their loop early), exhausted-but-unshown failures, and
  exhausted+shown units whose WORLD MOVED (gate memo tree fingerprint stale). Cascade
  quarantines ("dependsOn X not resolvable", never charged) unwind to a FIXED POINT in one
  batch: granting T2-006 restored its whole 16-unit chain instantly. Operator --retry remains
  available but is no longer the only heartbeat: the loop is self-sustaining until the grant
  cap (3/contract) locks a truly doomed unit - then the fatal report is honest.

### 15.5 Coder-guidance closed loops (skills, stack-specific by design)
- export generics + supertypes + imports-of-supertypes: java-springboot / java-standard skills
  (shared agent profiles + prompts.py stayed language-neutral: "spelled as your language writes
  them; your stack skill gives the shape" - operator corrections #1 and #2);
- `final` fields: inline initializer OR constructor assignment, never both - the "cannot assign
  a value to final variable" defect family that consumed gate cycles across T2-032/037/006.

### 15.6 State at the end of this pass
Queue drained 83 -> 77 with complete climbing; failures are ADVANCING per session (T2-025:
incompat set moved 104/123/133 -> 148 across sessions - informed retry bites now). Tokens flat
(1 premium request per session, ledger caps enforced); wall time per tree state: 1 probe
(~14 s) + O(N) millisecond replays. Remaining quarantines are genuine coder-defect convergence
loops, not tooling holes: the classes that blocked EVERY run for two days (silent grammar drops,
per-unit rebuild storms, blind grants, bystander charges, false hole aborts) are all closed with
harnesses (gate-wave 16/16, attempt-ledger 29/29 incl. S9 auto-grant semantics).

## 16. Day-2: the end of feature-enumeration (full-declaration redeclares, gauntlet-gated)

Root cause named after §15: the tools break EXACTLY where they synthesize source from
schema fields, and are flawless wherever they receive full text (members never broke;
shells/signatures broke repeatedly). Every §14/§15 "language feature" fix (generics on
export, implements/extends, static) was that one bug in new clothes: a lossy payload
schema + silent drops.

Implemented (day-1 gauntlet now guards every step):
1. WEAVING: a method `signature` may be the COMPLETE declaration (`public static Order
   from(Cart cart)`). fullDeclaration() parses it (grammar-ladder validated), and the
   twin method - matched by parameters OR SAME ERASURE (a test that exposed javac's
   "name clash: same erasure" semantic; text-typing alone would have appended a
   clashing twin) - is REDECLARED IN PLACE: modifiers, method-level type parameters,
   return type, throws all ride the text; existing annotations are kept. The bare
   contract spelling keeps the old path. NO new schema field is needed for the next
   unforeseen language shape - the text carries it. This is the mechanism that ends
   the treadmill, not another feature.
2. PRINTING: LexicalPreservingPrinter cannot track structurally-replaced nodes
   (observed: correct output, col-0 indentation). SourceFiles now marks a re-declared
   CU and renders such files with the clean printer - cosmetic correctness restored
   without losing the file's other members' positions.
3. Docs updated in the shared-neutral voice (prompts WEAVER SHAPE: "written TWO ways"
   semantics; the two java coder skills carry the concrete spelling). Writer schema,
   agent profiles and the §15/§16 boundary rule unchanged.

Verification: weaver JUnit 60/60 (new case: full-declaration replace keeps
`@Deprecated`, erasure-colliding twin replaced once, idempotent re-weave); gauntlet
46/46; ledger/gate harnesses 29+16 green; CLI smoke: T2-031-shaped instance->static
factory converts in one weave, compiles, idempotent.

Known debt left (documented, gauntlet-able): last text-phrase tables in the engine -
`SUPERTYPE_CONFLICT_PHRASES`, `test_gate.is_cascade` - still read normalized EXCERPT
lines. Migration plan: the runner already parses these same shapes; emit a
`conflicts: [{file, kind}]` field (supertype|cascade) alongside member_demands, have
the engine read the field with the phrase table as fallback. Mechanical, one session.

Decision posture (operator asked "which option is best"): Day-1 gauntlet + loud
boundary (done, §15 + this suite), Day-2 replace-don't-synthesize (this section),
then ONE validation drain of seed 002 before any further tuning: the loop's remaining
blockers are coder-semantics (final-assign discipline, whole-demand re-emits) and the
architect-level recordSequenced(TelemetrySample)/TelemetrySampleEvent pair - both are
EVALUATION SIGNALS the harness must surface, not more tool bugs.

## 17. Debt repaid: problem_kinds - the engine reads fields, never phrases

The last two compiler-text readers in the orchestrators (the supertype-conflict phrase
table and the cascade-vs-structural message scan) are migrated to a runner field, per
the §15 neutrality rule and the §16 stated plan:

- run-test-tool classifies every positioned compile error into
  `problem_kinds: [{file, line, kind}]`, kind in {supertype, missing-symbol, other},
  phrase tables for javac/tsc/go/python living ONLY in the tool; for supertype entries
  it also reads the blamed file and ships its declared `supertypes` names, so the
  engine's "is this moving port owned by a queued peer?" question is answered without
  either a message regex or a source-grammar read in orchestrator code.
- tdd_engine consumes the field first (`_own_structural`, `_peer_supertype_conflict`);
  the phrase/regex paths remain ONLY as fallback for verdicts recorded before the
  field existed. `_shared_verdict` carries problem_kinds through wave/memo replay;
  memo_version 5 -> 6 so no pre-kind verdict can masquerade as classified.
- Real classification bug fixed on the way: supertype-phrase errors (javac "method
  does not override...") were NOT in RE_COMPILE_HEAD at all - they misclassified whole
  compile failures as status=error (the exact shape that triggered the §15.1 per-unit
  rebuild storm). Positioned pattern now also understands tsc `file.ts(line,col)`.
- Gauntlet grew with the migration: G15-G17 (runner normalization incl. declared
  supertypes + tsc phrasing) and A7-A9 (field-driven deferral/charging with message
  text deliberately lying). 53/53 green; live-board proof: current verdict classifies
  compile_error, holes 0, every cached failure result carries attribution fields.

Verdict: the orchestrator suite no longer reads compiler output anywhere; the syntax
boundary holds end to end. Validation drain launches next.

## 18. Observability and the last deferral deadlock (run31/run32)

Restart blindness fixed (operator: "if you restart the process I cannot see anything"):
- every tagged log line now carries HH:MM:SS (pipeline entry patches print for `[...]`
  lines only; passthrough output untouched - pinned by F1/F2);
- one `[pass  ]` heartbeat per drain pass: wall seconds + cumulative
  queue/complete/quarantined counters + processed/blocked - restart-proof progress
  (pinned by the heartbeat fixtures);
- `python3 orchestrators/status.py`: read-only board view with per-quarantine LEDGER
  state - budget left, grants used, whether the last failure was ever SHOWN, and the
  eligibility verdict an auto-grant would compute (pinned by F3).

What the new visibility immediately exposed: a complete mutual-deferral cycle -
the adapter (T2-025) deferred because §13.1 fix-4 saw its port producer still pending,
the port producer deferred because all blamed files were foreign, and no unit was ever
charged: four zero-work passes, fatal, EVERY restart, forever. The fix-4 rule predates
the ledger guards that make charging safe. Relaxation (A10/A11): while the claimed
supertype is not a file on the tree, defer as before; once it is MATERIALIZED (woven,
concrete, if unverified), the structural defect in the adapter's own file CHARGES -
both gates otherwise deadlock on the same compile. Churn is bounded by the same-
signature break, the fed marker and the grant cap.

Observed consequence exactly as designed: T2-025 was charged, ran 3 attempts +
3 informed grants, and its failure MOVED each round (supertype shape -> own-file
structural -> the frozen-test pair defect). It is now locked at full budget - and
the remaining defect is the documented architect-level contradiction: T1-025's test
calls `recordSequenced(TelemetrySample)` while T1-024's port contract spells the
parameter `TelemetrySampleEvent`; no single unit's payload can satisfy the pair.
That is the honest terminal state of the automatic loop on this seed: the machinery
converges everything convergable and then names, loudly and with evidence, the one
thing only the architect stage (or an operator) can decide. Next evaluation signal
for the pipeline: the decomposition stage should schedule an adapter/overload task
where two frozen contracts of the same domain disagree - the demand is detectable
(the pair-defect blames two owned files with zero member demands and no owner).

## 19. The root of roots: the plan-time API contract table (ast_hints) is now live-enforced

§18's "architect pair-defect" traced one level deeper with evidence: the skills
ALREADY defined the contract table (task-decomposition: "method signatures with
parameter and return types"; tester: "shapes come ONLY from ast_hints.methods"),
but every emitted task carried ast_hints = {} because:
- the live schema (settings.REQUIRED_KEYS + tasks.validate + the architect prompt's
  key list) never contained ast_hints;
- the one validator that enforced it (writer-architect-file) required ids matching
  `T-###` while the pipeline's ids are `T2-###` - it had never validated anything.
Left with an empty table, the tester improvised `recordSequenced(TelemetrySample)`
from prose while the port froze `recordSequenced(TelemetrySampleEvent)`: two frozen
artifacts, one contradiction, six coder sessions burned, domain stop. Skill text
without a machine gate is a wish.

Enforcement now (all stack-neutral: names and opaque declaration strings):
- tasks.validate: ast_hints is a schema key; PLANNING mode (task_queue.emit_tasks)
  requires it for stage 1-2 and rejects `implements` with an empty `methods` table;
  resume mode only shape-checks (older boards stay loadable until the wipe);
- architect prompt contract documents the table + "prose may never be the only place
  a signature exists"; identical table required on the unit's stage-1 and stage-2
  tasks; the decomposition skill states it as the single API truth;
- tester profiles: empty/absent table on a behavioral unit = PLAN ERROR, report and
  stop - improvisation from prose is explicitly forbidden as the failure mode it is;
- writer-architect-file aligned to the live gate (id pattern, pinned {type,task_id}
  dependencies, returns may be ""); closure's gap-producer tasks carry the table;
- PROMPT_KEYS includes ast_hints: the table ships inside the agent-facing task brief
  AND joins the attempt-ledger contract hash (a moved table re-arms the unit's
  budget - it changes what "the same contract" means);
- gauntlet section G pins all of it end-to-end (accept/refuse/emit-land/emit-reject/
  legacy-resume), 66/66 green.

Restart protocol after this change: commit the tree, wipe ONLY the state folders
(blackboard/, projects/, /tmp logs), relaunch from seed. The next plan cannot ship
an API-less unit; the next contradiction - if any - dies at emit time with a named
reason instead of costing a domain.

## 21. Token forensics of the fresh runs + deterministic red recovery

Measured (copilot session-state usage, windows exact): fresh02 no-batch = 2,187,082 input
over 22 sessions for 19 units (~115K/unit); fresh04 batch-ON = 256,343 input over 2
sessions for 5 units (~51K/unit) - batching halved per-unit cost; the dashboard "spike"
was the single large batch transcript (147K) plus one batch killed mid-run (110K spent,
its units' tests+reds persisted on disk - zero data lost, resume closes them free).

That last residue was the only remaining double-payment in the design, now eliminated:
dispatchers.derive_red_phase - test file on disk + missing/unusable red record = the
engine runs the scoped command itself (shape shared with the green gate via
test_gate.command_from_test_path), pipes the official writer, revalidates. A session is
charged only when the TEST itself is wrong, never to re-observe a build result.
Pinned as H8-H10; gauntlet 80/80.

## 22. Profile & skill compression: every agent body and SKILL.md under 450 tokens

Motivation: per-turn session cost is dominated by the fixed prompt - agent profile +
loaded skills ride on EVERY turn of EVERY session. Nine passes compressed all 9 agents
(18 files incl. the .github mirrors, kept byte-identical bodies), 15 SKILL.md and the
2 previously-empty tech-stack skills down to <=1740 chars (~450 tokens) each.

What was preserved verbatim, because these are functional identifiers, not prose:
writer/tool command lines and their flags, exit-code semantics, blackboard paths,
payload key names, schema key lists, the mcp-server container blocks, gauntlet-checked
message substrings. What was removed: connective prose and - more importantly -
DUPLICATION: coder/tester profiles restated stack syntax that already lives in the
stack skills; the profiles now delegate ("syntax and payload shaping live in the stack
skill") so a stack rule has exactly one home.

Incidental contamination fix: tech-stack/java-springboot3 had shipped with the seed's
base package hardcoded (`com.pulsestream.telemetry`); it now reads the value from the
strategy's module_layout.base_package - agents/skills remain stack-generic (verified:
no seed identifier survives in .opencode/{agents,skills}). Gauntlet after compression:
80/80 green (the H5/H8 substrings live in orchestrators/prompts.py, untouched).

## 23. Day-3: the validation drain + two compression regressions caught by the drain itself (2026-11-11)
Executed the §19 restart protocol: state was clean-committed (tag
`board-pre-validation-2026-11-10` + tar in /tmp/opencode/archive), wiped ONLY
blackboard/ + projects/, relaunched seed 002 --watch. Launch tip: use `python3 -u` -
stdout through `tee` block-buffers and blinds live monitoring (same pain §18 fixed
for the log content; the flag fixes its delivery). Copilot CLI 1.0.109 still defaults
to claude-sonnet-5.5: no billing surprise from the update. First-session forensics:
turn-1 cacheWrite 9-12K vs yesterday's ~30K fixed floor - §22 compression is working.

R1 - the mapping stage burned its FULL 10-call budget and produced NOTHING on the
first restart: every writer-file call was rejected. Root cause was a §22 compression
REGRESSION, not agent capability: the mapping profile+skill payload contract was
rewritten into invented vocabulary (`relationships[{type,...,rationale,risk}]`,
`shared_languages[]`, top-level `source_report`) while the actual writer schema is
`context_map: [{upstream, downstream, relationship, direction, exchanged_information,
boundary_protection}]` + `cross_boundary_flows: [{business_process, contexts_involved,
consistency_expectation}]` + metadata.source_report = a DIRECTORY. Agents obey docs;
docs lied; §22's own invariant (functional identifiers preserved verbatim) was violated
here. Every restart would have re-paid the same ~150K for zero artifacts.
R2 - same pass, second drift: relationship enum APPROXIMATIONS ("Published language",
"Anti-corruption layer") vs the writer's canonical vocabulary ("Open host service /
published language", "Anticorruption layer") - the pre-compression table had them exact.
Found without an agent session by replaying the fixed contract against the real writer.

Fixed (commits 131869d, 22c9199):
1. Both mirrors of the mapping profile + the domain-context-mapping skill now carry the
   writer-true key lists, the exact RELATIONSHIPS enum, and the "writer exit 1 => run
   --emit-template, never guess" rule (discovery pair verified already correct).
2. Generic guard: writer-file now appends `hint: rerun with --emit-template <kind>` to
   EVERY schema rejection - a mis-documented shape costs the agent ONE extra call, not
   ten blind iterations (the tool tells the truth about itself).
3. Gauntlet K1-K4 (test_skill_scripts.py): the writer module's constants are now
   DIFFED against the prose of every mapping/discovery profile and skill - docs and
   schema cannot drift silently again; the emitted skeleton must feed back through the
   writer; 39+53 green.
4. Audit of every doc->script CLI call (--flags vs real argparse): all invocations
   match; the corruption was confined to prose key lists.

Resume evidence (run2): `[skip] discovery files already valid` (zero re-billing),
mapping GREEN in 4 calls ("writer accepted it" on the first try), strategy/db sessions
normal (9-15 calls; architect 15/12 WARN noted - session completed, hard kill never
fired). Drain continues toward the first clean per-stage measurement.

### 23.1 R3 - the context-boot deadlock (T2-012): attribution now covers RUNTIME graphs
The validation drain stopped itself at the mutual deadlock the §8/§14 pattern predicted:
T2-012's FROZEN test (T1-012, tester-authored) is `@SpringBootTest` - a unit-scoped
gate that can only pass when the WHOLE bean graph exists. Boot died demanding
`No qualifying bean of type SampleValidator` - a PENDING peer's exported product (T2-003,
still queued). No payload of T2-012 could ever converge: the engine charged 3 attempts
+ 2 informed grants (~5 sessions) on an impossible verdict, then quarantined, and the
quarantine REVERT removed the class other frozen tests import - every remaining test
file stopped compiling, all 10 peer units deferred on it, fatal "no progress". Layered
root causes: (a) `assertion_failure` bypassed `_blocked_by_peers` (status filter was
compile-only), (b) wave per-unit verdicts DROPPED attribution fields, (c) the §13.1
fix-4 family (supertype deferral) had no runtime-graph counterpart.
Fixed (commit 70c0743, gauntlet G18+A12-A14, 96/96):
1. run-test-tool emits `bean_demands:[simpleType]` for context-boot demands (Spring
   phrasing parsed in the tool only; neutrality rule held).
2. test_gate carries bean_demands/member_demands/problem_kinds through the wave per-unit
   verdict; memo_version 6->7 (stale fieldless verdicts cannot replay).
3. tdd_engine._pending_bean_demand: DEFER (zero cost, payload stays woven, tree keeps
   compiling) while a queued/quarantined peer owns a demanded bean; CHARGE when the bean
   is the unit's own exported type (making one's own type a bean IS the unit's contract)
   or when no pending peer owns it (surfacing, capped, honest - assembly territory).
4. This also closes the revert-hole cascade: the boot-blocked unit no longer quarantines,
   so its class stays on the tree and peers keep compiling.
Eval signal recorded (NOT fixed in scripts): testers writing `@SpringBootTest` unit
gates couples stage-2 verification to full-graph assembly; the plan invariant should
reserve boot-wide tests for wiring/assembly units (candidate for the tester profile +
task-decomposition skill next).
Resume (run3, --retry): T2-012 runs its last granted session; boot failure now defers;
peers proceed. Watch: first `[wait ] ... bean` line.

### 23.2 R4 - the revert-freeze: WOVEN-CLEAN quarantine (run3 -> run4)
T2-003's pair-defect quarantine REVERTED SampleValidator.java - a type ten peers'
files import. Every unit then deferred on `missing=SampleValidator` (compile hole),
auto-grant restored T2-003, its gate re-verified identically (the failure lives in
TELEMETRYSAMPLE's null-guard vs the frozen test's null construction - nothing the
validator's payload can change), reverted again: a 2-session-per-3-minutes freeze
loop that had already cost the domain twice. The revert doctrine ("quarantined code
must not poison the shared tree") is right for COMPILE poison and wrong for a payload
the COMPLETED SUITE JUST PROVED harmless: module compiled, suite ran to completion,
peers' classes all adjudicated, only the unit's own class red. New rule (commit
43c0479, gauntlet A15-A17): at quarantine, if the fresh verdict says assertion_failure
and the payload is woven, KEEP it (`[keep]` + [WOVEN-CLEAN] marker on the error
reason); compile_error/not_run/no-memo -> classic revert (poison proven or unproven).
A kept unit that later turns green via re-verification closes without ever leaving
the tree. Immediate effect (run4): T2-002/005/010 went green seconds after T2-003's
[keep] - the domain unfroze.

### 23.3 R5 - the materialized-bean deadlock and the first end-to-end boot recovery (run5)
Even with bean_demands deferral, run4 deadlocked 19 units on one boot demand:
`No qualifying bean of type SampleValidator` while the CLASS sat materialized (woven
by the locked T2-003). Deferral was waiting for something waiting could never deliver:
the missing piece is a REGISTRATION, the plan's wiring unit (T2-015, the only task
whose ast_hints/intent owns bean wiring) can write in its own file - the §18 A10/A11
materialized-port doctrine applied to the runtime graph. New rule (commit 5f?? ->
"materialized-bean rule", gauntlet A18/A18b): once the demanded class exists on the
tree, CHARGE the demanding units (bounded by same-signature break + fed marker +
grant cap), never defer; class absent -> defer stays.
run5 (11:49+): T2-012/T2-008 charged their repeat-break (~1 session each, [keep]-
woven), T2-003 closed zero-session ('failure already shown'), T2-015 ran its informed
attempt, registered the bean, WENT GREEN -> T2-009's boot failure resolved by the
world moving and closed green via skip-agent re-verification at ZERO sessions.
T3 evaluator wave flowing. 36/49 complete at 11:55, per-unit token cost in run5
~19.5K (batch + ledger + wave-cache). Remaining quarantines: T2-003 (the honest
architect-level pair defect: frozen T1-003 constructs TelemetrySample(status=null)
while completed T2-002's ctor requireNonNull's it - operator/plan arbitration, NOT a
tool bug, exactly the signal §6/§18 said to expect) and boot victims whose re-verify
grants now proceed automatically.
