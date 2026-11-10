# Generated-project problems report — `high-performance-time-series-telemetry-ingestion-pipeline`
Inspection date: 2026-11-09 · Artifact root: `projects/high-performance-time-series-telemetry-ingestion-pipeline/services/telemetry-ingestion-and-processing`
Companion documents: `PROCESS-REPORT-seed002.md` (why these exist), `REPAIR-NOTES-seed002.md` (operator edits).

Scope: full static read of all 31 main + 25 test sources, pom, both config files, the 4 SQL
migrations, plus a full local `./mvnw test` (zero agent tokens).
Verdict up front: **the artifact does not compile-fail (green `test-compile`) but it cannot be
shipped**: the test suite deadlocks, the database schema is never created at runtime, and the
domain has 11 unverified/never-run units (incl. exactly the files that deadlock the suite).

---

## P0 — breaks the artifact

**1. Full test suite hangs forever (`./mvnw test` never completes).**
`R2dbcTelemetrySampleRepositoryTest.latestRevision_noRow_returnsEmptyMono` (and
`latestRevision_anyCall_neverIssuesUpdateOrDelete`) deadlock: the test mocks `DatabaseClient`
with `RETURNS_DEEP_STUBS` and stubs `.map(...).one()`, while the implementation calls
`.map(...).first()` (R2dbcTelemetrySampleRepository.java:29). The unstubbed `.first()` returns a
do-nothing mock `Mono` that never terminates; `StepVerifier.verifyComplete()` and `.block()` wait
forever. Verified live: two independent full runs stuck at that class (15+ min / 6+ min).
Provenance: implementation is the woven payload of **T2-018 — a cascade-victim unit that was
quarantined with ZERO of its own gate attempts**; the pair was therefore never validated together.
Also latent by design: surefire has no per-test/per-class timeout in `pom.xml`, and the engine's
600 s gate timeout only covers per-unit scoped runs — a full-suite run hangs indefinitely.

**2. Migrations are orphaned — the schema is never applied.**
`db/migrations/V1–V4.sql` exist (tables + `telemetry_samples_latest` view, correct names — SQL in
the repository matches them), but the pom has **no Flyway/Liquibase**, and `application.yml` sets
no `spring.sql.init.schema-locations`. On the configured H2 in-memory URL the app boots
(`contextLoads` green) and fails on the FIRST real query with “table not found”. The R2DBC tests
mock `DatabaseClient`, so nothing catches this — exactly the class of defect the T4 assembly smoke
gate must catch (T4-001 is quarantined; it never reached a green boot-with-traffic).

**3. Two Spring Boot application classes; one has an invalid `main`.**
- `com.telemetry.telemetry_ingestion_and_processing.TelemetryIngestionAndProcessingApplication`
  (scaffold/Initializr, `@SpringBootApplication(scanBasePackages=…both…)`)
- `com.pulsestream.telemetry.TelemetryApplication` — declares `public void main(String[])`
  (NON-static): a broken entry point that is never invokable and is a second
  `@SpringBootApplication`. `spring-boot:run`/`repackage` main-class resolution is ambiguous
  against it. The duplicate was introduced by the container stage and never reconciled by the
  architect plan (both packages are scanned, so beans are fine — the packaging itself is wrong).

**4. 23 tasks uncomplete — 11 T2 implementation units.**
Real failures after retries: T2-009 (port defaults/Reactor semantics), T2-010 (payload cannot be
weaved: the Java weaver grammar rejects the interface `default` member), T2-021, T2-027
(status-vocabulary conflict). **Never attempted (cascade quarantine)**: T2-015/016/018/022/023/
024/025 — their source files remain woven into `src/main` **unverified**, and T2-018 is precisely
the deadlock of P0-1. The tree therefore mixes validated and unvalidated code with no marker.

---

## P1 — correctness / quality defects

**5. `window-size` conflates Duration and count in `WindowBufferService`.**
Config `telemetry.window-size: PT1M` (a Duration) is routed through the 3-arg constructor as
`(int) windowSize.toSeconds()` → groups **60 samples** per window; the red test’s 2-arg
constructor uses an int count directly. Duration-vs-count semantics differ per construction path,
and `streamWindow(…, Duration)` ignores its `window` argument entirely. Controller hardcodes
`Duration.ofSeconds(1)`. *(Operator glue — see REPAIR-NOTES; still shipped.)*

**6. Unbounded repository scan in the publisher-less path.**
`WindowBufferService.streamWindows(deviceId, metric)` with `publisher == null` queries
`findLatestRevisionsOrderedByTDevice(…, Instant.EPOCH, Instant.MAX)` — full-table scan per call on
an append-only time series. Contradicts the seed’s “high-throughput, bounded” posture.

