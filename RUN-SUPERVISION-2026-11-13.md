# Run supervision — seed 002 fresh validation drain, 2026-11-13 (fix-on-burn, live)

Protocol: board wiped, project deleted by the operator; pipeline relaunched fresh
(backend: GitHub Copilot CLI, seed `seed/002_description.md`, watch mode). Standing order:
inspect continuously; on any problem STOP the process, fix the ROOT, pin it in the gauntlet,
relaunch. The morning's engine/skill corrections
(`PROJECT-INSPECTION-2026-11-13.md` §"Implementation record") were validated under live fire.

## Final board state (14:05 — drained clean, nothing hanging)

| metric | value |
|---|---|
| complete | **42 / 42 tasks** (T0 5/5, T1 12/12, T2 12/12, T3 12/12, T4 1/1) — **zero quarantined** |
| full frozen suite on the delivered tree | **60/60 green, 0 failures, 0 errors** (`mvn -o test`, deterministic, zero sessions) |
| delivered tree | compiles (`[verify] passes typecheck` at 14:01), **boots green with the REAL context** (entry at `com.blackboard.telemetry`, ancestor of all code and tests — no scan directive needed) |
| config artifact | multi-document `application.yml`: base + `test` profile (H2 r2dbc + `flyway.enabled: false`) — the F5 shape landed |
| provider closure (F4) | every injected collaborator self-registers (@Service/@Component/@Repository/@RestController) — the DI graph constructs at boot |
| billed sessions whole day-13 run | **~34** (launch A 25 + fix round B/C 9) across 42 units (~0.8/unit) — yesterday: 144 premium requests for 96 |
| idle burn | zero: every stop was operator-initiated to fix a root cause, never a spin; replay-closes billed nothing |

## The morning's corrections, validated live

* **Plan-time prose-vs-table refusals (e)/(f):** the architect emitted the whole 12-unit plan in
  one accepted batch — **zero rejects, zero rewrites, and no impossible pair exists in the plan**.
  The correlation duty came out as ONE middleware unit (no utility-class collaborator at all);
  the validator replay over the live plan reports 0 hits (and, on the OLD yesterday-plan, it
  would have refused 11 intents — the class of defect that froze 2026-11-12 never entered the board).
* **WOVEN-CLEAN / sibling-gate / zero-bill deferral:** the first quarantine round
  (T2-001/009/010) never holed the tree, never charged bystanders, and closed repeats at zero
  sessions — twice (`replay repeats an already-informed failure: closing out with zero sessions`,
  then after the real fix: `restored re-verification: green, no session billed`).
* **Re-pin scaffold:** parent `3.5.16`, `<java.version>21</java.version>` honoured again.

## Root causes caught live — each stopped, fixed, pinned

1. **13:33 — the drain finished 41 units and exited having NEVER BOOTED the application.**
   `assembly.ensure_tasks()` ran once at launch, when `services/` did not exist (the scaffold is
   created DURING the drain), so no T4 was ever queued — and my first terminal-tree report only
   scanned completed T4 records, inheriting the blind spot. Yesterday's T4 existed only because
   that launch began over a leftover tree.
   FIX: `ensure_tasks()` re-runs EVERY watch pass + a post-pass reschedule with one extra drain
   for single-pass runs (idempotent, zero sessions); `_terminal_tree_report()` became
   board-driven and prints `[tree] <slug>: RED - NEVER BOOTED` when a domain has no completed
   boot — a silent lie-exit is now impossible. Pin: **T1–T5**.
2. **13:41 — the multi-document YAML config was UNWEAVABLE.** T2-001 burned its 3 attempts + a
   grant because `_text_write_exec.py` validated payloads with `safe_load`, which rejects the
   `---` second document the plan mandates and the frozen test asserts. The tool made a correct
   plan impossible — yesterday's cause-#5 class, YAML half.
   FIX: validation now `safe_load_all` (materialized) — the exact surface SnakeYAML/Spring parse.
   T2-001 went `[done]` in ONE informed session afterwards. Pin: **K5/K6**.
