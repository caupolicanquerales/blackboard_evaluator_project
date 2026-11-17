# Run supervision — seed 002 fresh drain, 2026-11-17 (fix-on-burn, live)

Protocol: board wiped, last project deleted by the operator; pipeline relaunched fresh
(Copilot backend, seed `seed/002_description.md`, watch mode, `python3 -u`, exact PIDs).
Standing order: inspect continuously; on any problem STOP, fix the ROOT, pin it in the
gauntlet, relaunch. Operator addition: watch token consumption — the plan phase was the
flagged burn.

## Preflight

Gauntlet 166/166 + 53/53; Docker up with the springboot MCP image; copilot CLI 1.0.112;
both AST jars built; board folders empty; `projects/` empty; no surviving orchestrator
or pipeline-copilot processes (checked against the 11-16 pgrep-wrapper trap).

## Final board state

| metric | value |
|---|---|
| complete | **63 / 63** (T0 5, T1 19, T2 19, T3 19, T4 1) — zero quarantined |
| delivered suite | **131 tests, 0 failures, 0 errors** (offline `./mvnw -o test`, confirmed by the memoized terminal-suite verdict for the final fingerprint) |
| boot | GREEN — assembly ran `./mvnw -Dtest=TelemetryIngestControllerTest` (8 tests) |
| assembly.detect | **zero problems** on the delivered tree |
| gauntlet | engine decisions **174/174** (8 new pins today), skill scripts **57/57** (4 new) |

## Root causes caught live — each stopped, fixed at the root, pinned

1. **12:02 — every stage-1 TEST task emitted on the PRODUCTION path.** The phase-2
   architect pointed all 19 tester tasks at the unit-under-test's own file (including
   `application.yml` for T1-001). The tester — bound verbatim to "ONE unit test at task
   `path`", "Only `path` writable" — wrote `@Test` classes into `src/main/java`;
   test-scoped deps (JUnit/AssertJ/Mockito/reactor-test) are invisible to the main
   compile classpath, and the import-closure guard killed the drain at the first red
   close-out instead of billing ~100 sessions into it. No emit rule pinned test-artifact
   separation; every previous drain had simply used test paths by habit.
   FIX: plan rule **(w)** refused at emit (stage-1 path colliding with a stage-2/3 task's
   path, board-wide not just pair-identical) + `path` field rule spelled out in the
   phase-2 prompt + `task-decomposition-dag` + architect digests both tiers + README.
   Live-fire, zero sessions: the REAL 57-task draft re-emitted against the gate —
   refused on all 19 T1 ids. Pins **Z1/Z1b/Z1c**. Relaunch 12:19 emitted correct
   `src/test/java` paths.
2. **12:33–12:52 — frozen-test fixture defects (creator/reader split + codec).**
   The tester's persistence-slice fixtures created the H2 substitute over Flyway-JDBC
   with `("sa","")` and read it back through a BARE `r2dbc:h2:mem:///…` URL — H2 answers
   `[28000] Wrong user name or password`; and `H2Row.get(..., Long.class)` on a
   `MAX()` aggregate throws "Cannot decode value of type java.lang.Long" (probe:
   Number/Integer/Object decode fine). A compile-error RED never executes the fixture,
   so both classes surfaced only at the green gate — three units burned their 3-attempt
   budgets on unwinnable contracts before the drain was stopped.
   FIX: `java-junit5` tester skill now pins both laws (same credentials on creator AND
   reader — `;USER=sa;PASSWORD=`; aggregates read as Number, convert in Java). Board
   healed by 3 deterministic fixture edits (invisible to every assertion — proven by the
   unchanged oracle values) + zero-bill replay closes. Pin **P5**.
3. **12:44 — the composition root was delivered in the WRONG package.** The Initializr
   nests the boot class under `<base>.<artifact_under>` (`…telemetry.telemetry_ingestion_processing`),
   while the plan required a single root at `com.pulsestream.telemetry`. The scaffold's
   own smoke test passes (same package — the search finds it), so T0-001 closed green;
   but every `@SpringBootTest` planned in a SIBLING package dies on the upwards config
   search, and component scan silently covers only its own subtree. The container
   checklist had no placement check (its checks were pom-only).
   FIX: `mcp-server-springboot` skill gained **check 7 COMPOSITION-ROOT PLACEMENT** —
   sanctioned relocation (file move + package rewrite, the smoke test stays: upward
   search now finds the root), verified by test-compile, BLOCKED if still misplaced;
   the stack skill states the placement law. Board healed by that same relocation.
   Pin **P7**.
4. **12:46 — "registered only by the wiring factory, no scanning-registration
   annotation" is WebFlux-impossible.** The controller intent pinned a marker-less POJO
   produced by the factory; `RequestMappingHandlerMapping.isHandler` accepts ONLY
   `@Controller` classes (verified against the shipped framework bytecode — no
   `@RequestMapping` fallback, unlike WebMVC): the bean exists, the context boots, and
   every request answers 404. Only the e2e slice (rule (p)) could catch it — and it did.
   FIX: plan rule **(x)** refused at emit (language-gated via the strategy's planned
   language, handler-gated so factory-built WebFilter components — which legitimately
   need no marker — stay exempt): an inbound HANDLER unit forbidding the marker while
   crediting the factory alone names an unsatisfiable mechanism pair. Stack law in
   `java-springboot3`; digest mirror both tiers; README. Board healed by adding
   `@Controller` (the same-name factory @Bean yields to the scanned definition —
   proven by suite + boot, no duplicate mapping) + the 018 trio's intent wording
   rewritten across queue/complete/error records (same repair class as the 11-16
   reserved-segment rename). Pins **Z2/Z2b/Z2c** (b = accepted shape, c = filter
   exemption — the (r)-style gate-vs-gate trap deliberately avoided).
