# Project Inspection — 2026-11-26 (seed 003, `conversational-agent`)

Purpose: validate the orchestrator and the split planner on a fresh AI-domain seed,
live, under supervision — stop on any problem, fix the root, relaunch, stop after the
tasks are generated. Outcome: the plan completed **3 minutes 26 seconds** after the
phases were all warm, with **3 billed sessions** (1 draft + 2 routed repairs) and zero
manual intervention in the final pass — after a day in which twelve root causes were
found and closed at the layer that produced them, and the engine was restructured into
importable families with the full gauntlet green (179 + 372).

---

## §1 — Live supervision: incidents stopped and fixed at the root

| # | Symptom (live) | Root cause | Fix (home) |
|---|---|---|---|
| 1 | 3 subdomains minted from one small service; `ai_directive` duplicated; access policy restated twice; a sync read faked as an event handshake | discovery laws split on *signals* with no cohesion counterweight; directive trigger said "the domain", ambiguous per-slice; no cross-cutting-policy home; events-only interaction vocabulary | cohesion guard, per-slice directive attribution (summarization added), one-home-per-access-policy, `reads` channel as a first-class field — `domain-boundary-discovery` SKILL + profile; `reads?` in the writer schema (`task_creation`… `writer_file.py`); verified: next cold discovery produced ONE subdomain, 3 contexts, clean directives |
| 2 | context map shipped dangling publishes as note-flags; `Conversation Memory -> external` ACL edge pointed at the provider | flag-only validation; direction tied to caller instead of supplier | WIRING CLOSURE (wire-with-quoted-phrase or adjudicate planning-blocking — a bare flag never ships), supplier-direction law, read-after-event staleness posture — `domain-context-mapping` SKILL + profiles; deterministic external-edge refusals in `writer_file.py` (ACL/OHS shapes); verified: regenerated map zero bare flags, edges supplier-oriented, postures named |
| 3 | planner session killed at the hard cap (33 calls) ONE lint round from done; its COMPLETE draft was discarded and the whole session re-billed on relaunch | budget calibrated for logical reads, not windowed `view` paging + one 40KB draft decode; `draft_is_fresh` required a sidecar only successful claims wrote | single concatenated brief (stack skills inlined, ONE full read), 3-lint cap, measured budget 22/cap 44; `draft_state` = `unjudged` → the claim gate JUDGES dead-run bytes for free — `prompts.py`, `settings.py`, `plan_drafts.py`; verified: a 95%-done draft resumed through the gate, repairs took it home |
| 4 | two SKILL.md edits during live repair rotated every draft hash → 8 full drafting sessions re-billed; a *rejected* draft relaunched as "fresh — claimed without a session" (re-repair storm each launch) | freshness hashed LAW PROSE (SKILL.md) but not the LAW CODE; the claim sidecar recorded no verdict | FACT/LAW/VERDICT split: facts (strategy+specs) hashed; law = explicit `LAW_VERSION` → a law move means FREE revalidation (`unjudged`), never re-draft; verdict + `attempts` stamped at claim; `rejected` escalates to ONE re-draft; `exhausted` after `MAX_REDRAFTS=2` stops loudly — `plan_drafts.py`, `plan_flow.py`; verified 7/7 transitions + real board |
| 5 | batch refused 22 routed lines; every repair billed on progress; then fatal "still refuses after 4 round(s)" — with 4 buckets the pre-R3 global cap (`2×2`) spent itself in the FIRST sweep before any bucket got its promised second round; the final join refusal had no `ERR` prefix and routed to NO bucket (blind fatal) | routed semantics arrived (R3) while the global cap kept whole-batch arithmetic; router recognized only `ERR`-prefixed lines | cap derived from the per-bucket guarantee `2 × (contexts + 1)`; id-bearing and `slug:`-bearing lines route (cross-context → domain, repair scoped to the NAMED files only); verified: next rejection round converged after 2 sessions |
| 6 | queue had NO scaffold task at all (unbootable plan) | the manifest prepass built its used-id set from raw numbers while comparing full ids — it silently OVERWROTE the strategy's scaffold at `T0-001`; the gap-gate fallback then miscredited the manifest as a scaffold; killed strategy sessions refused to "duplicate" it (shape, not marker, matched) | collision fixed + never-overwrite guard; fallback excludes `build-manifest` (identity = EXPORT MARKER); engine HEALS damaged stage-0 boards from the agent's own draft (renumber, re-queue, re-point manifest) — `ddd.py`, `plan_board.py`; marker law taught in both strategy carriers; verified live: `[heal] scaffold task T0-006 re-queued … (zero sessions)` |
| 7 | stack facts lived in FIVE private copies (verification if-chain, test_gate shape chain, closure detect chain, assembly marker tuple, ddd `pom.xml` fallback) — every incident added a branch to whichever copy it touched; the migration gate hardcoded Flyway naming (`V*__*.sql`) as BOARD law (would fatal a lawful alembic/TypeORM plan) | no single toolchain registry; stack vocabulary above the adapter line | `stacks.py` — ONE ecosystem registry (markers, wrappers, verify commands, scoped-test shapes, closure dispatch); all five consumers read it; migration check became RECORD-driven (a DB task's declared path exists); golden-verified byte-identical decisions |
| 8 | orphan risk on kill: death-shim flag raised BEFORE registration (a worker-thread adopt silently disabled the handler forever), plus a Popen→adopt signal window | `agent_runners._install_death_shim` ordering; entry-time adoption race | install at import (main thread), flag flips only on success, `_SHUTTING_DOWN` re-check kills children adopted inside the window — `agent_runners.py` |
| 9 | "the golden passed" — while `run()` actually crashed at `docker_gate()` (hoist left call sites zero-arg) because BOTH harness runs died instantly on a bad relative seed path and compared one-line fatal outputs | a golden that does not assert DEPTH proves nothing | harness rebuilt: absolute seed, depth assertion (`[plan] architect writing application tasks` must appear), serial-vs-parallel multiset equality; the hoist bug then surfaced and died on the FIRST REAL LAUNCH (stopped, fixed, relaunched — no session wasted) |

## §2 — Structural re-org (maintainability, the "spaghetti" debt paid)

3,239-line `task_queue.py`, 1,149-line `tasks.py` and 1,043-line `pipeline.py` were split
into four family folders, each keeping its root script and a README with the failure-home
map; `family_paths.py` is the one bootstrap (every module imports `settings` before any
family name, so flat imports survive):

```
orchestrators/
├── orchestration/   pipeline.py · cli_args.py · run_phases.py · plan_gates.py · plan_flow.py · drain_flow.py
├── task_contract/   tasks.py · task_identity.py · task_signals.py · task_rules.py
├── task_creation/   task_queue.py · plan_drafts.py · plan_board.py · plan_wiring.py · plan_laws.py
└── backends/        copilot_backend.py · opencode_backend.py
```

- Public surfaces unchanged: `pipeline.X` / `tasks.X` / `task_queue.X` re-export everything
  callers (backends, assembly, closure, tdd_engine, gauntlet) already used — zero caller edits.
- Zero-behavior proof per split: byte-identical goldens (record digests, emit-refusal sha,
  mock-run stdout multiset); the pipeline golden additionally now asserts DEPTH (§1.9).
- The gauntlet was re-homed with the split (paths, `src_run` → `_phases_src()`, the new
  `route_refusals` tuple, `READ EXACTLY THESE` → `INPUT - ONE FILE, ONE FULL READ`,
  SP8 rewritten to the FACT/LAW/VERDICT contract with a new `LAW_VERSION→unjudged`
  assertion, budgets 14/22). Two carrier regressions the gauntlet caught were fixed in the
  SOURCES, not silenced: the relationship enum deleted from the mapping profile during a
  lean pass (restored to both mirrors), `pom.xml` leaked into stack-agnostic strategy
  carriers (de-stacked). Final: **GAUNTLET ALL GREEN (179 skill + 372 engine)**.

## §3 — The parallel planner (the decode-bound bottleneck)

Measured wall anatomy of a planner session: ~10% tool calls, **60–75% a single create turn
decoding 40–85KB of JSON**, ~15–25% per-turn transcript prefill — the old split optimized
call COUNT (the cheap axis) and the concatenated brief even grew per-turn bytes. The
structural lever was the pin law: contexts serialize because sibling ids do not exist until
claim. Solution — siblings pin by ANCHOR, the engine binds ids:

- `{type, context}` dependency entries accepted by the schema (`task_identity`), taught by
  the brief (`prompts`); bounded contexts draft CONCURRENTLY after the serial root pass
  (`settings.PLAN_PARALLEL`, thread-capped waves, disjoint files); `plan_wiring.resolve_sibling_anchors`
  binds every anchor to the RENUMBERED id before the batch and mirrors the pair edge onto
  the test side; claims/emit/repair stay serial. `PLAN_PARALLEL=1` is byte-identical to the
  serial flow (proved: output multisets equal).
- Fixture-proven: 3 threads overlap (1.94s vs 3.6s+ serial), anchors bind across collision
  renumbering, `attempts`/verdict ladder intact.

## §4 — Seed 003 plan: result and economics

```
queue 222 = 6 stage-0 (scaffold, manifest, 4 migrations) + 72×(T1 tester + T2 coder + T3 evaluator)
drafts: 4 contexts, verdict clean, law 2026-11-26.1, attempts 0
audited clean: graph, pair identity 72/72, floor 13/13 single-owner, duty closure,
               singletons, anchors bound, offline stub + golden set + boot posture, literals
final plan pass: 14:22:08 → 14:25:34 = 3m26s, 3 billed sessions, auto-stopped by --plan-only
```

## §5 — Second plan audit: four findings, four roots

1. **D1 — 3 of 8 authorization rows (`AZ-02/03/08`) reached NO unit.** The claim gate
   verified DUTY `spec_ref`s; rows discharged only through another duty's `covers` were
   scheduled at spec level and invisible at plan level — an unspoken IDOR rule ships
   unenforced. **Root:** a row layer in `_security_claim_errors` — every
   `authorization_matrix` row must be spoken, with the covering duty's capability, at the
   unit that IS its surface entry; measured on the live board: fires on exactly the three
   holes.
2. **D2 — covered rows' `test_duty` cases died at the digest join** (`SI-07` arrived with
   `test_duty: None` while `AZ-08` carried the full cross-owner case): the machine enforced
   "what is written", and the duty had written nothing. **Root:** the slice join inherits
   `test_duty`/`surface` from covered rule entries (provenance stamped `test_duty_of`).
