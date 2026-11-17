# Project inspection — 2026-11-17 (seed 002, fourth drain + its delivered artifact)

Method: READ-ONLY re-analysis of the delivered artifact after the drain closed
(sources, tests, config, migrations, board records, engine logs), plus deterministic
zero-token verifications (full offline suite, jar boot from a foreign cwd, live curl
of the HTTP contract, framework bytecode inspection). The drain itself is recorded
in `RUN-SUPERVISION-2026-11-17.md`; this file is the artifact report.
Clarification for the record: `PROJECT-INSPECTION-2026-11-16.md` was last edited at
11:40 (previous session's post-drain addendum) BEFORE this session began at 11:47 —
it was not touched by today's work; today's findings live here.

## 1. Verdict up front

| dimension | state |
|---|---|
| board | **63/63** (T0 5, T1 19, T2 19, T3 19, T4 1), queue 0, quarantined 0 ✔ |
| authoritative suite | **131 tests, 20 classes, 0 failures, 0 errors** — fresh offline `./mvnw -o test` + memoized terminal-suite verdict for the final fingerprint ✔ |
| boot | GREEN — assembly ran the e2e class as the boot gate (8/8); re-proven today: repackaged jar boots from `/tmp` (foreign cwd), both migrations applied from the CLASSPATH, live curls answered 202/400/202 with the contract bodies ✔ |
| assembly gate | `assembly.detect` = **zero problems** on the delivered tree ✔ |
| seed fidelity | 4 boundaries VERBATIM (30–240 / 0–2500 / 0–220 / >45 exclusive), `VALIDATION_FAILED` keeps the payload, 60 s window re-indexing by `t_device` is LIVE in the request path, append-only revisions honored — all proven by the artifact's own tests AND today's live probe ✔ |
| shape of the day | the drain died TWICE and was healed twice; every new failure class now dies EARLIER than it did yesterday — plan-shape at emit, scaffold-shape at a container check, fixture-shape at the tester skill, gate-vs-contract at a test-witnessed exemption |

## 2. Economics

| metric | value |
|---|---|
| billed sessions (whole day) | **56** for 63 units (~1.0/unit, repair cycles included) |
| tokens | **7.43 M in / 0.22 M out**; ~24.8 K input/turn |
| over-budget sessions | 4 — ALL plan-phase (architect 19/12 and 16/12 calls, database 16/14, first-draft architect) |
| largest single session | 537 K (doomed first architect draft); accepted re-decomposition 502 K |
| wave sessions | tester batches 8/19 calls, coder batches 8–11/46 — no overruns |
| repair billing | every tooling/plan-caused red closed at ZERO billed sessions after its root fix (`restored re-verification: green, no session billed` ×N; terminal-gate reopen→owner→restore cycle billed nothing) |

The flagged burn is confirmed, bounded and attributed: the plan-phase transcript
(537 K/502 K sessions) exceeds its call budget via scope-escape calls the prompts
already ban (audited: `skills_folder_listing` ×4, `board_bulk_read` ×16,
`agent_scratch` ×22) with the hard-kill watchdog bounding every case; the remaining
~340 K of waste was the fatal-draft itself, which the import-closure guard stopped
after 7 sessions instead of the ~100 a full drain would have burned.

## 3. The artifact — what is actually proven

**Structure**: 18 production classes / 595 LOC under `com.pulsestream.telemetry`
(intake / validation / reordering / eventlog / shared-observability / shared-config),
composition root at the ancestor base package, 20 test classes / 91 methods (131
runtime including the 28 expanded config parameterizations).

| rule (from the seed) | delivered mechanism | proof on the board / live |
|---|---|---|
| boundary validation, invalid kept | `ValidationService.isValid` switch over the four bounded metrics, config-bound bounds; `default -> true` for the seed's range-less metrics | `ValidationServiceTest` 25 cases incl. exclusive-45 swim-pace edge; live 202 with `VALIDATION_FAILED` row kept |
| reordering by `t_device`, 60 s window | `PipelineConfiguration.telemetryPipeline` (line 81): `intake → validate → buffer(window) → reorderWindow → append`; stable sort BY DEVICE CLOCK (`ReorderingService.BY_DEVICE_TIME`), never `t_ingress` | `ReorderingServiceTest` 7 cases incl. backfill/beyond-window counting; e2e durable rows arrive in device order |
| append-only + corrections append revisions | `R2dbcEventLogRepository.append` (lines 33–35): `MAX+1`, INSERT-only, `RECORD`(1)/`REVISION`(>1); earlier rows untouched | `R2dbcEventLogRepositoryTest` `secondSampleSameKey_insertsRevisionTwoAndKeepsFirstRowUnchanged` + e2e `repeatedPost_appendsSecondRevisionRow` |
| non-blocking ingestion + backpressure | `Sinks.many().multicast().onBackpressureBuffer(capacity, false)` (`IntakeService:26`), `tryEmitNext` with counted overflow (`:41–44`), zero blocking in the request path | `IntakeServiceTest` 8 cases; overflow counted `telemetry.pipeline.dropped{stage=intake}` |
| correlation | `CorrelationWebFilter` adopts/generates `X-Request-Id`, echoes it, `contextWrite("requestId")`; carried as the explicit `correlation_id` audit field and log kv; handler reads it via `deferContextual` (`TelemetryIngestController:54`) | `CorrelationWebFilterTest` + e2e `requestId_isWrittenAsAuditCorrelationId`; live echo header confirmed |
| observability floor | 8 step logs claimed across units; 6 meters; every failure/drop outcome paired with `telemetry.pipeline.dropped{stage}` or the outcome-tagged counters (`uncounted_failures: none` posture) | ECS file log from the live boot showed `intake.packet.received / validation.* / reordering.window.flushed / eventlog.*` with `correlationId`; `/actuator/metrics` answered tagged counts |

**Duplicate posture (planned, not accidental)**: the strategy segment states *"Delivery
posture: at-most-once inbound (no dedup identity); retries from devices may produce
duplicate Event Revisions and consumers must be idempotent"* — the value axis of rule
(s) is therefore resolved as include-everything-at-the-store, max-revision-read at the
consumer; the README of the artifact carries it as an operator decision line.

## 4. The factory on live fire — where each of today's classes now dies

| # | class of defect (what ALMOST shipped / did burn) | new front that now stops it | pinned |
|---|---|---|---|
| 1 | stage-1 TEST tasks emitted on production paths (whole plan, 19/19) | emit rule **(w)**: test-path vs implementation-path collision refused, board-wide | Z1/Z1b/Z1c — live-fire on the real draft: refused 19/19, zero queued |
| 2 | frozen fixtures creating the H2 substitute with JDBC credentials and reading it bare ([28000]), and decoding `MAX()` as `Long.class` (codec cannot) | tester-skill laws: creator/reader share credentials; aggregates read as `Number` | P5 (laws pinned in `java-junit5`) |
| 3 | composition root nested under the artifact slug — smoke passes, siblings' `@SpringBootTest` die | container-skill **check 7** placement relocation (sanctioned, verified); stack-skill law | P7 |
| 4 | "no scanning-registration annotation, registered only by the wiring factory" — WebFlux `isHandler` accepts ONLY `@Controller` (bytecode-verified): green boot, permanent 404 | emit rule **(x)**, language-gated, factory-built FILTERs exempt | Z2/Z2b/Z2c |
| 5 | packaged migration dir empty: copy duty unschedulable at database-emit time (its target file has no owner yet) | database skill outputs DIRECTLY at the runtime-loaded dir; engine's `_migration_files` accepts it | P6 |
| 6 | delivered-time probe ordered the assembler to rewrite a value the frozen test pins — probe-vs-contract collision, the (r)/N8 family's VALUE twin | test-witnessed exemption in `_base_config_problems` + assembly menu item 7 exception + terminal suite gate (which already caught/fixed it live end-to-end) | X5d/X5e |

Gauntlet after all of it: **engine 174/174, skill-scripts 57/57** (8 engine + 4
doc pins added today over the 166+53 baseline).

## 5. Residual findings (honest, none silent)

* **H1 — inert double registration**: `ValidationService` and `EventLogService` carry
  both `@Service` and a same-name factory `@Bean`; the scanned definition wins (Spring
  precedence), exactly one bean is effective (asserted by boot + runner tests) — but
  the (n) single-mechanism law is honored only by precedence, not by plan hygiene.
  Candidate emit refinement: flag a unit that names ANOTHER unit's product as its own
  stereotype while that product's intent also claims factory production.
* **H2 — scaffold intent vs strategy disagreement**: T0-001 demanded a
  `micrometer context-propagation` dependency; the strategy explicitly installs NO
  propagation mechanism ("correlation id on log lines is not promised") — the pom
  carries neither the dependency nor a `Hooks` call. Harmless (nothing imports it),
  but it is a promise/duty mismatch in the opposite direction of rule (t): (t) polices
  PROMISE→DUTY, not DUTY-without-PROMISE. Candidate: (t) twin check — a scaffold duty
  naming a mechanism token must appear (unnegated) in the strategy, or be dropped.
* **H3 — silent terminal error**: `telemetryPipeline.subscribe(record->{}, error->{})`
  swallows an unexpected pipeline death (not a tabled outcome, so the floor's
  `uncounted_failures: none` claim stands literally — but a crashed stream would show
  in no counter). Candidate meter: a pipeline-alive gauge owned by the wiring unit.
* **H4 — two-byte-set migrations**: the packaged `src/main/resources/db/migration`
  (runtime truth) and the frozen stage-0 authoring copy at `db/migrations/` were
  byte-identical at delivery (verified); the divergence guard the database skill
  demands is a duty nobody owns today — the next drain's corrected plan shape removes
  the second set by construction.
* **H5 — range-less metrics accepted unbounded** (`ground_contact_time`,
  `respiration`, …): the fidelity rule working as designed; one operator decision list
  (artifact README §Decision list) instead of invented bounds.
* **H6 — embedded-H2 boot default in the BASE config document** (no env required):
  pinned by `ApplicationYmlConfigTest` verbatim, assembly-probe-exempt (X5d), and the
  README documents the production override surface; the deployment contract stays
  operator-visible, not fiction.
* **H7 — the plan-phase scope-escape burn** (§2): watchdog-bounded, audit-visible,
  not mechanically closeable without enlarging the fixed prompt (which would raise
  every session's per-turn floor — the anti-economics). The honest lever remains the
  per-turn transcript size of the architect prompt itself, unchanged since yesterday.

## 6. Bottom line

Yesterday's ceiling was "green board, green tree, silently missing integrations".
Today the artifact's integrations are PROVEN (request-path slice live in the pipeline,
real-schema persistence, counted-and-audited failures, portable packaged migrations),
and every one of today's four NEW failure classes — a whole-plan shape defect, two
fixture-physics laws, a scaffold placement rule and a framework-registration
impossibility — was caught, root-fixed at the tier where the fix is still cheap
(emit gate, container check, tester law, witnessed-exemption), live-fire-proven
against the artifact that produced it, and pinned (174+57). The drain's exit-lie
family also fired its first fully self-healing cycle: probe broke a contract, the
terminal suite gate named the OWNER, the owner restored it, zero sessions billed,
and the probe now cannot repeat the order.
