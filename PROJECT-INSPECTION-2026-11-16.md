# Project inspection / final evaluation — seed 002, 2026-11-16 drain

> **Scope note (updated 2026-11-16 evening).** PART I inspects the FIRST drain's
> tree (09:48–11:55, 71 units); PART II the SECOND drain's (13:54–15:33, 26 units).
> After the same-day gate fixes shipped, the operator wiped board and project a
> second time and the engine regenerated again. PART I and PART II are retained
> **verbatim as the historical record** — including the N1–N10 findings the rules
> (o)–(r) and the weaver fixes were built from. **PART III (below) inspects the
> CURRENT delivered artifact (third drain, 32 units, 258/258 green) and is the
> current truth about the delivered artifact.**

Object: the generated service at
`projects/high-performance-time-series-telemetry-ingestion-pipeline/services/telemetry-ingestion-processing`
(PulseStream Engine), board state, and delivered-tree logic, against
`seed/002_description.md`. Companion documents: `RUN-SUPERVISION-2026-11-16.md`
(the six root-cause fixes made DURING the drain — this document does not repeat them)
and the artifact guide `projects/…/README.md`.

Authorship disclosure. This run's product tree is NOT untouched: unlike the 11-13
inspection (project not modified), the operator repaired tooling-made-impossible
artifacts mid-run, all disclosed live and pinned in the gauntlet:
(a) the `interface`→`api` package rename across 12 task records, 4 frozen test files
(`src/test/java/com/pulsestream/telemetry/{intake,observability}/api/`), red/AST records
and payloads — Java reserved word planned as a package segment, unweavable and
uncompilable by any agent;
(b) `db/migrations/V1,V2` portability fixes (`TIMESTAMP WITH TIME ZONE`, quoted
`"value"`, semicolon-free COMMENT literals) — the slice tests execute these files
verbatim against plain H2;
(c) one source edit: removal of the out-of-contract constructor guard
(`TelemetrySample.java`) that the T3-005 evaluator added and its engine_diff hid,
breaking `SampleValidatorTest` (a peer's frozen contract);
(d) board-payload alignment for (b) (`T2-011` SQL quoting, `T2-005` body cleared).
Every repair was re-adjudicated by the engine's own gates — three closed at ZERO
billed sessions via the replay machinery.

Method: authoritative full-suite run + boot re-check + line-by-line source and
record attribution of every finding. `P` =
`services/telemetry-ingestion-processing/src/main/java/com/pulsestream/telemetry`.

---

# PART I — first drain (09:48–11:55): historical record

## 1. Verdict up front

| dimension | board claims | empirical state |
|---|---|---|
| completion | 71/71 tasks, queue 0, quarantined 0 | matches: T0 4, T1 22, T2 22, T3 22, T4 1 ✔ |
| build | typecheck green | `./mvnw -o test-compile` GREEN ✔ |
| suite | green terminal verdicts | **145/145, 0 failures, 0 errors** (fresh offline run) ✔ |
| boot | T4-001 green, re-checked by engine | GREEN, real context (entry `…telemetry_ingestion_processing.TelemetryIngestionProcessingApplication`, `scanBasePackages = "com.pulsestream.telemetry"` declares coverage of every package) ✔ |
| board-vs-tree lie class (11-12 / 11-13 PART I) | — | **eliminated**: the terminal suite gate caught both cross-stage regressions live and healed them ✔ |
| seed-rule coverage | 4 business rules planned | **3 of 4 live; the reordering rule is NOT wired** (F1) ✘ |
| deliverable | — | **runs and ingests correctly on the request path, but carries 6 logic/topology defects the per-unit gates structurally cannot see** (F1–F6) — see §3 |

The engine loop converged honestly. The artifact's problem class changed: no longer
"broken tree, lying board" but "green board, green tree, silently missing integrations".

## 2. Economics

| metric | value |
|---|---|
| billed sessions (whole day, all launches) | 78 for 71 units (~1.1/unit) |
| tokens | 9.48 M in / 249 K out; mean 22.4 K in/turn |
| over-budget sessions | 6 (worst: the doomed first architect 397 K — incident #1 in the supervision doc, since fixed + pinned) |
| tooling-caused reds closed at zero bill after root fixes | all of them (T2-003 config pair, T2-011/014 slices, T2-008 validator world-move, T4 final cycle) |
| comparison | 11-11: 51 units/80 tests/15 red · 11-12: 96 units/89 done/broken tree · 11-13: 42 units/60 green · **today: 71 units/145 green/0 broken** |

## 3. Findings — each proved, root-attributed

### F1 (critical) The backfill-reordering subsystem is orphaned in the live app
Evidence: `ReorderingService.accept()` and `.ordered()` have **zero callers** —
the only reference in production sources is the bean factory
(`P/shared/config/TelemetryWiringConfig.java:31-32`). The ingestion path is
`TelemetryController:28 → IngestTelemetryUseCase:45 → stream.publish → EventLogAppender`:
samples reach `telemetry_event_log` in ARRIVAL order. The seed's core rule
("out-of-order packets delayed up to a 60-second window must be dynamically
re-indexed chronologically by t_device") never executes; consequently dead in
runtime: the window reconciliation (`ReorderingService.java:67-81`), the
buffer-full backpressure (`:85`), the `telemetry.samples.backfilled{within_window}`
meter (`:77`) and 2 of the 5 promised step logs.
Root owner: **agent-architect** — T2-016's dependency table pins
`TelemetryEventStream` but never `ReorderingService`, and no wiring duty exists
between them; the decomposition made the context a tested island.
Engine blind spot (named, not fixed): the boot gate proves the bean GRAPH resolves;
nothing proves the DATA-FLOW TOPOLOGY. Every per-unit gate is structurally blind
here — the slice tests `new` the service directly.

### F2 (high) Burst = silent drop while the API lies `202 VALID`
Evidence: `TelemetryEventStream.publish()` returns `boolean`
(`P/eventlog/application/TelemetryEventStream.java:23`,
`tryEmitNext(...).isSuccess()`, bounded buffer `:14`);
`IngestTelemetryUseCase.java:45` **ignores the return value**. When the
`buffer-capacity`-bounded sink fills — the seed's "thousands of simultaneous
transmissions" — the revision is dropped and the caller still gets
`202 ACCEPTED` + `VALID` + SUCCESS-shaped audit. Violates the seed's
"without dropping the underlying payload" + backpressure guarantee.
Root: **plan-time** (the use-case contract text says "publish to TelemetryEventStream"
without an overflow duty) + **coder** (could not add handling the contract did not
name: the signature returns `Mono<ValidatedSample>` and the table offers no
overflow surface).

### F3 (high) The revision number contradicts itself across four units
Evidence: `EventRevision.FIRST_REVISION = 1` (`P/eventlog/domain/EventRevision.java:12,18`)
· `IngestTelemetryUseCase.java:45` publishes revision **0** (it calls `initial()`
then rebuilds the record discarding the factory's number) ·
`EventLogAppender.java:43` labels `kind = number > 1 ? "revision" : "record"` —
under 0-based publishing the FIRST correction (1) is metered as "record" ·
`ReorderingService.java:67-68` builds a correction by `revisionNumber()+1` of the
INCOMING sample — two independent corrections for one `(device_id, t_device)` both
produce 1 → the unique key collides → `R2dbcEventLogRepository` swallows the
violation into `false` → **`EventLogAppender.java:44-46` returns without audit,
without metric, without error** (the `inserted == false` short-circuit skips the
audit branch entirely). Silent data loss at the append-only log — the exact
auditability the seed's event-sourcing rule promises.
Root: **agent-architect** — a plan-wide constant (first revision number) is spelled
independently in four contracts; there is no plan mechanism pinning shared NUMBERS
(only shared SHAPES), and no duty "compute next revision from the log".

### F4 (high) The delivered domain speaks the wrong ubiquitous language
Evidence: seed names heart rate (30–240 BPM), power (0–2500 W), cadence (0–220 RPM),
swim pace (>45 s/100 m), ground contact, respiration, stroke; the implementation's
`MetricKind` enum is `TEMPERATURE, HUMIDITY, PRESSURE`
(`P/intake/domain/MetricKind.java:5`) with industrial bounds in
`application.yml` (`-90..60 / 0..100 / 300..1100`). None of the seed's boundaries are
enforced; the one-sided pace rule is absent; the failure flag is `INVALID`
(`ValidationStatus.java:5`) where the seed's language is `VALIDATION_FAILED`.
An athletic payload cannot even enter: `MetricKind.valueOf("HEART_RATE")` throws
`IllegalArgumentException` inside `TelemetrySampleRequest.toDomain`
(`P/intake/api/TelemetrySampleRequest.java:12`) → HTTP 500, and the request is
DROPPED — the seed's "tag, do not drop" rule, broken at the API boundary itself.
Root: **domain-boundary discovery** invented the wrong metric family; every
downstream gate checks internal consistency, never fidelity to the seed's verbatim
terms, so the wrong world propagated coherently through all 71 records (145 green
tests included). Secondary: **F4b** — the bean-validation annotations (`@NotBlank`,
`@NotNull`, same file) are never enforced: `TelemetryController.java:27` has no
`@Valid` — a dead validation surface the plan's (h)-style completeness rules do not
reach.

### F5 (medium) 3 of 5 promised step logs never fire at runtime
Evidence: "record / revision appended" is claimed VERBATIM by T2-021's
`observability.step_logs`, but `EventLogAppender` contains **no logger at all**;
its frozen test asserts only the counters (`EventLogAppenderTest.java:54,63,73`) —
the promise "its coder logs it, its tester asserts it" silently degraded to the
metric side. The other two missing ("sample buffered in reorder window",
"backfill reconciled") are alive code but unreachable per F1.
Root: **agent-tester/plan** — the emit gate validates claim COVERAGE
(exactly-one-owner) but the paired test need not reference the claimed string.

### F6 (medium) Two migration sources, already diverged
Evidence: `db/migrations/` (what the H2 slice tests execute — carries today's
portability fixes: quoted `"value"`, `;`-free COMMENT literals) vs
`src/main/resources/db/migration/` (what Flyway applies at runtime — still the
pre-fix `value DOUBLE PRECISION` and `;`-in-literal COMMENTs; verified by diff).
The schema deployed ≠ the schema tested. Survives today only because H2's
`NON_KEYWORDS=VALUE` and Flyway's literal-aware splitter forgive both.
Root: **stage-0 scaffold** duplicated the scripts; no "one canonical location +
scheduled copy duty" rule.

### F7 (low-medium) Correlation via MDC is thread-hop fragile
Evidence: `CorrelationWebFilter.java:25-27` puts/removes MDC around `chain.filter`
without a Reactor context-propagation registration; after any event-loop hop the
step-log lines (`sample validated`, `validation failed`,
`IngressPacketReceived …`) may lose `requestId` in the ECS file output. The AUDIT
path is correct — it reads the Reactor context
(`IngestTelemetryUseCase.java:46 getOrDefault("requestId", …)`) — the LOG surface
is the weak half of the correlation story.

### F8 (low) Structural noise
* `CorrelationWebFilter` declared TWICE: `@Component` (`:11`) + `@Bean`
  (`TelemetryWiringConfig.java:41`) — the scanned definition wins, the @Bean is a
  misleading corpse.
* `EventLogAppender.java:33` — the stream subscription ends in bare `.subscribe()`:
  if the audit write inside `onErrorResume` itself fails, the whole append pipeline
  terminates and the event log stops silently for the process lifetime.
* `TelemetryEventStream.events()` and `EventLogRepository.findHistory()` are
  internal-only: the seed's "broadcasting to downstream event streams" has no
  external surface (SSE/WebSocket/producer) and history has no read endpoint —
  defensible if declared an out-of-process boundary, which the plan never named.
* scaffold leftovers in the tree: `HELP.md`, committed `target/`.
* config-fiction residual (already logged in the run supervision): one env var
  (`TELEMETRY_DB_URL`) feeds both the `r2dbc:` and the `jdbc:` Flyway URL because
  the FROZEN `ApplicationConfigTest:43` substring contract forces it — a plan-level
  contract the engine correctly refused to break (the evaluator recorded the finding
  without touching the pinned surface: model behavior).

## 4. What stayed GOOD (fair ledger)

* **The exit-lie class died this run.** The terminal suite gate (born from today's
  incident #6) caught, live, the cross-stage regressions the old engine would have
  shipped: an evaluator's record guard and the assembler's config rewrite were named,
  reopened and healed (the validator world-move closed at zero bill; the revision
  regression healed through its own owner) — final board == final tree truth
  (71/71 == 145/145).
* Genuinely non-blocking request path (zero `block()`/sleep in main sources), bounded
  buffers on both reactive edges, backpressure-aware sinks (modulo F2's ignored signal).
* Append-only schema with the right UNIQUE key and revisions, audit trail complete
  (actor/action/outcome/timestamp/correlation), ECS file logging + rolling policy,
  metrics named with bounded tags, H2 fallback keeps dev boot honest.
* Pins honoured end to end: Java 21, Boot 3.5.16 (generator re-pin path exercised),
  WebFlux/R2DBC/Flyway; clean feature-per-context packaging after the `interface`→`api`
  rename; reserved-word, phase-order and silent-`-q` gates now ship with pins
  (gauntlet 48 + 123 checks, was 48 + 109 at day start).
* Economics: ~1.1 session/unit for 71 units including six incident stops — vs 1.5+
  on the 96-unit 11-12 run; every tool-caused red closed at zero bill after its fix.

## 5. Recommendations for the next round (plan-time, in priority order)

**Update 2026-11-16 (later the same day): items 1, 2, 3, 4, 6 and 7 SHIPPED as
skill rules; item 5 and the mechanical emit-gates for the rest are the open tail.**

1. **Consumer-closure rule** (mirror of provider closure (f)): every application
   service whose intent implements a seed business RULE must be named in ≥1 other
   unit's `dependsOn` or declare an explicit entry-point wiring duty — kills F1.
   → SHIPPED: `task-decomposition-dag` rule **(k)** + architect profile.
2. **Shared-constants table**: numbers used by ≥2 units (revision origin, header
   names, meter names) get ONE pinned owner unit; contracts cite it — kills F3's
   four spellings.
   → SHIPPED: rule **(l)** (single owning unit for literals + DISTINCT config keys
   per URL-form reader; the `java-springboot3` Flyway paragraph — the literal source
   of the "same env placeholder" collision — rewritten to demand separate
   `${X_JDBC_URL}`/`${X_R2DBC_URL}` keys).
3. **Backpressure-signal duty**: a port method returning a success signal requires
   a named consumer duty for the false case — kills F2.
   → SHIPPED: rule **(m)** (both branches contracted on every consumer, paired test
   covers each).
4. **Seed-language fidelity check** at discovery validation: entities/metrics/ranges
   named VERBATIM in the seed must appear in the slice's ubiquitous language (or in a
   disclosed `assumptions[]`) — kills F4-class drift.
   → SHIPPED: `domain-boundary-discovery` Validate step extended (verbatim fidelity
   clause; deviations only as named assumptions).
5. **Step-log assertion pairing**: a unit claiming a step log must have its paired
   stage-1 test reference the claim string — kills F5.
   → OPEN: guidance already exists in the skill text ("that unit's tester asserts
   the captured event"); the machine-check (stage-1 intent must contain the claimed
   string, refuse otherwise) is an emit-validator change needing gauntlet pins.
6. **Single-source migration rule**: one canonical directory + a scheduled copy duty
   for the runtime location — kills F6.
   → SHIPPED: `concrete-database-migration` handoff + `java-springboot3` Flyway
   paragraph (canonical dir; any copy is a named duty of one unit; verification
   fails on divergence).
7. Minor: ban duplicate bean declaration styles (skill line for the wiring unit);
   require `@Valid` pairing when bean-validation annotations are tabled.
   → SHIPPED: rule **(n)** (registration mechanism XOR, never both; declared DTO
   validation must name its activation in the entry unit + a boundary-rejection
   test). Bonus: `java-springboot3` now carries the reactive-MDC truth (F7) -
   context propagation must be a planned duty; bare `MDC.put` in a filter is
   explicitly named as the illusion-of-correlation trap.

Skill rules (k)/(m)/(n) shipped with their machine halves the same day (2026-11-16
evening round): the emit validator now refuses (k) a tabled method that PUBLISHES a
stream whose unit no CONSUMER pins - a wiring unit's own pin counts as PRODUCTION, not
consumption, and the out-of-process exemption must name the source unit (W1-W3 pins;
the real F1 plan is refused exactly at T2-020); (m) a SIGNAL return (`boolean`,
`Mono<Boolean>`, …) with no `semantics` (W4-W4c; the live plan's publish/append
surfaces are refused); (n) a product claimed by BOTH a wiring factory and a
self-registration duty (W5-W5b). Guidance remains for what no structural check can
see: (l)'s cross-prose literal agreement, (m)'s both-branch CONSUMER intents, F5's
test-side assertion of claimed step logs, and write-time stereotype choices the plan
never mentioned.

## 6. Bottom line

The FACTORY is now trustworthy: for the first time the green board and the green tree
mean the same thing, every stop was a root cause with a pin, and the economics held.
The ARTIFACT runs, persists and audits correctly on the path that exists — but it
implements a subtly different contract than the seed: its reordering heart never
beats (F1), its metric family is from another domain (F4), and its event-sourcing
revision scheme is self-contradictory (F3). These are plan-quality defects, visible
only to cross-unit/seed fidelity checks — §5 turns each into a machine-enforceable
rule for the next drain.

---

# PART II — second drain (13:54–15:33): historical record

Object: the REGENERATED service (26-unit decomposition) produced by the engine
after every PART I fix shipped; same path as above. Method: full source read,
live deterministic probes on real H2, strategy-vs-artifact cross-check, seed-
fidelity pass — zero agent sessions consumed.

Operator edits to this tree during the run: none to `src/main` (unlike the morning);
the mid-run repairs were board-side (fixture `revision` 0→1 in 6 frozen-test sites,
`sealed` removed from `TelemetryIngestionEvent.java` — an edit the recorded payload
never contained) — each disclosed and pinned in the supervision doc §"Second drain".

## II.1 Verdict up front

| dimension | state |
|---|---|
| board | 84/84 (T0 5, T1 26, T2 26, T3 26, T4 1), queue 0, quarantined 0 — matches the tree ✔ |
| suite / boot | 186/186 green, boot green, terminal suite gate certified the final fingerprint ✔ |
| seed fidelity | metric kinds, boundary numbers, `VALIDATION_FAILED`, one-sided SWIM_PACE: **all VERBATIM now** ✔ (the discovery-fidelity rule fired where the morning plan drifted) |
| reordering rule | **WIRED** — ticks + watermark drain + audit + meter on the live path (the morning's orphan F1 is gone) ✔ |
| production readiness | **NOT DEPLOYABLE** — every audit write fails on the first real request (N1, proven live), and the async pipeline carries a self-kill switch (N2) ✘ |
| root of what remains | three plan-class gaps the CURRENT gates cannot see: adapter↔schema pairing untested against real DDL (N1), context-load ≠ request-path (N1/N3), reactor-sink semantics as a stack law (N2) |

The factory improved again; the new failure is NOT a lying board — it is the
known ceiling: mocked-client tests plus a context-only boot gate certify SHAPES,
not the request path's INTERACTION with the real schema.

## II.2 Findings

### II.N1 (critical, live-proven) — the audit trail fails on every production write
`R2dbcAuditTrail.record()` inserts `(actor, action, outcome, occurred_at,
correlation_id)` — but V2 declares `audit_id VARCHAR(64) NOT NULL` as PRIMARY KEY
with no default, no identity, no generation strategy. Proof (real V2 + the adapter's
exact SQL on H2, zero sessions):

    Error: JdbcSQLIntegrityConstraintViolationException:
    NULL not allowed for column "AUDIT_ID" [23502-232]

Blast radius: `IngestTelemetryService.complete()` chains `auditTrail.record(...)` into
EVERY ingest — the row is persisted, the event is broadcast, then the audit insert
errors → the client gets a 5xx for an operation that half-succeeded, the audit floor
is 0% populated, and client retries (no idempotency key, N4) mint duplicate revisions.
Why every gate was green:
* `R2dbcAuditTrailTest` MOCKS `DatabaseClient` — it asserts SQL text fragments and
  bound values; the INSERT never touches a schema. (The sibling `R2dbcTelemetryEventStoreTest`
  DOES run the real V1 DDL on H2 via `ConnectionFactories` — the asymmetry is the tell.)
* the smoke test is `contextLoads` — no request, no write.
* the plan gave the DB step a VARCHAR id with no generation duty and the adapter unit
  no id field in its table — neither contract mentions `audit_id`, so the cross-task
  gate had nothing to disagree about.
Root owners: **agent-database-architect** (unpopulated NOT NULL PK) × **tester/coder
of the audit adapter** (a DB adapter verified only against a mock of the database) ×
**decomposition** (no request-path integration triple — see Recommendations 1–2).

### II.N2 (high) — the async pipeline has a self-kill switch: `autoCancel` sinks + resubscription
Both fan-out sinks are built as `Sinks.many().multicast().onBackpressureBuffer(capacity)`
(one-arg: **autoCancel = true**): `ReactiveIngestionEventChannel.java:15`,
`SinkTelemetryStreamBroadcaster.java:29`. `StreamProcessingSubscription` then wraps the
consumer in `retryWhen(fixedDelay)` — the exact combination that kills the sink:
any pipeline termination (window overflow → `Flux.error`, an audit error inside
`drain`, context shutdown) cancels the last subscription, the autoCancel sink
TERMINATES, and every later `tryEmitNext` returns FAIL_TERMINATED → `publish()` raises
→ **every subsequent ingest answers 503** even though `store.append` succeeded.
The broadcaster sink dies the same way the moment the last external subscriber leaves
(a normal event for an out-of-process broadcast boundary!). This morning's code passed
`onBackpressureBuffer(capacity, false)` explicitly — the 2-arg shape was lost in
today's regeneration: a silent semantic regression no gate compares.
Trigger is realistic: one device with a clock skewed minutes ahead parks samples in
the window until its 4096 capacity fills; one overflow error, and the domain is dead
to requests while the boot test still smiles.

### II.N3 (high) — production fiction in the base document, pinned by its own test
`application.yml` sets `spring.r2dbc.url: r2dbc:h2:mem:///telemetry`,
`spring.flyway.url: jdbc:h2:mem:telemetry` — literal H2 as the BASE default, with no
environment placeholder anywhere; `ApplicationYmlTest.java:40-45` asserts exactly
those literals. This contradicts, in one document set: the strategy's own persistence
paragraph ("embedded in-process substitute **only for boot/test profile**") and the
`java-springboot3` skill rule the morning wrote ("NEVER as the BASE document's
placeholder default ... the substitute reaches the boot ONLY through the test-profile
activation route"). The activation route exists (`src/test/resources/application.properties
→ spring.profiles.active=test`) but activates NO profile document — a true double
fiction: a route to nothing, and a production default that is the substitute.
Deployment cannot point the service at a real database without editing artifacts.
Root: the config test author chose "what boots" over strategy fidelity; the plan's
(h)-family checks verify document SURFACES exist, never that a base-document VALUE
matches the strategy's storage target.

### II.N4 (medium-high) — overflow/retry semantics: half-success returned as failure
Order in `complete()`: `publish` (in-memory fan-out) and `audit` run AFTER the durable
`store.append`. A channel-full or audit error 5xx-es a request whose row is already
committed; the event is already visible downstream; the client's retry then becomes a
REVISION (`findLatest` → `nextRevision`) — a data-shaping decision driven by an
infrastructure hiccup. There is no idempotency/dedup key: `eventId` is
`UUID.randomUUID()` per delivery (`IngressController.java:44`), so a network retry is
indistinguishable from a correction — the exact confusion the append-only revision
chain exists to avoid.

### II.N5 (medium) — unbounded busy-spin on emitter contention
`do { result = sink.tryEmitNext(e); } while (result == FAIL_NON_SERIALIZED);`
(both sinks) spins the event-loop thread with NO bound while two producers contend —
under the seed's burst scenario this burns CPU precisely when the system is loaded.
Reactor ships the bounded answer (`Sinks.EmitFailureHandler.busyLooping(duration)` /
`emitNext` with a handler, or `SerializedSink`); the unbounded hand-rolled loop is the
classic trap.

### II.N6 (medium) — log correlation: claimed, not implemented
The strategy's correlation surface says the key rides "audit records and, **via
context-propagation, log lines**". The artifact has NO MDC write, no
`context-propagation` dependency, no `Hooks.enableAutomaticContextPropagation()`
(grep: zero hits). Audit records (Reactor Context) are correct; the ECS step-log lines
carry no `requestId`. The claim gate verifies step-log OWNERSHIP, not the strategy's
correlation prose — so the floor has a hole that no unit can see from its own file.

### II.N7 (low-medium) — revision floor disagreement, schema vs domain
V1: `revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0)`; the domain's single
truth is `FIRST_REVISION = 1` (`TelemetrySample.java:9`). Unreachable through the app
(every insert carries the domain value) — but the schema now documents a revision the
domain calls illegal: the same "one fact, several owners" family this morning's rule
(l) targets, shrunk to a cosmetic remnant.

### II.N8 (low-medium) — migrations deployable only from the module directory
`spring.flyway.locations: filesystem:db/migrations` (the single-source rule, correctly
applied — no diverged classpath copy this time) is CWD-relative: `java -jar` from
anywhere else finds NO migrations, and with H2-as-base (N3) the app STILL boots green
against an empty database — every read/write then fails at request time. The assembly
gate's "runner wired to an empty locations folder" probe passes because the folder
exists relative to the test run. A packaged deployment ships schema-less silently.

### II.N9 (low) — payload fidelity and nullability edges
`IngressPacket.toSample` builds `rawPayload` by string concatenation with no JSON
escaping — a deviceId containing `"` or `\` corrupts the "retained verbatim" payload
(and the seed's auditability intent). V1 allows `metric_value` NULL while
`R2dbcTelemetryEventStore.toSample` reads it as primitive `Double` — any foreign row
with a NULL value NPEs the read path.

### II.N10 (low) — knob and taxonomy notes
`reorder-buffer-capacity` feeds TWO bounded queues (ingestion channel AND the reorder
window — one number, two backpressure points). `ValidationFailed` events are silently
dropped by `StreamProcessingService.handle` (never reordered/broadcast) — defensible
(failures aren't ordered telemetry) but nowhere declared.

## II.3 What the fixed engine got RIGHT (grading this morning's fixes on live fire)

* **Seed fidelity (rule 4 / discovery):** metric kinds, the exact ranges (30–240,
  0–2500, 0–220), the one-sided `SWIM_PACE > 45` (`minExclusive`), the
  `VALIDATION_FAILED` term — all verbatim. Undisclosed GCT/RESPIRATION/SWIM_STROKE
  ranges are honestly `enabled: false` + a strategy open question. The morning's
  weather-metrics world is gone.
* **Consumer closure (rule (k)):** every publisher-form return is pinned
  (`IngestTelemetryServiceTest`-driven chains: channel→subscription→service→window→
  broadcaster); the reordering rule RUNS at runtime for once — ticks, watermark,
  drain ordering by (tDevice, revision), overflow posture metered.
* **Signal semantics (rule (m)):** `offer`/`accepts`/`isValidationFailed`/`enabled`/
  `minExclusive` all carry TRUE/FALSE contracts, and the implementation HONORS them
  (offer-false → error → 503 handler; see N4 for the sharper ordering question).
* **Revision single-source (rule (l) at work):** ONE `FIRST_REVISION` constant, and
  the revision CHAIN now derives from the log (`findLatest → nextRevision`), closing
  the morning's collision class; the UNIQUE key gained `metric_kind`.
* **Registration XOR (rule (n)):** one mechanism (all beans via `TelemetryBeansConfig`,
  zero stereotypes except the sanctioned filter) — the morning's double declaration
  is gone.
* **Scaffold tooling (P-pins):** surefire 300s guardrail + activation file present in
  the delivered pom/paths; single canonical migration directory (no diverged copy).
* **Exit-lie class (terminal suite gate):** born this morning, and its first live
  double-shift (mockability incident W7) charged the CLOSER, not the victim.
Composition root sits at the ancestor package with no scan directive needed.

## II.4 Economics

143 sessions / 155 units across both drains (~0.92/session-per-unit incl. all repair
cycles); 17.15 M tokens in; second drain's plan phase: architect phases + DB + scaffold
≈ 12 sessions, 80 agent units ≈ 95, the rest incident repair — every tooling-caused red
closed at zero bill after its root fix (ledger replay: "restored re-verification: green,
no session billed" ×2).

## II.5 Recommendations (the ceiling this run exposed, in priority order)

1. **Real-substrate rule for persistence adapters (N1):** an adapter whose table pins
   SQL against the runtime store must ship its paired stage-1 test on the EMBEDDED
   SUBSTITUTE EXECUTING THE REAL MIGRATION DDL (the store adapter's own test pattern);
   a mocked database client verifies call shape, never schema fit — the plan rule
   belongs in `task-decomposition-dag` (test pairing) + the tester skill. Machine-
   checkable core: a stage-2 unit whose intent names an INSERT/migration and whose
   paired stage-1 intent lacks a substitute-executing marker (`ConnectionFactories`/
   `Files.readString`) is refused.
2. **One request-path integration triple per domain (N1/N3):** a @SpringBootTest slice
   that drives the ENTRY endpoint (WebTestClient) against the substitute database and
   asserts the durable effect (row count, audit row) — `contextLoads` proves the graph
   resolves; an endpoint call proves the pieces AGREE. This is the N1 detector and
   belongs to the decomposition duties list.
3. **Sink lifecycle law (N2):** a reactor fan-out sink feeding a retrying/late-
   resubscribing consumer MUST be created with autoCancel=false (or a direct
   replay/serialize choice named in the strategy); stack-skill line + candidate
   for a weaver-side lint.
4. **Strategy-value fidelity for config (N3):** extend the (h) family — a substitute
   connection string (the stack skill names the embedded schemes) in a NON-profile
   document is refused when the strategy says the substitute is test/boot-only;
   the config test must pin PLACEHOLDERS for production readers.
5. **Idempotency duty for retryable effects (N4):** when the entry contract is
   at-least-once (HTTP client visible), a retry must not become a domain revision —
   carry a client-supplied key (the seed already has one: the device event identity)
   or declare at-most-once semantics in the strategy.
6. **Bounded emit retry (N5)** and **context-propagation duty when the strategy
   promises log correlation (N6)** — stack-skill lines.

## II.6 Bottom line

The morning's artifact lied about its board and its integrity; the fixed engine
today produced an artifact whose board is TRUE, whose seed fidelity is real, and whose
business rules actually RUN — and then exposed the NEXT honest ceiling: nothing in the
plan ever executed a request against the real schema, so a NOT NULL landmine (N1) and a
sink-lifecycle trap (N2) sit between this tree and production. Both are one rule away
from being structurally impossible: recommendations 1 and 2 close that class the same
way (k)/(m)/(n) closed the last one.

---

# PART III — third drain (16:43–19:27): THE CURRENT ARTIFACT

Object: the REGENERATED service (32-unit decomposition, 102 tasks, root package
`com.blackboard.telemetry`, contexts ingestion / history / shared) produced by the
engine AFTER every fix shipped earlier today — this is both an artifact inspection
and the live-fire grading of today's own rules. Method: full source read (32 main
classes + 33 test classes, one of them the boot smoke), deterministic probes on real H2 (zero agent sessions),
strategy-vs-artifact cross-check, fresh authoritative suite.

Operator edits to this tree (disclosed): 7 literal corrections in the e2e slice
(`"BLE"` — a transport label owned by no contract — to the enum's own
`EDGE_DEVICE`), same repair class as PART II's fixture fixes; the units then
replay-closed at zero billed sessions.

A `README.md` was written for this artifact the same evening; every claim in it
(config keys, meter names and tags, request shape, status semantics — including
that a duplicate natural identity answers `202` as a silent no-op — schema
constraints, three-branch reorder logic, env vars, test counts 33 classes/258
tests) was re-verified against the delivered sources, and the G-list above is
reproduced there as the known-limitations section.

## III.1 Verdict up front

| dimension | state |
|---|---|
| board | 102/102 (T0 5, T1 32, T2 32, T3 32, T4 1), queue 0, quarantined 0 ✔ |
| authoritative suite | **258 tests, 0 failures, 0 errors** — fresh offline `./mvnw -o test`, red classes: NONE ✔ |
| boot + jar portability | GREEN; migrations applied from PACKAGED resources via the flyway customizer — `java -jar` works from any directory ✔ |
| seed fidelity | 7 metric kinds VERBATIM, boundaries 30–240/0–2500/0–220, `SWIM_PACE` one-sided via `minExclusive`, `VALIDATION_FAILED` + honest `enabled:false` for the unnamed ranges ✔ |
| reordering rule | LIVE: e2e asserts `window buffered` / reorder / backfill effects against the real migrated schema ✔ |
| deployable? | **Yes, as an ingestion service.** Residual gaps below are contract/documentation-level (G1–G4), not silent landmines |

The failure class moved one last time: PART I lied about the tree, PART II's tree
held schema landmines no test touched, **PART III ships a tree whose integration is
touched by its own tests** — the e2e slice caught and killed the mocked-substrate
and vocabulary bugs DURING the drain, which is precisely what it was born to do.

## III.2 Today's gates on live fire — evidence per rule

| rule | how the third drain's plan honored it (verified in sources/tests) |
|---|---|
| (k) consumer closure | `ValidatedSampleStream.events()` is consumed by a planned unit (`PipelineSubscriber:38` subscribes → `ReorderHistoryService.handle`); no registered island anywhere |
| (m) signal semantics | every `boolean`/status return in the tables carries TRUE/FALSE `semantics`; `publish` failure surfaces as an error the pipeline handles with a FAILED audit (`ReorderHistoryService.failed`) |
| (o) real substrate | `R2dbcTelemetryHistoryRepositoryTest` runs `ConnectionFactories` + `Files.readString` of the ACTUAL V1/V2 DDL; the e2e slice boots the migrated schema — the mocked-DatabaseClient-only pattern from PART II N1 is gone |
| (p) request-path slice | `PipelineEndToEndTest` (8/8): 202 + durable VALID row + `VALIDATION_FAILED` row kept + **resent packet keeps one row and no revision** + downstream broadcast — the first artifact in the day's series where controller→store→schema agreement is PROVEN |
| (q) idempotency | natural business identity `UNIQUE (device_id, metric, t_device)` + duplicate insert → no-op; pinned by the e2e case above |
| (r) packaged migrations | `MigrationWiringConfiguration` flyway customizer → `classpath:db/migrations`, scripts present under `src/main/resources/db/migrations/` ✔ (but see G1) |
| (n) one registration | stereotype on adapters/controllers, factories in `TelemetryConfiguration` — no double claim surfaced; boot green |
| (l)/(d)/(W6) | `ValidationStatus{UNVALIDATED,VALID,VALIDATION_FAILED}` — the initial-state encoding PART I's D1 demanded; constructor bounds tabled in `semantics` |
| reactor laws | history publisher: `Sinks.many().replay().limit(cap)` + `emitNext(busyLooping(timeout))`; validated stream: `onBackpressureBuffer(cap, false)` (autoCancel OFF) + deadline-bounded retry — PART II's N2/N5 shapes are structurally avoided |

## III.3 Residual findings (honest, none silent)

* **G1 — documented-vs-effective config divergence.** The base `application.yml`
  still spells `spring.flyway.locations: filesystem:db/migrations`, pinned by its
  frozen `ApplicationYmlTest:57`; the runtime truth is the customizer's
  `classpath:db/migrations`. The delivered jar is portable, but the yml line is now
  DEAD CONFIG that tests still certify — the exact seam rule (r) exists to prevent,
  visible here because this plan was emitted before rule (r) shipped. A re-emitted
  plan cannot reproduce this pair; for this tree, the README documents the
  effective value.
* **G2 — dedup swallows value-corrections of a known identity.** `UNIQUE(device_id,
  metric, t_device)` means a RESENT sample with the same identity but a DIFFERENT
  value is silently dropped (insert conflict → no-op), never appended as a revision.
  The seed's "corrections append new event revisions" is honored only along the
  late-arrival axis (`t_ingress − t_device > window`). No test pins the
  same-identity-new-value case; the strategy lists corrections handling as an open
  question, so this is a disclosed ambiguity the plan resolved one way without
  asserting it. Candidate: a strategy-level Assumption or an emit rule binding
  "correction" semantics to an identity that INCLUDES the value axis.
* **G3 — log correlation is manual.** `requestId={}` is hand-passed as a log
  argument; there is no MDC/`context-propagation` bridge, so a future log line that
  forgets the argument silently loses correlation. The strategy promises the key on
  log lines; the mechanism is discipline, not dependency. Minor, but it is the
  difference between "correlated" and "correlatable".
* **G4 — broadcast drops are audited but not metered.** `PipelineSubscriber:38`
  swallows per-event errors after the service's FAILED audit; a persistently
  failing pipeline would show in `audit_trail` but not in any counter — one metric
  (`telemetry.pipeline.dropped{stage}`) would close the observability loop the
  strategy's own floor demands.
* Cosmetic: `HELP.md` and an emptied package directory (`telemetry_ingestion_processing/`,
  the pre-T4 entry location) remain in the tree.

## III.4 Economics

Third drain: ~104 billed sessions for 32 units + repair cycles (~3.2/unit including
ALL gate/tooling incidents the drain itself surfaced and healed); the whole day across
three drains: ~250 sessions for 257 units (~0.97/unit) with every tooling-caused red
closed at zero bill after its root fix. Zero quarantined at exit; zero flakes across
the authoritative reruns.

## III.5 Bottom line

The factory earned its keep: every rule shipped today (k)–(r) demonstrably steered
the third plan — seed fidelity is real, the reordering rule RUNS, the integration is
PROVEN by its own slice, migrations travel with the jar, and the artifact is
deployable. The residuals (G1–G4) are the next, smaller ceiling: they are all of the
class "the plan chose one semantics and did not say so" — exactly what the strategy
Assumption/ambiguity machinery is for. The day's trajectory: lying board → silent
landmines → proven integration with disclosed edges. The process is no longer the
weakest part of the artifact; the remaining gaps are the business ambiguities only
an operator can decide.