3. **D3 — the map's adjudicated serialization posture reached no unit** (strategy carried it
   in `risks`; DG6 rightly bans strategy risks from slices for token reasons; the brief
   channel was blind). **Root:** the phase-2 digest carries `commitments` — risk lines split
   by VOICE ("accepted:" = exposure, never planned; anything else = behavior that must land
   on a unit or be reported as a phase-1 gap) — DG6's audit honored, the invisibility closed.
4. **D4 — one trust domain, two credential stores** (`chat.service-credentials` vs
   `chat.history.service-credentials`). **Root:** security-strategy skill law — one principal
   class + population = ONE owning row; siblings reference the home (split-brain secrets).

Budget discipline held while adding them: security rulebook back to 996 words (<1000 cap),
no line >200 chars, DAG skill within its scannability caps — the gauntlet's own checks
forced the compression, then went green.

## §6 — Residuals (named, not hidden)

- **The queued plan predates D1–D3**: `--replan conversational-agent` is the designed path
  to regenerate it under the row-closure + commitments + trust-domain laws (~15 min,
  parallel wave active). Not yet run — the laws, not the board, were this day's scope.
- **Per-turn payload** is the honest performance lever left after parallelization:
  the concatenated brief grows 83–120KB; section-slicing the inlined stack skills to
  `Record keys`/`Scaffold facts` is identified, not yet done.
- **The execute side has not drained seed 003** (stages 1–4: TDD loop, assembly, terminal
  gates) — verdict contract O1–O5 still awaits its first live drain on this seed.
- **AST extractor tooling is Java-only** (`.env` `AST_TOOL_ROOT`): real external dependency
  of the multi-stack promise, untouched today by design.
- `MAX_REDRAFTS`/exhaustion, sibling-anchor resolver, `resolve_lost_scaffold` and the row
  layer are unit/fixture-proven but not yet gauntlet-pinned — candidates for the next
  "no merge without a case" pass.

## §7 — Day ledger

- Billed sessions today (all phases, all passes, incl. the two invalidation storms §1.4):
  ≈ 26 planner-family + 6 spec/strategy + 3 DDD sessions. The FINAL pass: 3.
- Engine files: 16,774 lines across 4 families + shared kernel; every split golden-verified.
- Gauntlet: 551 cases, all green; 2 carrier regressions caught by it were fixed in sources
  (enum restoration, de-stacking), 1 expectation (SP8) rewritten to the new contract WITH a
  stronger assertion than before.