**7. Ingest path is O(2N) sequential DB round-trips.**
`IngestPacketService.ingest` does `concatMap(sample -> repository.latestRevision(…).flatMap(-> append(…)))`:
two blocking-chain round-trips per sample, serialized. Correct but at odds with the seed’s burst
load requirement (thousands of simultaneous 1Hz devices); no batching, no bounded-queue on the
ingress Mono.

**8. Bean-validation on the ingress endpoint is dead configuration.**
`@Valid @RequestBody Mono<IngressPacketRequest>` — WebFlux does not apply JSR-303 to a reactive
body argument without an explicit validator setup; `@NotBlank/@NotNull/@NotEmpty` annotations and
the `validation` starter currently enforce nothing at the HTTP edge. (Domain-side
`SampleValidator` fail-closed validation still covers metric ranges, which is what the seed
actually requires — so severity stays P1.)

**9. Duplicate/aliased configuration blocks.**
`application.yml` defines the props twice: under `pulsestream.telemetry` (anchor) and re-exported
at root `telemetry: *telemetry` (alias) to satisfy `TelemetryProperties(prefix="telemetry")`;
plus a scaffold `application.properties` also setting `spring.application.name`. The active keys
work, the structure invites drift; `HELP.md` (scaffold residue) documents the abandoned package.

**10. Seed-fidelity edge on swim pace.**
Seed: “Swimming Pace: **>45** sec/100m”. Config `swim-pace: min 45` + `SensorMetricBoundary.contains`
inclusive → 45.0 validates as VALID; off-by-one semantics against the business rule.

**11. Dead/decorative members introduced to satisfy tests.**
- `IngestResult.accepted(String deviceId)` ignores its parameter and returns constant counts.
- `IngressPacketRequest(String,long,long,String,double)` ignores the `long revision` slot (it maps
  nowhere).
- `IngressPacket` carries a vestigial method `public void IngressPacket(…)` (record with a
  same-named void method) — weaver artifact; and single-sample delegators `metric()/value()/tDevice()`
  that silently return null/0 for multi-sample packets.
- Class name `DeviceAclMapper` claims ACL semantics it does not implement (pure DTO mapper).
*(Most of these are operator/coder conveniences to satisfy conflicting frozen tests; they are
smells, but each traces to a plan-stage ambiguity documented in the process report §4.)*

---

## P2 — hygiene

12. `HELP.md`, `.gitattributes`, unused Initializr package left beside the pulsestream tree.
13. No `.gitignore` entry hygiene verified for `target/` (exists) — fine; no README for the service.
14. Mockito self-attach warnings; Boot 4 artifact id `spring-boot-h2console` (odd name, resolves OK).

---

## Verified-good (against the seed — so the report is not only negative)

- **Non-blocking guarantee**: zero `block()/Thread.sleep/blockFirst` in any `src/main` file (grep
  clean); ingestion chain is pure Flux/Mono composition.
- **Append-only event sourcing**: INSERT-only SQL (asserted by T2-019-style tests), revisions bumped
  for backfill (`withBackfillRevision`), `telemetry_samples_latest` view exists in V2 with matching
  names; `TelemetryEvent` carries Validated/ValidationFailed/Backfilled/WindowBuffered.
- **Boundary validation, fail-closed**: unknown metric → `VALIDATION_FAILED`, payload retained,
  not dropped (seed-compliant); HR/Power/Cadence bounds exactly match the seed numbers.
- **Backpressure broadcasting**: bounded multicast sink, explicit `DROP_OLDEST` overflow strategy,
  emit-retry scoped to `FAIL_NON_SERIALIZED`.
- **Reorder semantics** (`ReorderBufferService`): watermark + `ReorderWindowPolicy.LATE` → backfill
  revision bump, per-batch sort by `tDevice` — matches the seed’s reorder/backfill rule.
- `./mvnw test-compile` is green for the whole tree (3,344 LOC, 31 main + 25 test files).

## Priority order for the next pipeline iteration
1. Weaver/verification: **quarantine must revert or mark the unit’s woven file** (P0-1 root);
   add surefire per-test timeouts (P0-1 amplifier).
2. Wire a migration runner (Flyway) or `spring.sql.init` in the scaffold plan (P0-2), and make the
   T4 assembly gate exercise one real append+query round-trip.
3. Collapse the duplicate boot class in the container→architect handoff (P0-3).
4. Give never-attempted cascade victims at least one own-gate attempt before quarantine (P0-4).
5. Clean the Duration-vs-count conflation and the EPOCH→MAX scan once P1 owners re-enter green.
