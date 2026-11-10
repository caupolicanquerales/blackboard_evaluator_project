# Repair notes — run of seed/002_description.md (PulseStream Engine), 2026-11-09

> SUPERSEDED AS THE ANALYSIS DOCUMENT by `PROCESS-REPORT-seed002.md` (final results §7-§8).
> This file documents the OPERATOR code edits made to the generated project BEFORE the
> "tune the process, do not fix generated code" directive; keep it as the contamination
> disclosure referenced by §5 of the process report.

Pipeline: `python3 orchestrators/orchestrator_github.py --seed seed/002_description.md --watch`
(Copilot CLI backend). Process was STOPPED by the operator on request.

State at stop: queue ~53 tasks, complete 31, error 0. Full `./mvnw test-compile` of the
generated service is GREEN. Nothing was mid-write when stopped (killed orchestrator +
copilot children by PID).

## Engine fixes (orchestrators/)

1. `settings.py` (none) / budgets unchanged — per-session tool-call budgets + hard kill
   (2x budget + slack 4) worked as designed.

2. `test_gate.py`
   - `JAVA_LANG_NAMES`: added `NoSuchMethodException` (java.lang reflection exception used
     in `throws` clauses was misread by closure.py as a missing producer).
   - `repair_test_imports()`: rewritten. Now covers MAIN and TEST trees; reroutes
     imports of NESTED types written as if top-level (`import p.Inner;` →
     `import p.Outer.Inner;`), reroutes wrong-package imports of uniquely-owned
     top-level types, and ADDS missing imports (including same-package nested types,
     which javac does not put in scope). Idempotent (second pass repairs 0 files).

3. `tdd_engine.py`
   - `_unresolvable_missing()`: the scheduling-hole detector only saw file STEMS, so
     nested types (e.g. `IngestResult` inside `IngestPacketUseCase.java`) looked like
     holes and aborted the whole drain. Now counts all declared types (class/interface/
     enum/record) in project sources as resolvable.

4. `closure.py`
   - `gaps()`: same blind spot — nested declarations in main files are now added to
     `produced_pairs`, so `--emit` no longer queues duplicate/bogus producers for names
     that exist nested.

## Run sequence and operator fixes (generated project)

- Abort 1 (fatal, T1-014): tester assumed package `domain.policy` for `ReorderWindowPolicy`;
  architect scheduled it in `domain.service`. Import repointed, red-phase record
  regenerated locally with `run-test-tool.py | write-red-phase.py` (zero agent tokens).
- Emitted missing producers via sanctioned path: `closure.py --emit` → T2/T3-026
  (WindowQuery — later identified as MY duplicate, see below) and T2/T3-027
  (IngestResponse — genuine gap).
- Abort 2 (fatal, T2-020): hole detector false positive on nested types → fixed in
  `tdd_engine.py` (above).
- Livelock: quarantined units left broken woven files; every gate deferrals blamed peers;
  coders received foreign blame ("payload unchanged") and burned 3 attempts. Orchestrator
  stopped; domain repaired deterministically:
  - `WindowBufferService.java`: rewritten to its red tests (frankenstein file had two
    constructors, lost `implements`, unbound pattern variables).
  - `implements` restored: `IngestPacketService` → `IngestPacketUseCase`,
    `BackpressureEventBroadcaster` → `TelemetryEventPublisher`,
    `R2dbcTelemetrySampleRepository` → `TelemetrySampleRepository`.
  - `QueryTelemetryWindowUseCase` port: + default `queryWindow(String,String,Instant,Instant)`
    and `streamWindow(String,String,Duration)` (kept abstract surface unchanged so T1-010's
    anonymous implementers still compile).
  - Additive members demanded by frozen tests: `TelemetrySample.id()`, `.backfill()`,
    convenience constructors ((…,Instant,double,int/long), (…,double,Instant,long), 6-arg
    status-String, 7-arg long revision), `of(deviceId,tDevice,tIngress)`;
    `IngressPacket.RawSample(String,double,Instant)` + single-sample delegates
    `metric()/value()/tDevice()`; `TelemetryWindowBuffered` 4-arg secondary;
    `IngestResult.accepted(String)`; `IngressPacketRequest` 5-arg single-sample secondary;
    `TelemetrySampleEntity.fromDomain` made static (pure function).
  - Duplicates caused by races between the still-running coder weaves and manual edits
    were collapsed (IngestResult.accepted, TelemetryWindowBuffered 4-arg).
  - ONE test file edited by operator (only the operator may touch frozen tests):
    `TelemetryWindowControllerTest` — stubbed the use-case returning the REST DTO
    (layering inversion contradicting WindowBufferServiceTest); rewired to stub domain
    samples and assert mapped `TelemetrySampleResponse` bodies.
  - T2-026/T3-026 (top-level WindowQuery producer) were REMOVED from queue + payload +
    weave + file: the architect owns WindowQuery nested in the use-case; my earlier
    `--emit` duplicated it (closure stem-blindness was the cause; engine now fixed).

## Token accounting (from log `[tokens]` events)

- Every agent session = 1 premium request; sessions observed: ~1 per task pass, avg ~6
  tool calls (budget 6–12, hard kill 2×+4 never fired except once at 15 on a batch).
- Total recorded premium requests across the whole day-run: ~76 (incl. smoke test).
- Baseline cost: ~30k input tokens per copilot call (cache writes) — the real cost driver,
  capped by the per-session call budgets.
- All deterministic repairs above cost ZERO agent tokens (local `mvnw` +
  `run-test-tool.py` only).

## To resume

```
cd /home/caupolican/Desktop/Blackboard/blackboard_evaluator_project
setsid nohup python3 -u orchestrators/orchestrator_github.py \
  --seed seed/002_description.md --watch --retry >> /tmp/opencode/pulsestream_run.log 2>&1 < /dev/null &
```

`--retry` restores any future quarantines; skip-agent paths reuse recorded payloads and
red records, so already-finished work is not re-billed.

## Known open items (runtime, not compile)

- `ReorderBufferService.reorder` does not yet flag late samples as backfilled
  (revision bump) — its T1-014 test asserts this; engine retry must fix (unit-owned).
- DeviceAclMapper `List<TelemetrySample>` vs `List<IngressPacket.RawSample>` internal
  mismatch surfaced earlier — unit T2-021 owned, retry with clean logs should converge.
- If a quarantine wave repeats, suspect cross-test contract conflicts first (engine
  cannot edit tests; operator edits are listed above).
