# Project inspection — high-performance-time-series-telemetry-ingestion (seed 002) — 2026-11-13

Supervision of the delivered tree at
`projects/high-performance-time-series-telemetry-ingestion-pipeline/services/telemetry-ingestion-processing`
plus the final board state, against `seed/002_description.md` and yesterday's
`RUN-SUPERVISION-2026-11-12.md`. The project itself was **not modified**: every experiment ran in a
throwaway copy at `/tmp/opencode/scratch/tsi`.

> **Scope note (updated 2026-11-13 afternoon).** The tree inspected below (PART I) was the
> 2026-11-12 drain's output; the operator then wiped board and project, and every fix in the
> Implementation record shipped and was validated by a fresh drain (13:06–13:56, see
> `RUN-SUPERVISION-2026-11-13.md`). This section is retained **verbatim as the historical
> record** and the provenance of the fixes. **PART II (end of document) inspects the
> REGENERATED project and is the current truth about the delivered artifact.**

## Verdict up front

| dimension | yesterday's report claimed | today's empirical state |
|---|---|---|
| board | 89/96 complete, 2 quarantined, 5 deferred | matches exactly (complete 89, error 2, queue 5) ✔ |
| build | boot GREEN at 16:17, "tree moved afterwards" | **`mvn -o test-compile` FAILS on PRODUCTION code** — tree does not build ✘ |
| root contradiction | "exactly one contradiction at the root" (static call at `DefaultIngestTelemetryUseCaseTest:79`) | **two** paired contradictions (see F2) ✘ |
| boot GREEN meaning | 1/1 smoke test | smoke test is **vacuous**: the booted context contains zero domain beans (F3/F4) ✘ |
| deliverable | "named, evidenced, budget-bounded" tail | **not deliverable**: the 89-complete figure is a board statistic, not a working application |

Everything else about yesterday's board accounting checks out. What the supervision report could not
see is that the exit state left the tree **non-compiling**, and that the "boot green" that closed the
run never proved wiring, because the composition root cannot see the code.

## How each finding was proved

* `mvn -o test-compile` on the real tree → main compile error (F1).
* Read of every frozen test vs. its owner's production file (F2, F6).
* Scratch copy with the *minimum* unblock (faithful T2-020 impl per intent + the two disclosed
  test-shape fixes) → `mvn -o test`: **154/166 green**; the only remaining reds are the two genuinely
  unfinished units (F5, F6). My scratch `DefaultIngestTelemetryUseCase` passed its frozen test 8/8 —
  the T2-020 contract IS satisfiable once the test pair is coherent.
* Scratch-only `@SpringBootTest` bean inventory → context boots but `IngressController`,
  `IngestTelemetryUseCase`, `CorrelationIdWebFilter` are **absent** (F3); after adding
  `scanBasePackages`, startup now fails on a **missing `CorrelationContext` bean** (F4); after adding
  that bean too, the inventory goes green (full remedy chain demonstrated).

## Findings

### F1 — CRITICAL: the delivered tree does not compile (production code)

`src/main/java/com/pulsestream/telemetry/shared/config/TelemetryWiringConfiguration.java:3,57` imports
and constructs `DefaultIngestTelemetryUseCase` — the artifact of **quarantined T2-020**, which does not
exist in `src/main`.

```
ERROR TelemetryWiringConfiguration.java:[3,55] cannot find symbol
ERROR TelemetryWiringConfiguration.java:[57,20] cannot find symbol
```