3. **13:45 — the coverage rule accepted a HOLLOW FIX.** With T4 reopened, the assembly agent
   declared `scanBasePackages` (my rule #1 accepted the marker), the smoke test booted green —
   while both `@DataR2dbcTest` slice units stayed red forever: `Unable to find a
   @SpringBootConfiguration by searching packages upwards` — package-upwards discovery IGNORES
   scan directives, so the marker can only ever be a half fix.
   FIX: `_coverage_problems` gained a second, NON-WAIVABLE half: every context-discovering test's
   package must contain-or-be-below the entry package; the only repair is moving the composition
   root to the shared ancestor. The agent (attempt 2, fed the structural reason) executed exactly
   that — and the two slice units then re-verified **green at zero sessions**, because the world
   they were failing on had moved. Pin: **S4/S5**.
4. **13:51 — the path-guard quarantined the CORRECT fix.** After the move, stage-4's recorded
   `path` no longer existed and `agent finished but <file> was not created` fired — the guard
   that means "the session must write its file" for tester/evaluator/scaffold judged assembly,
   whose contract is the boot gate alone.
   FIX: `_missing_artifact_problem` exempts stage 4 (and keeps judging every other stage).
   Pin: **U1/U2**.
5. **13:51 — re-emitting an id left a zombie quarantine.** The per-pass reschedule (fix 1)
   re-issued T4-001 with the FRESH entry path (that is what healed the run), but the old
   `error/T4-001` record survived next to `queue/`→`complete/` — one id, two records; a relaunch
   would have let producers resolve to the zombie.
   FIX: `emit_tasks` supersedes the same-id error record on landing (`[emit] superseded stale
   quarantine record`). The zombie on the live board was cleared as the documented remedy.
   Pin: **U3**.

## Economics of the day-part (why nothing was burned twice)

| round | what ran | billed |
|---|---|---|
| launch A 13:06–13:33 | discovery/mapping/strategy/DB/scaffold/12 testers/12 coders/evaluators | 25 sessions, 2.83M in — the whole plan phase green-first-pass |
| stop → fixes 1+2 | engine + tool edits, gauntlet 48+96 | zero |
| launch B 13:40–13:45 | T2-001 one session → done; T2-009/010 replayed-closed free; T4 first boot session (marker fix) | ~5 |
| stop → fix 3 (+4,5) | slice rule, guard, zombie, gauntlet 48+101 | zero |
| launch C 13:49–13:56 | T4 attempt 1 rejected by UPWARDS gate, attempt 2 moves root, T2-009/010 restored green FREE, T3 mirrors | ~9 |
| 14:00–14:01 | zombie cleared; zero-session verify pass: typecheck green | 0 |
| final | 42/42 complete, 0 quarantined, 60/60 suite | — |

Every unit that was red for a TOOLING reason went green without a single new coder session once
the tool/plan was fixed: the engine's replay machinery (yesterday's fixes) did exactly what it
was built to do — the waste today was confined to the ~2 sessions spent BY the defective tool
before each stop, never repeated after.

## Residuals (named, not hidden)

* Datasource↔migrator alignment (F5 adjacent: flyway enabled in the base document, no
  `spring.datasource.url`) remains a SKILL rule only — no engine validator; the JDBC-embedded-H2
  boot happened to tolerate it (`value` parses over JDBC), the production-DB migration fiction
  risk stays on the operator checklist.
* F9 (unsubscribed stream ports) did not recur in this decomposition — no zero-subscriber stream
  port was planned; rule (i) now prevents the shape.
* Slice markers stay a documented escape for MAIN visibility only; the upwards-discovery half is
  deliberately unwaivable.

## Gauntlet

Grew to **48 skill-script + 101 engine-decision checks** (new: K5–K6, T1–T5, U1–U3, S4–S5 +
the morning's G21–G24/A27/A28/S1–S3). All green after every single edit; every production defect
observed today is pinned by at least one deterministic case.