5. **12:46 — the packaged migration directory was EMPTY: the copy duty had no door.**
   The database skill teaches outputs at `services/<slug>/db/migrations/` while the
   stack skill demands the scripts live in the classpath directory the runtime loads;
   the plan resolved the contradiction the way the emit gate ALLOWED — the DB agent's
   intent naming `application.yml` was refused (rule (a): the config unit did not exist
   yet at database-emit time), so the copy duty degenerated to prose in
   `flyway-config.md`. A stage-0 deadlock class (incident #7 family): a requirement with
   no tool path that can hold it.
   FIX: `concrete-database-migration` now outputs DIRECTLY at the runtime-loaded
   directory named by the tech-stack skill (one canonical copy, no copy duty can exist
   unfed); the engine's `_migration_files` gate accepts the packaged layout too (a
   literal folder check would have fatal'd the corrected plan — gate-vs-skill twin).
   Board healed by copying V1/V2 byte-identically into `src/main/resources/db/migration`
   (root scripts stay as the tests' module-root-relative source — same bytes, disclosed).
   Pin **P6**.
6. **13:36 — the base-document probe collided with the config unit's frozen test —
   caught BY THE MACHINE, healed BY THE MACHINE, then fixed at the root.** The
   assembler obeyed fix-menu item 7 (move the H2 literal out of the base document); the
   TERMINAL SUITE GATE immediately found ApplicationYmlConfigTest red, charged the OWNER
   (T2-001, not the bystander assembler), reopened it, and the owner restored the
   contract value at zero billed sessions. Doctrine confirmation: a base value that a
   delivered test asserts verbatim is a PLANNED, DISCLOSED posture (offline boot
   default) — the (r)/N8 "never relitigate a frozen value at a delivered gate" rule
   simply lacked its VALUE twin.
   FIX: `_base_config_problems` now goes SILENT when the delivered test tree witnesses
   the exact value (probe message teaches the exemption), the assembly skill item 7
   carries the exception, README updated. Pins **X5d/X5e** (e = the exemption cannot be
   conjured without the witness). Delivered tree: `assembly.detect` = no problems.
7. **12:46 — one impossible frozen pair, adjudicated:** the e2e test expected
   `MAX(revision) = 1` after two appended revision rows, while the repository's own
   frozen test pins the FIRST revision at 1 (the `>= 1` floor tabled across five
   contracts — the W6 family). Two rows under a composite (device, metric, t, revision)
   PK can only end at 2; the oracle value was the outlier, not the table. Operator
   adjudication `1L → 2L`, disclosed, with the arithmetic proof.

## Economics (the token watch)

* Whole day, both drains + repair cycles: **56 billed sessions, 7.43 M input / 0.22 M
  output tokens, ~24.8 K input per turn** — for 63 units (~0.9 sessions/unit, in line
  with the 11-16 second drain's 0.92).
* Over-budget sessions: 4, ALL in the plan phase (the two doomed/lucky architect runs
  19/12 and 16/12 calls, the database 16/14, plus the first drain's architect).
  `session_audit` attributes the excess to scope-escape calls the prompts already ban
  (skills_folder_listing ×4, board_bulk_read ×16, agent_scratch ×22, src_full_read ×28);
  the hard-kill watchdog bounded every one, and enlarging the fixed prompt to re-ban
  what is already banned would raise the per-turn floor of every session — the opposite
  trade. No mechanical gap found: watched, not burned blind.
* Largest single session: **537 K** (the first doomed architect) / 502 K (the accepted
  re-decomposition) — the plan-phase transcript is and remains the burn; every wave
  session ran 3–14 calls inside budgets (coder batches 8–11 of 46).
* All six healing classes closed at ZERO billed sessions after their root fix:
  `restored re-verification: green, no session billed` ×2 (config + audit adapter),
  the fixture/codec/relocate board edits replayed green, and the terminal suite gate's
  own reopen→owner→restore cycle billed nothing.
* Every deterministic verification (full offline suites, decode matrix, credential
  matrix, handler-registration bytecode check) cost zero agent tokens.

## Residuals (named, not hidden)

* The plan phase keeps exceeding its call budget on this backend via scope-escape
  calls (watchdog-bounded, auditable, ~150 K worst-case/session overhead). The honest
  next lever is per-turn transcript size in the architect prompt, not more prohibitions.
* `revision (>=1)` floor vs a future e2e that re-derives numbering wrong: today's (7)
  was adjudicated by arithmetic; an emit-side cross-test value check remains open
  (same family as the reserved-word-inside-signature residual from 11-16).
* The same-name factory @Bean for the marker-annotated controller is inert-but-present
  (the scanned definition wins per Spring precedence). Legal, tested, disclosed — the
  clean future shape is stereotype-only for handlers, which (x) now steers plans toward.

## Watch notes (today's additions)

* An orphaned copilot child survives the orchestrator kill twice today (12:52, 13:4x):
  kill the exact PIDs parent-first, then re-`pgrep -af "copilot -p"` excluding the IDE
  runtime, and kill stragglers explicitly (the 11-16 rule, still load-bearing).
* `pgrep -f orchestrator_github` matched a transient shell wrapper (status.py reported
  PID 116403 as an "orchestrator process" that had already exited) — same self-match
  trap as the 11-16 11:47 double-drain warning; verify with `ps -p <pid>` before acting.