The engine rolled back T2-020's payload on quarantine but left the assembly-era consumer behind. The
stale `DefaultIngestTelemetryUseCase.class` still present in `target/` until this inspection proves the
file existed at 16:17 (boot GREEN) and was deleted afterwards. A "contract-regression reopen" (fix #12)
only rescues files **owned by a completed unit**; `TelemetryWiringConfiguration` is an assembly product
(T4-001 emitted **no** coder-changes payload), so nothing revisits it. Yesterday's exit summary
described the state as a clean definition-of-done tail; it is actually a broken main source.

### F2 — CRITICAL: the root contradiction is a PAIR, not one

Yesterday's FINAL section names one line (`DefaultIngestTelemetryUseCaseTest:79`, static call). The
board's own T2-020 error string already contains the second half:

```
CorrelationContextTest.java:15,48 ] CorrelationContext() has private access
```

The operator-corrected `CorrelationContextTest` (line 15) does `new CorrelationContext()`, but the
class re-emitted at 17:01 keeps `private CorrelationContext()` — because **T2-014's intent prose still
says** "Final utility class … Private constructor". The intent contradicts its own ast_hints table
(instance members) and DI usage; per the new "table wins over prose" rule the prose should have been
rewritten too, and wasn't. This is why T2-014 sits back in `queue/` (reopened via fix #12) and why the
whole deferred cluster never cleared. **The plan must re-emit T2-014 with a coherent
contract (recommendation: public constructor + instance methods), or the frozen pair stays impossible.**

### F3 — HIGH: the composition root cannot see the application (boot-green was vacuous)

`@SpringBootApplication` sits in `com.example.telemetry_ingestion_processing` (Initializr default),
while **every** production class lives under `com.pulsestream.telemetry`. No
`scanBasePackages`/`@ComponentScan` exists anywhere in `src/main`. Empirical proof (scratch):
the booted `ApplicationContext` contains zero `IngressController` / `IngestTelemetryUseCase` /
`CorrelationIdWebFilter` beans. The scaffold smoke test lives in `com.example…` and passes trivially
over the empty context.

The prior committed tree (run 1, `git log`) had the app class at `com.pulsestream.telemetry.…` and this
worked; the rebuild regressed it. The scaffold skill honored the seed's *version* pins verbatim
(Java 21 / Boot 3.5.16 — verified resolving) but the **package pin moved the code away from the
entry point** nobody owns. Assembly's STACKS row checks the smoke class + entry marker — never that the
entry point actually loads the domain.

### F4 — HIGH: even with scanning, startup fails — no `CorrelationContext` bean provider

`CorrelationIdWebFilter` (T2-029's file, already present) constructor-injects `CorrelationContext`, but
no `@Bean` and no stereotype provides it. With `scanBasePackages` added in scratch, the context refresh
dies: `No qualifying bean of type '…CorrelationContext'`. This gap is owned by **no queued task** —
T4-001 finished by passing the vacuous smoke test. Adding the `@Bean` completes the boot (proved green).

### F5 — MEDIUM: T2-002/T3-002 never produced the second YAML document (8 frozen-test failures)

The frozen `ApplicationYmlTest` (`sources.hasSize(2)`, `testProfileDocument_loaded_usesH2AndDisablesFlyway`)
requires a `---` profile document with `spring.r2dbc.url=r2dbc:h2:mem:///telemetry;DB_CLOSE_DELAY=-1` and
`spring.flyway.enabled=false`. The delivered `application.yml` (edited 17:02 during the storm) has only
the single base document → all 8 tests fail. The base document itself satisfies every literal.

Adjacent runtime risk (same file, no unit owns it): Flyway is enabled with
`locations: filesystem:db/migrations` but **no `spring.datasource.url` is ever set** — Boot will
auto-detect the runtime-scope H2 and migrate a throwaway in-memory database while R2DBC writes to
Postgres. Production schema is never migrated by this configuration. Worth an operator decision
(explicit JDBC url from the same env var, or disable flyway and own migrations externally).

### F6 — MEDIUM: T2-029 never produced the delegation (4 frozen-test failures)

The delivered `CorrelationIdWebFilter` hardcodes `HEADER = "X-Request-Id"` / `KEY = "requestId"` and
never calls the injected `correlationContext.headerName()/contextKey()`. In scratch (class shape fixed)
the frozen test's 4 errors move from `MissingMethodInvocationException` (yesterday's static-era class)
to `UnnecessaryStubbing` — proving the remaining red is the unit's own unfinished contract, not the
test. Correctly still pending.

### F7 — LOW: the delivered tree is not in git at all

`git ls-files projects/` tracks **45 files, all from run 1** (old `ingestion/eventlog/reordering`
packages, old `V1__create_event_log_store.sql`). `git status` shows them as deleted and **20 `??`
untracked entries** carrying yesterday's entire output. One `git checkout` or clean wipes the run. The
supervision protocol deleted the project at the start of the day; nothing re-committed it at the end.

### F8 — LOW: hygiene deltas

* `logs/telemetry-ingestion-processing.log` (161 KB of run residue) is not gitignored (no `logs/` entry
  in `.gitignore`) — and `application.yml` writes there by design, so it will regenerate.
* `HELP.md` left from Initializr (tracked already — cosmetic).
* `target/` still held a `DefaultIngestTelemetryUseCase.class` from a deleted source (partially
  invalidated by this inspection's failed compile) — never trust `target/` when reading state.

### F9 — OBSERVATION: the broadcast stream has no subscriber in this tree

`TelemetryEventPublisher.events()` has **zero call sites in `src/main`**. The seed's "backpressure-aware
event broadcasting to downstream event streams" terminates at an in-process `Sinks.Many` that nobody
reads; on zero-subscriber emits, `InMemoryTelemetryEventPublisher` counts
`recordBackpressureOverflow(DROP_OLDEST)` — the metric inflates for "no downstream wired", which is an
artifact-boundary choice the architect doc should state explicitly (or a follow-up egress unit is
missing from the plan).

## What was verified GOOD (and matches the report)

* Board ↔ tree reconciliation exact: 89 complete + 2 quarantined + 5 deferred = 96; T2/T3 splits as claimed.
* Pins honored: `<java.version>21</java.version>`, parent `3.5.16` resolves offline (re-pin worked).
* Seed business rules are genuinely implemented where they exist: inclusive HR/Power/Cadence boundaries
  with the seed's exact literals, swim pace strictly `> 45`, 60 s device-clock reorder watermark,
  append-only revisions (`latestRevision+1`, 0 when none) with unique-packet dedup, `VALIDATION_FAILED`
  tag without dropping the payload, ECS file logging + rolling policy, env-placeholder Postgres url,
  health+metrics exposure, reactive controller (202 + `Mono` end-to-end, no `block()` found in main).
* Migrations ↔ repository SQL agree column-for-column (`value` hazard already handled in the R2DBC test
  harness); `backup_telemetry_sample_revision.sh` is executable.
* 154/166 frozen tests pass on the unblocked copy — the storm fixes really did converge the rest of the
  board; yesterday's "clean convergence" economics claim holds.

## Shortest path to a green, deliverable tree

1. **Re-emit T2-014's contract** (intent prose must follow the table: instance + **public** constructor;
   or the architect picks the static-port option and then the frozen pair + DI site move to it — one
   coherent decision, not two shapes).
2. Operator option 2 from yesterday, extended: disclosed edit `DefaultIngestTelemetryUseCaseTest:79`
   to the instance form **+** relax the private constructor in the corrected class; then
   `--retry T2-020` (T3-020 unblocks; scratch proves 8/8 pass with this unblock).
3. Drain the queue: T2-002 (second yml doc + datasource/flyway decision), T2-029 (delegate to the
   injected context), then T3 mirrors.
4. **Assembly fix (currently owned by nobody)**: `scanBasePackages = "com.pulsestream.telemetry"` on
   the entry point + a `CorrelationContext` `@Bean`; re-run the boot gate.
5. Commit the tree. 20 untracked files is one `git clean -fd` away from zero.

## Process-level gaps this inspection exposes (candidates for the gauntlet/skills, not this tree)

* **A main-source consumer of a quarantined unit survives rollback** → finalize/quarantine must reopen
  or strip assembly files that import a rolled-back artifact (extension of fix #12 to non-unit-owned
  files). F1.
* **Intent prose vs ast_hints table coherence check at plan time** — "Private constructor" shipped
  alongside instance-method bindings in the same task (F2; the same defect class today's rules were
  supposed to kill, only half-pinned: writers refuse statics, nobody refuses constructor prose drift).
* **Boot gate must assert bean presence, not context-load success** — `contextLoads` over an
  un-scannable package root is 1/1 green with zero application inside (F3/F4; a bean-inventory probe
  like the scratch one, per stack, would have caught both).
* **Supervision reports should re-run the build on the final tree**, not on the last gate transcript —
  both F1 and the "tree moved afterwards" footnote disappear if the exit summary includes one
  `test-compile` on the delivered directory.

## Success proportions — how close to perfect (measured 2026-11-13)

Two different numbers answer "how close", and the gap between them is the entire point:

| lens | measurement | % of perfect |
|---|---|---|
| A. As delivered (ship today) | `test-compile` fails → 0 of 166 frozen tests execute | **0%** |
| B. Board statistic (yesterday's claim) | 89/96 tasks complete | 92.7% |
| C. Latent quality (2 contract fixes applied, nothing else) | 154/166 frozen tests pass | 92.8% |
| D. Full remedy chain (6 edits, proved in scratch) | **167/167** (166 frozen + bean inventory) green, BUILD SUCCESS | **100%** |

Per-dimension latent scores (lens C, the honest reading of the implementation itself):

| dimension | score | note |
|---|---|---|
| Seed business rules (validation, reorder, backpressure, event sourcing) | 4/4 | implemented and behavior-tested green |
| Frozen contract tests | 154/166 (92.8%) | red = only the 2 never-produced units (F5, F6) |
| Production artifacts | 29/30 files exist | `DefaultIngestTelemetryUseCase` missing (~128 lines) |
| Code volume | 743/877+ main LOC (≈ 85%) | remainder = missing class + 5 micro-edits |
| Runtime wiring (composition root) | 0/2 | scan gap (F3) + missing bean (F4) — both invisible to every gate |
| Board bookkeeping | 89/96 exact | but "completed" ≠ "the application runs" |

**Headline: ~93%** on the board/test lenses — and the distance to perfect is now *empirically bounded*,
not estimated: exactly **6 edits across 5 files + 1 plan decision** (~145 lines of production code,
mostly the one missing class), and the scratch copy proves that chain converges to 167/167 with the
full bean inventory green. Nothing else fails. There are no hidden third-order defects behind these
six: once compiled, the other 154 behaviors were never red.

The uncomfortable corollary: yesterday's run was already at "perfect minus a bounded 7%", but three
of the six fixes (F3, F4, F1's surviving import) lie **outside any task's ownership** — no unit in
the DAG would ever have caught them. The 93% is real engineering convergence; the missing 7% is
entirely a blind spot in the *gates*, not in the coder loop.

## Implementation record — fixes landed 2026-11-13 (verified, pinned, generic)

Pre-check of "did yesterday fix any of this?" (read from the code, not the report):

| defect | already guarded by yesterday's fixes? | verdict |
|---|---|---|
| F1 quarantine rollback holes main sources | fix #12 (`_reopen_contract_regression` + A25/A26) exists, but it only fires on a LIVE verdict and only for unit-owned files; after the LAST verdict nothing scans, and the terminal exits re-verify nothing | HALF — the exact exit shape slipped through |
| F2 prose-vs-table shape contradiction | fix #13 declared "prose is not a binding" (write-time), and the writer refuses static smuggling (W11-W15); NO plan-time refusal of a contradictory pair | NOT guarded |
| F3 composition root outside the code packages | assembly probe knew entry UNIQUENESS + launchability only | NOT guarded |
| F4 injected type with no provider | nothing anywhere owned the closure | NOT guarded |
| F5/F9 config-surface / egress gaps | skill rule (b) scheduled the config UNIT, not its document surface or stream consumers | NOT guarded |

Engine changes (all stack-neutral; framework vocabulary lives in STACKS data rows and skills):

1. `tasks.py` — two emit-refused plan rules (seed-002 rerun F2):
   **(e) prose-vs-own-table**: intent asserting an unconstructible shape ("private constructor /
   utility class / non-instantiable") while the same table binds INSTANCE members is REFUSED;
   **(f) prose-vs-producer-table**: any staged intent calling a pinned producer's member in static
   form (`Type.member(`) where that producer's table binds it instance is REFUSED. Corpus replay
   against the REAL board: fires on T1-014/T2-014 (the pair that froze T2-020), on T1-020's own
   static prose, on T1-029/T2-029, and surfaces a latent inconsistency in the
   `TelemetryEvent.windowEmitted` table (static factory bound without `static`). Zero false
   positives on framework calls (`Mono.just`, `List.of` are not project exports).
2. `tdd_engine.py` — quarantine rollback can no longer hole the delivered tree silently (F1):
   after a destructive revert, `_dangling_main_consumers` scans NON-test sources for references to
   the rolled-back product; OWNED consumers are REOPENED to their owners (their next gate defers at
   zero bill against the quarantined symbol — the queue stops lying about being empty), UNOWNED
   (assembly-era) consumers are NAMED in the log AND appended to the quarantine record the operator
   reads (`[DANGLING-CONSUMERS: ...]`). Wired into both revert sites (own-unit quarantine + cascade).
3. `assembly.py` — the hollow-boot guard (F3/F4): the java STACKS row now carries `package_regex`
   + `coverage_markers` as DATA, and `_coverage_problems` refuses any tree where the composition
   root's package cannot see the main-source packages and no scan coverage is declared. Stacks
   without the row keys (explicit module graphs) skip the rule. The gate that booted green over an
   EMPTY context now cannot close.
4. `pipeline.py` — `_terminal_tree_report()`: every terminal exit (`[exhausted]`, stuck-fatal,
   blocked) re-runs the deterministic stage-4 gate on the DELIVERED bytes and prints
   `[tree   ] <slug>: GREEN|RED` before returning. A cached 16:17 boot verdict can no longer be
   reported as the final state — the supervision-misreport root cause dies with it.

Skill/agent updates (the architect half; generic wording, stack detail only in tech-stack skills):

* `task-decomposition-dag` + `agent-architect` (both mirrors): plan validity extended with (e)
  prose-must-not-fight-the-table, (f) provider closure (every injected type has a named provider
  duty), (g) composition-root visibility, (h) config-surface completeness (multi-document + the
  enabled-reader-needs-its-datasource rule, F5), (i) stream egress consumer/boundary (F9).
* `assembly-framework/java-springboot`: "what the smoke proves" now states green proves NOTHING
  unless the entry sees the code (F3); fix menu item 0 = prove the context contains the application
  + provider closure; new failure-map line for green-boot/404; constraints forbid completing from a
  cached verdict and name stale `target/`.
* `tech-stack/java-springboot3`: the entry point belongs in the strategy base package (Initializr
  default is never a decision); an injected collaborator needs exactly one named provider; flyway
  enabled must share its document with a datasource URL; multi-document test profile rule.

Gauntlet: 9 new pins (G21/G22 prose-vs-table refusal + coherent acceptance, G23/G24 cross-unit
static-shape refusal + instance prose acceptance, A27/A28 rollback names + reopens the consumer,
S1/S2/S3 coverage refusal / scanBasePackages accepted / under-root accepted).
Full suites: **46/46 + 91/91, all green** after every change.

Deliberate non-changes: the current BOARD (89/96, T2-020 quarantined) was left untouched — these
fixes govern the NEXT drain; today's tree is still remediated by the 6-step chain in the previous
section. A relaunch on the corrected plan would refuse the F2 pair at emit, require the F4 provider
duty in the wiring unit, gate the F3 scan structurally, name any F1-style rollback hole in the
quarantine record, and exit only over a freshly re-verified tree.

---

# PART II — Re-inspection: the regenerated project (fresh drain 2026-11-13 13:06–13:56)

Tree: `projects/high-performance-time-series-telemetry-ingestion-pipeline/services/telemetry-ingestion-processing`
(12 main sources / 288 LOC, 13 test classes / 60 tests, 42 board tasks, zero quarantined at exit).

## Verdict up front — the inversion

| lens | yesterday's tree (Part I) | today's tree |
|---|---|---|
| As delivered: compiles | 0% (dangling import) | **100%** — `[verify] passes typecheck` at 14:01 |
| As delivered: boots with real beans | vacuous (empty context) | **100%** — entry `com.blackboard.telemetry` bare `@SpringBootApplication`, ancestor of every package; stereotype DI graph constructs |
| Frozen contract | 154/166 latent, 0 runnable as shipped | **60/60, 0 failures, 0 errors** (fresh `mvn -o test`) |
| Board | 89/96 with an impossible tail | **42/42, zero quarantined, no frozen-test repair needed** |
| Engine-gate classes F1–F5 | all open | **all closed** (table below) |
| **Seed business rules actually implemented** | **4/4 (with wiring tail broken)** | **≈1.5/4 — the plan itself dropped them** |

**The headline finding of the new project is not a wiring defect: it is a COMPLETENESS defect that
no gate can see.** Today's machinery is perfect — and precisely because the validators all compare
plan↔board, plan↔plan and tree↔runtime, nothing compares **plan↔domain-slice**: the architect
decomposed 12 units instead of 30, the drain converged in 50 minutes with zero quarantines, and the
resulting tree omits the seed's central capabilities. Fastest run ever partly because the scope
shrank to what the plan asks for — and the plan forgot what the description demands.

## Machinery verification — every Part-I defect class, re-tested on the new tree

| old defect | status in the new tree | evidence |
|---|---|---|
| F1 quarantine rollback holes main sources | **CLOSED** | tree compiles clean; no dangling imports anywhere; both rollback paths and the zombie-record supersede are pinned (A27/A28, U1–U3) |
| F2 prose-vs-table impossible pair | **CLOSED** | validator replay over the LIVE plan: 0 hits; the plan never contains a utility-class/instance contradiction; correlation is ONE middleware unit (the skill's own wording) |
| F3 composition root outside the scan | **CLOSED, hardened twice** | entry at the base package (bare annotation); the gate gained the NON-WAIVABLE slice-discovery half (S4/S5) after the 13:45 live lesson |
| F4 injected type with no provider | **CLOSED** | every injected collaborator self-registers (@Service/@Repository/@Component/@RestController); boot constructs the whole graph |
| F5 single-document config | **CLOSED** | 2-document `application.yml`: base + `test` profile (`r2dbc:h2…;NON_KEYWORDS=VALUE`, `flyway.enabled: false`); the database step even QUOTED `"value"` in V1 — the schema-level fix of yesterday's keyword hazard |
| F6/F7 git hygiene | **OPEN (unchanged)** | tracked files are still run-1's 45; today's entire output is collapsed untracked directories; one `git clean -fdx projects/` erases the run again |
| F8 scaffold residue | **PARTIAL** | empty `logs/` + `HELP.md` remain; `target/` regenerated (build artifacts) |
| F9 zero-subscriber stream port | **N/A — and worse** | this plan never scheduled a broadcast port at all (see N5/N6) |

## New findings (N-series) — plan↔seed completeness

Traceability of the seed's four numbered business rules through the pipeline:
domain slice (discovery) → execution strategy (phase 1) → tasks (phase 2) → delivered code.

| rule | domain slice | strategy | tasks | code |
|---|---|---|---|---|
| R1 Boundary validation (HR 30–240, Power 0–2500, Cadence 0–220, swim >45) | **verbatim, with literals** | named once, NO literals, no metric taxonomy | **NO TASK** | `isValid()` = well-formedness only (`isBlank`/`isFinite`); `VALIDATION_FAILED` never fires for out-of-range values |
| R2 60-second backfill re-index | verbatim | 3 mentions | T2-007 intent has "reorder" | `BackfillReorderer.reorder(List)` = bare sort: **not a bean, zero callers in main**, no window semantics; `telemetry.backfill.window-seconds: 60` has NO reader |
| R3 Non-blocking WITH backpressure (burst of thousands, bounded buffers) | verbatim | "bounded buffers with backpressure" promised | **NO TASK** | reactive ✔ (0 blocking calls) but `collectList()` = unbounded buffering; `telemetry.buffer.capacity: 1024` has NO reader; no overflow posture exists |
| R4 Append-only + corrective revisions | verbatim | 12 mentions | intents mention "revision" | schema+store support revisions ✔ (PK includes revision, CK ≥ 0), but ingest HARDCODES `revision=1L`: corrections are unreachable and a second sample at the same (device, metric, tDevice) hits the PK and **fails the whole request** |

- **N1 — CRITICAL (product): the domain's defining invariant is absent.** No `MetricKind` taxonomy,
  no per-metric ranges, no boundary keys in the config, no frozen test mentioning 240/2500/220/45
  (grep: zero hits across the whole tree). Yesterday's tree implemented all of it. Nothing failed,
  because every gate was answering "does the tree match the plan?", and the plan never asked.
- **N2 — HIGH: the reconciliation context is a facade.** One green-tested class no one calls, not
  even registered — bounded contexts whose product nobody consumes pass every gate (the F4 rule
  closed type-provision closure; CAPABILITY consumption is not a plan concept yet).
- **N3 — HIGH: revision degeneration + duplicate-key failure** (R4 row above). Packet dedup
  (`existsByPacketId`-equivalent) also absent: no packet identity exists anywhere in the model.
- **N4 — HIGH (new defect family): correlation has TWO independent sources of truth.**
  `CorrelationIdWebFilter` adopts/mints a requestId, sets the response header, and writes the
  Reactor `contextWrite` — which **zero call sites read** (grep `deferContextual`: 0 outside the
  filter). The controller re-reads the header and mints its OWN UUID when absent. Header-less
  request ⇒ response `X-Request-Id` = filter-UUID-A, audit `correlationId` = controller-UUID-B:
  the audit trail cannot join to the response for every unheadered packet. Each unit's frozen test
  passes in isolation; the cross-unit contract lives in prose only.
- **N5 — MEDIUM: dangling operational values (rule-(b)'s mirror).** The config document carries
  `window-seconds` and `buffer.capacity` but no binder reads either. Rule (b) refuses plans that
  speak of externalized values without a CONFIG UNIT; nothing refuses the inverse — a config unit
  whose values no consuming unit binds. Silent fiction: operators would tune knobs that do nothing.
- **N6 — MEDIUM: the promised egress does not exist.** The strategy explicitly promised "an
  in-process reactive stream (Flux) of TelemetrySampleValidated/ValidationFailed events via a
  published port" — no such port was scheduled; the event surface is pull-only
  (`findLatestInRange`). The seed's "broadcasting to downstream event streams" is unimplemented
  (rule (i) was new this morning; the strategy→tasks drop happened at the seam rule (i) does not
  yet cover: promised port → scheduled unit).
- **N7 — LOW: migration duplication.** `db/migrations/` (database step's canonical folder) plus the
  assembly-era copy under `src/main/resources/db/migration/`; the base yml reads only the classpath
  pair; `db/migrations/flyway-config.yml` + `backup-recovery.md` are now orphaned (no import
  references them). Two sources of DDL truth drift the moment anyone edits one.
- **N8 — LOW: slice tests re-type their DDL inline** (`R2dbcTelemetryEventStoreTest` embeds the
  CREATE TABLE text) — the pattern the tech-stack skill forbids ("schema from the real migration
  files, never retyped DDL"); currently byte-consistent with V1, drift-prone by construction.
- **N9 — LOW: unbounded metric tag.** `telemetry.samples.validated{metric=<free string>}` counts
  the CLIENT-SUPPLIED metric string as a tag — with no taxonomy (N1), that is unbounded tag
  cardinality, the exact Micrometer prohibition. Consequence of N1.

## Success proportions of the new implementation

| lens | measurement | % |
|---|---|---|
| Board (plan execution) | 42/42, zero quarantined, zero operator repairs | **100%** |
| Delivered as shipped | compiles, boots real context, 60/60 frozen tests | **100% of the plan** |
| Gate-class defects (F1–F5) | 0 recurrences | **100%** |
| **Seed obligation coverage** | R1 0%, R2 40% (dead sort), R3 50% (non-blocking but unbounded), R4 55% (append+schema, no corrective path) | **≈36%** |
| Ubiquitous language realized | 2.5 of 6 pinned terms functional (Sample ✔, timestamps ✔, Ingress Packet ~½ (no identity), Reorder Window / Backpressure / Sensor Boundary ✘) | **≈42%** |
| Strategy-promised runtime surfaces | audit ✔, correlation ½ (N4), metrics ½ (N9), ECS file sink ✔, published event port ✘, bounded buffers ✘ | **≈58%** |

**Headline: the machinery is at 100% and the product is at roughly a third of the seed's intent —
the exact inverse of yesterday (product ~93%, machinery with a broken 7%).** Yesterday's tree, once
the 6-edit chain was applied, delivered the seed's substance; today's tree needs no chain and
delivers far less. The distance to "perfect" today is not a wiring patch: it is a follow-up drain
carrying ~6 new units (validator+taxonomy+boundary keys, reorderer-as-bean with window binding and
watermark semantics, packet identity + dedup + revision increment, broadcast port with capacity and
overflow posture, correlation read via `deferContextual` as the single source, and the obligation
map below).

## Process-level root cause (named so it can be fixed next)

Every emit-time validator shipped so far compares artifacts to EACH OTHER (table↔prose, unit↔board,
tree↔runtime). None compares the **plan to the domain slice's invariants**. Discovery captured all
four rules verbatim into `blackboard/domain/domain-boundary-telemetry-ingestion-processing.json`;
the strategy weakened R1/R3 to abstractions; phase-2 tasks dropped R1/R3 entirely and shrank
R2/R4 to stubs; the drain then executed the shrunken plan flawlessly. Recommended fix (NOT yet
implemented — proposed for the next work session):

1. **Obligation matrix at emit**: the architect phase-2 draft must carry, per domain,
   `invariants: [{id, source (domain-slice quote), unit (task id)}]`; `tasks.plan_consistency`
   refuses any domain-slice `business_rules[]`/`invariants[]` entry not mapped to at least one
   task, and refuses a config key with no consuming unit (N5's inverse-binder rule).
2. **Cross-unit consumption rule** (N2/N4/N6 family): a unit's exported capability must be
   consumed by ≥1 other unit or be declared an explicit boundary duty — mirrors rule (f)'s
   provider closure, this time for CONSUMERS.
3. **Correlation single-source rule** (tester/coder skills): the entry adapter must read the
   request id from the Reactor context written by the correlation middleware, never re-mint —
   the class of bug per-unit gates structurally cannot see.
4. Commit the board's output: Part I's F7 warning repeated itself verbatim.

## What stayed GOOD (fair ledger)

Pins honoured again (Java 21, Boot 3.5.16 re-pin); the ndjson request binding pairs streamed types
with streamed bodies (the D2-class defect this morning's rule (c) prevents — the new plan got it
right by construction); audit trail complete (actor/action/outcome/timestamp/correlation); ECS file
logging + rolling policy; env-placeholder r2dbc URL; quoted `"value"` in the canonical schema;
zero blocking calls in the request path; clean feature-per-context packaging; and — the real prize
of the day — **no unit ever died of tooling**: every red was adjudicated, budgeted, and the two
tool-caused ones (N/A here; fixed live: T2-001 config, slice units) closed at zero sessions after
their root fixes.
