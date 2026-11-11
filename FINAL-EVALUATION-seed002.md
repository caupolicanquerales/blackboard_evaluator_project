# FINAL EVALUATION — seed 002, clean validation drain (2026-11-11)

Object: the generated service at
`projects/high-performance-time-series-telemetry-ingestion-pipeline/services/telemetry-ingestion-processing`
Authorship: fully agent-generated (no operator product edits this run — unlike the
first run's §5 contamination). Engine-side repairs only: wrapper bits, and removal of
ONE import the orchestrator's own repair pass had wrongly inserted (disclosed, §23.4 R6).

Method: authoritative full-suite run + record-by-record attribution of every red unit
and every latent finding to the agent decision that created it.

## 1. Artifact health

| probe | result |
|---|---|
| `mvnw test-compile` (main+test, whole module) | GREEN |
| application boot (smoke `TelemetryIngestionProcessingApplicationTests`) | GREEN (1/1) |
| full suite | **80 tests: 65 green, 3 failures, 12 errors** — every red sits in exactly the 3 locked classes (`SampleValidatorTest`, `IngressControllerTest`, `R2dbcEventLogRepositoryTest`); zero collateral reds, zero flakes across 4 reruns |
| board | 45/51 units complete, 6 quarantined (3 real + 3 never-charged dependents), queue 0 |
| code layout | clean hexagonal-ish layering (`api/application/domain/infrastructure` per context), no frankenstein files, no duplicate members (W1-class weaving artifacts: zero found) |
| tree hygiene | one leftover: `TelemetryWiringConfiguration.java.new` (assembly scratch file) |

## 2. The three terminal defects — root cause chains

### D1  T2-003 `SampleValidator` — pair contradiction (4 reds)
Chain:
1. architect T2-002 intent: "Compact constructor rejects blank deviceId/metric **and
   null status**" — a null-intolerant value type.
2. architect ast_hints (identical on T1-002/T2-002/T1-003/T2-003):
   `TelemetrySample(String … , String validationStatus)` — **nullability semantics are
   NOT in the table** (§19 mechanism pins shapes, not contracts about null).
3. Domain design requires a PRE-validation state (validator receives raw samples) but
   the type offers only `VALID`/`VALIDATION_FAILED` + null-rejection.
4. tester T1-003, obeying the table (its profile: shapes come ONLY from ast_hints),
   writes `sample()` passing `null` → every call throws `IllegalArgumentException`.
5. coder T2-003 cannot change T2-002's completed constructor nor the frozen test →
   locked after full lifetime budget, closed out at ZERO sessions, WOVEN-CLEAN.
**Root owner: agent-architect** (an unusable type surface: a null-rejecting mandatory
field with no legal way to represent its initial state, plus a contract table that
cannot express it). Secondary mechanism gap: ast_hints schema lacks nullability/
semantics.

### D2  T2-008 `IngressController` — contract-vs-behavior contradiction (3 reds)
Chain:
1. architect ast_hints pins on BOTH test and impl units:
   `receivePacket(Flux<@Valid IngressSampleDto> samples)`.
2. architect T1-008 intent mandates the test POSTs **"a JSON array"** of DTOs.
3. WebFlux decodes `Flux<T>` bodies as streamed JSON documents, NEVER a single array
   document → with the pinned signature, no valid body shape reaches the endpoint:
   every POST 500s at decode time. The 202 path is unreachable by ANY payload.
4. coder iterated (3 attempts + 1 grant): manual `Validator` + `ServerWebInputException`
   — correct response to the wrong (unsatisfiable) binding.
**Root owner: agent-architect** (authored both sides of the contradiction — signature
and expected request encoding — in the same decomposition). The plan-level rule missing:
a pinned `Flux<Dto>` request must be paired with a stream-encoding intent, or `List<Dto>`
with array-encoding.

### D3  T2-012 `R2dbcEventLogRepository` — schema never reaches any runtime (8 reds)
Chain:
1. tester T1-012 wrote (per its intent) `@SpringBootTest` + H2-PostgreSQL-mode +
   "Flyway migrations V1/V2 applied" — a legitimate, but boot-wide, unit gate.
2. architect scheduled **NO configuration unit**: no task path ever targets
   `src/main/resources/application.*`. The config duty was written into T2-001's intent
   as prose ("Also provide application.yml entries…") while T2-001's path is ONE java
   file — a unit can weave exactly one file, so the instruction was unschedulable noise.
3. database-architect emitted `db/migrations/flyway-profile.properties` using
   **`flyway.locations=filesystem:db/migrations`** — real Flyway keys in a file NO Spring
   app reads, beside migrations on the filesystem nothing puts on any classpath.
4. §10.5 orphaned-schema gate checked for a RUNNER MARKER (spring.flyway.enabled) and
   found one (added by assembly) — it cannot see that `locations=classpath:db/migration`
   points to a folder containing only `.gitkeep` (zero migrations). Startup "migrates"
   successfully with nothing; smoke boots green over a **schema-less runtime**.
5. Test context: same nothing → `BadSqlGrammar DELETE FROM telemetry_event_log.…`.
6. assembly (T4-001) improvised values it had no spec to bind against (see L2/L3).
**Root owner: agent-architect** (missing scheduleable config unit; §10.7 invariant
"operational values bind through the config unit" violated silently); contributors:
agent-database-architect (inert file, wrong key namespace), assembly gate (marker-deep,
not alignment-deep).

## 3. Latent problems the green gates did NOT catch (found by this inspection)

L1 **All runtime samples validate as VALIDATION_FAILED**: `TelemetryProperties.metricBounds`
is only populated by an application.yml that was never scheduled (§D3); empty bounds →
validator flags everything. No test catches it (tests construct properties directly).
L2 **Reorder window is 5 s at runtime; the seed mandates 60 s** — assembly honestly
disclosed "values are my own defaults". Backfill reordering is functionally broken in
production by 12×.
L3 **Migrations never run at runtime** (empty flyway locations): the first real
repository call in production would hit missing tables (the exact failure T2-012 shows
in tests). Assembly boot-green masks it because no bean touches SQL at startup.
L4 **`ReorderBuffer` registered as a singleton `@Component` with mutable internal
lists** — evaluator T3-010 already flagged the shared-state-per-subscription hazard;
assembly's singleton registration made it real. Plan gap: a stateful per-stream buffer
needs a factory/scoped bean; no unit owned that decision.
L5 **Boot-wide unit tests** (T1-012) couple a single unit's gate to the whole bean
graph — cost driver (T2-012's boot-era double billing) and reason every graph defect
lands on an innocent bystander. Allowed by no rule; needs one.
L6 hygiene: `TelemetryWiringConfiguration.java.new` leftover; three evaluators
explicitly trusted a cached "passed" verdict while seeing "3 errors alongside passed"
(§23 wave-verdict counts leak into their reports — honest disclosures, but a memo
wording trap).

## 4. Per-agent scorecard (this clean run)

| agent | sessions | outcome | verdict |
|---|---|---|---|
| discovery specialist | 1 (3 calls) | valid slice | GOOD |
| context-mapping specialist | 1 (4 calls) | valid map (after docs fix) | GOOD |
| architect — strategy | 1 (15 calls) | complete strategy | OK |
| architect — decomposition | 1 (18 calls) | 45 units, ast_hints everywhere | **ROOT CAUSE of D1/D2/D3, L1–L4**: contradictory pinned signatures, null-intolerant type with no initial state, prose duties without owning units (config), bean-scope decision unowned |
| container | 1 (12 calls) | green scaffold, Boot drift handled by skill rule | GOOD |
| database architect | 1 (9 calls) | real SQL, correct expand-only | MIXED: migrations content fine, but inert profile keys/location (D3 step 3) |
| testers (batched) | 4 sessions, 15 units, 0 quarantine | all reds recorded properly; shapes from tables | GOOD — D1 step 4 was their table-legal reading of a plan contradiction; L5 is a taste rule to add |
| coders (batched+singles) | 14 units green first-wave, retries bounded | final-assign defects self-corrected once feedback was named | GOOD: zero terminal defect was coder-caused |
| evaluators | 12 green, 3 never-ran | CLEAN×8, REFACTORED×4, findings honest (L4 flagged by T3-010!) | GOOD |
| assembly | 2 sessions, gate green | booted app; disclosed placeholders | MIXED (forced): invented config values (L2), empty flyway location (L3), `.new` leftover, singleton registration crystallizing L4 — all because the plan left it nothing truthful to bind |

Process-machinery note: after today's fixes (§23), **no terminal defect and no latent
finding is a tooling failure** — every red has a named, evidenced, plan-level owner,
and the harness converged everything convergable (45/51) while spending its last three
restart passes at ZERO billed sessions.

## 5. Where to fix the roots (for your determination)

1. **Decomposition validity check (agent-architect, `task-decomposition-dag` skill +
   a validator like §19's)** — mechanical rules, all detectable at emit time:
   - every duty in an intent must be executable through THAT unit's path/file-type, or
     name an existing owning unit (kills D3 step 2's "also provide application.yml");
   - whenever any task mentions `@ConfigurationProperties`/operational values, a config
     unit whose path targets `src/main/resources/application.*` MUST be scheduled with
     the seed's literal values in its intent (kills D3, L1, L2, L3 by construction);
   - a pinned `Flux<Dto>` request signature contradicts "JSON array" wording in the
     paired test intent (kills D2);
   - ast_hints entries gain a semantics column the testers must obey (nullability,
     initial-state encoding) — or the domain record must ship an UNVALIDATED constant
     (kills D1: the architect wrote "rejects null" against a type whose only purpose is
     to receive pre-validation samples).
2. **Database architect handoff rule**: profile fragments must use the runtime's real
   property namespace and be consumed by the config unit it names — or don't write them.
3. **Assembly gate depth (§10.5 upgrade)**: alignment check, not marker check — when
   `db/migrations/*.sql` exist, assert every migration filename is discoverable under
   the configured locations (and that locations are non-empty), before accepting boot.
4. **Bean-scope ownership**: a unit exporting mutable per-stream state requires a
   companion wiring decision (prototype/factory) in the plan — evaluator T3-009/010
   already saw the symptom ("looked like a green-phase special case").
5. **Tester taste rule**: repository gates should use a persistence slice
   (`@DataR2dbcTest`-class) unless the unit IS composition — boot-wide unit tests must
   be reserved to assembly/wiring units (removes L5 and the whole D3 blast radius from
   ever charging a bystander again).

Root-of-the-roots, in one line: **the architect decomposed the DOMAIN correctly (the
context map, ownership, and invariants all held for 45 units) but did not decompose the
RUNTIME**: nothing in the plan owns application config, migration application, bean
scope, or request-encoding semantics — and the two contract-table contradictions (D1,
D2) show the table currently pins shapes without pinning the behaviors those shapes
make possible.

## 6. Next-session checklist (plan-stage fixes to implement in skills + plan gate)
Read first: PROCESS-REPORT-seed002.md §19 (ast_hints enforcement mechanism), §23 (all
today's fixes), and this file §5. All changes are plan-stage (skills) + emit-time
validators — never post-hoc test edits.
1. `.opencode/skills/architect-practices/task-decomposition-dag/SKILL.md` (+ .github
   mirror is a symlink — one edit): (a) EVERY duty an intent assigns must be executable
   by that unit's own `path` artifact or name the owning unit — "also provide <other
   file>" inside an intent is the D1..D3 root pattern; (b) if any task mentions
   @ConfigurationProperties/operational values/seed literals, a CONFIG UNIT targeting
   `src/main/resources/application.*` MUST be scheduled carrying those literal values;
   (c) pinned request signatures must match the paired test intent encoding
   (Flux<Dto> = streamed documents; List<Dto> = one array document); (d) ast_hints
   entries may carry a `semantics` note (e.g. nullability, initial-state sentinel) and
   MUST for mandatory fields whose type rejects null — the pre-validation state of
   D1 must be a named constant in the producing unit's table.
2. `.opencode/agents/agent-architect.md` + `.github/agents/agent-architect.agent.md`:
   restate (a)-(d) as emission duties (profiles carry rules; skill carries vocabulary).
3. `orchestrators/task_queue.py` (planning-mode validator, like §19's): reject a task
   whose intent mentions a file artifact that is not its `path` and not any other
   task's `path` (config-unit check); reject test+impl unit pairs whose pinned request
   parameter type contradicts the test intent body-shape words. Emit-time = zero agent
   sessions wasted.
4. `.opencode/skills/architect-practices/database-persistence-strategy` + concrete
   migration skill: a profile fragment must use the RUNTIME property namespace
   (`spring.flyway.locations`, not `flyway.locations`) and name the consuming unit —
   or not be written at all. Migrations folder and configured locations must align.
5. `orchestrators/assembly.py`: deepen the §10.5 schema gate from marker to ALIGNMENT:
   when `db/migrations/*.sql` is non-empty, the configured locations must contain ≥1
   migration file (check both classpath-under-src and filesystem paths); else gate red
   with the actionable line (assembly agent wires it — the only stage allowed).
6. Tester profiles (`agent-tester` ×2) + `tester-framework` skill: repository/adapter
   unit gates should use a persistence-slice test (stack skill gives the concrete
   annotation); boot-wide context tests reserved for composition/wiring units — unless
   the pinned plan says otherwise.
7. Gauntlet: extend section G (plan validation) with the (a)-(d) fixtures — accept
   aligned pairs, REJECT a config-less plan, an intent naming an unowned file, a
   Flux-vs-array contradiction, and a null-rejecting mandatory field with no
   initial-state constant. Keep the board wipe-and-rerun protocol of §19 after landing.
Definition of done: gauntlet green; a fresh seed-002 drain shows D1/D2/D3 dying at
EMIT time with named reasons (zero coder sessions spent on them), and the final suite
has no red outside genuinely agent-incapable defects.
