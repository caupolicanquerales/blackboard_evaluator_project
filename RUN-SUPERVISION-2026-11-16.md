# Run supervision — seed 002 fresh drain, 2026-11-16 (fix-on-burn, live)

Protocol: board wiped, project deleted by the operator; pipeline relaunched fresh
(GitHub Copilot CLI backend, seed `seed/002_description.md`, watch mode). Standing order:
inspect continuously; on any problem STOP the process, fix the ROOT, pin it in the
gauntlet, relaunch.

## Final board state

| metric | value |
|---|---|
| complete | **71 / 71** (T0 5, T1 22, T2 22, T3 21 + T4 1) — zero quarantined |
| delivered suite on the final tree | **145 tests, 0 failures, 0 errors** (engine memoized wave verdict, confirmed by a fresh `./mvnw -o test`) |
| boot | GREEN — assembly gate re-checked by the engine; smoke class inside the 145 |
| tree | compiles; config keeps the frozen contract (`spring.flyway.url` contains `${TELEMETRY_DB_URL`) AND boots without env vars (H2 fallback default) |

## Root causes caught live — each stopped, fixed, pinned

1. **09:50 — phase-order hole killed the architect.** The step-log CLAIM gate (layer 2)
   demanded stage-2 claims while the phase-1 architect could only emit the stage-0
   scaffold task: an impossible refusal. The architect burned 19 calls (budget 12) and
   the run died `[fatal] no scaffold task`.
   FIX: claims are checked only once the project HAS stage-2 tasks (queue or batch);
   the observability FLOOR stays unconditional at every emit. Pin: **V6/V6b/V6c**.
2. **09:50 (same incident) — the resume shape could not heal.** Strategy on disk + no
   scaffold task made every relaunch skip phase 1 and die at the fatal again.
   FIX: `pipeline._strategy_phase_gaps()` — a strategy without its stage-0 task re-runs
   phase 1 (the agent's second attempt emitted the real T0 in 8 calls, zero refusals).
   Pin: **V9**.
3. **10:15 — reserved word as a package segment.** The architect planned the driver
   layer `...intake.interface` / `...observability.interface` (`interface` is a Java
   keyword): the weaver can never render the package line, the frozen tests can never
   compile. 3 units + 3 evaluators quarantined, ~6 bounce/attempt sessions on an
   unfixable contract, and T2-015 (observability) was heading for the same wall.
   FIX: emit gate `LANGUAGE_RESERVED_SEGMENTS` refuses `ast_hints.package` / `export` /
   `path` segments reserved IN THE STRATEGY'S PLANNED LANGUAGE (data-driven per
   language: Java/TS/JS/Python/Go; contextual words like `record` stay legal; no
   strategy or unknown language skips). Board healed by renaming the segment to
   `api` across the 12 task records, 4 frozen test files, payloads and red/AST records.
   Prompts + pin: **V10/V10b/V11/V11b/V12/V12b**.
4. **10:30 — Maven `-q` green is silent.** A recorded scoped command with `-q` exits 0
   printing NOTHING on success; the runner's silent-exit-0 guard classified a green
   10-test class as `not_run` → fatal abort. The proof exists on disk — Surefire writes
   its XML reports even under `-q`.
   FIX: run-test-tool falls back to fresh `TEST-*.xml` reports (aggregated counts,
   per-class verdicts, failure entries; `evidence: surefire-xml`); strict `>= started`
   mtime (a tolerance window swept the PREVIOUS unit's report into the verdict —
   the "17 tests" miscount, pinned). Pins: tool suite + 3 new CLI cases.
5. **10:39 — PostgreSQL-dialect migration vs plain H2.** Slice tests execute the
   migration files VERBATIM against an H2 URL frozen inside the test; `TIMESTAMPTZ`
   (unknown type), unquoted `value` (H2 reserved) and `;` INSIDE COMMENT string
   literals (the test splits on `;`) killed T2-011/T2-014 with defects no coder
   payload may repair.
   FIX (operator scaffold repair + skill rule): portable `TIMESTAMP WITH TIME ZONE`,
   quoted `"value"` in DDL and in the T2-011 payload, semicolon-free comment literals;
   the `java-springboot3` tech-stack skill now names the type/portability rule.
6. **10:44–10:52 — cross-stage regression with NO gate left to fire.** The T3-007
   evaluator's `TelemetrySample` refactor and the T4 assembler's `flyway.url` rewrite
   broke PEER frozen tests after the last wave ran; the board fell silent at queue 0
   with a red delivered suite (the 2026-11-12 exit-lie family, new door).
   FIX: **terminal suite gate** (`tdd_engine.terminal_suite_gate`, run by the pipeline
   on every quiet board): full-suite verdict memoized per tree fingerprint (zero builds
   while the tree is unchanged), red class → its producing unit via the stage-1 pair
   (stem equality), PLUS main-file blame via `error_locations` (a red test often lies in
   a collaborator's file — the validator was charged for the record's guard), ownerless
   integration reds → the domain's stage-4 task (once per tree state), quarantined
   owners left to the retry path, everything else NAMED on `[suite ]` lines. Healed
   live: T2-003/T2-016 (config + use case) and the final T4 cycle. Pins: **V13/V13b/
   V13c/V13d** (123/123 engine + 48/48 skill-script).

## Economics

Planning (discovery/mapping/strategy/DB/scaffold) ~9 sessions; 22 testers + 22 coders +
21 evaluators + 2 assembly cycles ≈ 40 sessions; every tooling-caused red closed at
ZERO billed sessions after its root fix (replay/re-open machinery). Largest single
session 397K input (the doomed first architect — the incident this report exists for).

## Residuals (named, not hidden)

* `TELEMETRY_DB_URL` feeds BOTH `spring.r2dbc.url` (r2dbc scheme) and
  `spring.flyway.url` (jdbc scheme) — the frozen config test's substring contract
  (`contains "${TELEMETRY_DB_URL"`) FORCES the single-variable shape; production must
  set two differently-prefixed URLs in one variable or the plan's test pair must be
  corrected. The evaluator recorded the finding; the engine cannot edit a frozen
  contract. Candidate for the next plan-validity rule (config key whose readers demand
  different URL schemes must pin distinct variables or a derivation duty).
* `src/test/resources/application.properties` (profile activation route) is still
  absent — boot resolves through the base fallbacks instead. Workable, but the
  documented route is `spring.profiles.active=test`.
* Reserved-segment gate checks `package`/`export`/`path` only; a reserved word inside
  a method signature's parameter type spelling would still only die at weave time
  (bounded by the bounce caps).

## Watch notes

Launch the orchestrator via `python3 -u` (the drain log must stream — buffered stdout
hid the first 09:50 fatal until after exit). Kill the orchestrator with an exact PID
(`pgrep -f "python3 -u orchestr"` can match the invoking shell wrapper and double-drain;
on 11:47 a surviving old process raced a new one on the same T4 for ~60s — the loser's
orphan copilot child was killed explicitly; no double charge: the duplicate session was
never granted the board's ledger).

## Second drain (13:54–15:33, operator-wiped board — the SAME day, engine carrying this morning's fixes)

Fresh plan: 26 units, and the new emit gates proved themselves: the decomposition was
**accepted first try** with every stream source pinned by a consumer, every signal
return carrying TRUE/FALSE semantics, and the metric taxonomy back to the seed's
domain (the morning's (k)/(l)/(m) rules steered the architect away from F1/F2/F4).
Three incidents, each stopped, root-fixed, pinned:

7. **14:01 — stage-0 deadlock: requirement without a sanctioned tool.** The T0 intent
   demanded a surefire test-run guardrail and the test-profile activation file; the
   generator cannot emit them, `repin-parent.py` could not add them, and hand-editing
   the pom is forbidden by design — so the container agent correctly reported BLOCKED
   and delivered NOTHING: `[fatal] pom.xml was not created`. The plan had made the
   scaffold unsatisfiable by its own tooling.
   FIX: `repin-parent.py --surefire-timeout` (the sanctioned, verified, self-reverting
   pom edit now carries the capability — proven on the real generated tree and applied
   by the retried session: delivered pom shows `forkedProcessTimeoutInSeconds>300`);
   check 5's wording disambiguated ("the container creates it" → YOU, the agent, with
   the exact shell line); BLOCKED's meaning narrowed (true catalog gap only). Pins P1–P4.
8. **14:43–15:03 — prose-only constructor invariants (two victims, one root).** The
   domain record enforced `revision >= 1` — but the bound lived ONLY in the producer's
   intent prose; the constructor's table `semantics` was None, and the collaborator
   table injected into consumer testers never carries prose. Six frozen fixtures across
   five units fabricated `revision=0` and died in their own helpers before touching the
   unit under test (the coder could not fix them; the tests are FROZEN).
   FIX: emit rule — an intent stating an argument-range invariant (`revision (>=1 …)`)
   is REFUSED unless the constructor's table entry spells it in `semantics`; the
   collaborator table now carries `semantics` (delivery fixed — it was dropped on the
   way to the tester); tester skill law: table semantics bind fixture values. Board
   healed by 6 fixture edits (0→1, invisible to every assertion) + zero-bill replay
   closes. Pins **W6/W6b**; the offline sweep proved the rule fires exactly on the one
   real offender among 26 units.
9. **15:18 — evaluator closed a type; the consumer paid.** T3-004's evaluator sealed
   `TelemetryIngestionEvent` (engine_diff recorded it) — Mockito cannot stub a sealed
   interface, so the subscription unit's seven `@Mock`-based tests died, its evaluator
   correctly refused to refactor over red, and the unit quarantined: charged to the
   victim, which can edit neither its frozen test nor the foreign modifier.
   FIX (three layers): the runner normalizes the gap to `mock_impossible` + per-failure
   `mock_type` (Mockito phrasing stays inside the tool); the engine DEFERS the mocking
   unit and REOPENS the producer that closed the type, and the terminal suite gate
   charges mock-victim classes to the closer, never the stub-er; the java-springboot3
   skill now states the mockability law (sealed ⟂ @Mock). Board healed by unsealing
   the source — the T2-004 payload never wrote `sealed` (only the evaluator's edit did),
   so the delivered tree now matches the recorded contract exactly. Pins **W7/W7b/W7c**
   + R-mock.

Final: **84/84 units, queue 0, quarantined 0; terminal suite verdict 186/186 green
with the boot smoke inside it** — certified by the gate that was born from this
morning's incident #6. Day totals across both drains: ~120 sessions for 155 units.

## Third drain (16:43–19:27, operator-wiped board — the engine carrying ALL of today's gates, live fire on a 32-unit plan)

The regenerated plan proved the gates steer: phase-2 batch **accepted first try** with
every stream source pinned by a consumer, every signal return carrying TRUE/FALSE
semantics, seed vocabulary and ranges verbatim, TWO end-to-end request-path slices and
dedup language on the ingress chain (the (k)–(q) rules worked as designed, not as
luck). Four new root causes, each stopped, fixed, pinned:

10. **16:53 / 18:11 — the weaver could not derive packages for `src/test/java`**
    (`PayloadNames.JAVA_SOURCE_MARKER` hardcoded to `src/main/java`): a created
    support class under the test root landed with NO package → the frozen e2e test
    that imports it died on `duplicate class` / `cannot access`. FIX: derive from any
    `src/<config>/java` source root. Live-proofed: the original failing payload now
    produces a correctly-packaged file. Pins V10-style + weaver JUnit (packageOf).
11. **17:16–18:24 — dead compact constructors, synthesized by the tool itself.**
    `declaresConstructor` recognized only `ClassOrInterfaceDeclaration`, so a
    method==type-name payload on a RECORD fell into the method splice and the tool
    manufactured `public void Name(...)`: legal Java, never runs — SIX records shipped
    silently dead guards, and the units burned their attempt budgets on a defect the
    payload never even contained the text of. A first fix wrapped everything compact
    and re-erred on canonical bodies (`cannot assign final variable`); the final rule
    classifies: body assigns `this.x =` → canonical constructor, else compact; plus a
    rung-level `rejectDeadConstructor` bounce for the members-text shape (attempt-free,
    message teaches the spelling). Weaver JUnit now 23/23 + 3 new cases.
12. **18:24–19:17 — a gate-vs-gate livelock CREATED BY MY OWN MORNING FIXES**: the
    N8 assembly probe (refuse `filesystem:db/migrations`) collided with the config
    unit's FROZEN test that pins exactly that string — the assembler was ordered to
    break a contract it must not touch, and T4 died 3/3 on an unsatisfiable pair.
    Doctrine confirmed the right placement: portability is an EMIT rule (refuse a
    config UNIT that pins CWD-relative locations when the scripts live in the project)
    — enforced where the architect can still fix it, never relitigated at the
    delivered gate. Assembly check removed; plan rule (r) + pins X5c/X6/X6b shipped.
    Same section: the terminal suite gate read a quarantined owner as "NO producing
    unit" because its owner map skipped error/ records (X7 pin, include_error fix).
13. **19:25 — the runner misclassified a 258/258-GREEN suite as assertion_failure**
    because its loose assertion-vocabulary swept application LOG lines into the
    failures list while the toolchain's own counts said 0/0 — and the terminal gate
    faithfully reported the fake tree-wide red with no owner. FIX in classify():
    a clean exit-0 run with zero counted failures/errors is never red for
    test-name-less noise entries; contaminated memo purged (exactly 1 entry),
    rebuilt verdict: passed 258/0/0. Pins: tool-suite cases.

Final: **102/102 units (T0 5, T1 32, T2 32, T3 32, T4 1), queue 0, quarantined 0,
fresh offline suite 258/258 green with the request-path e2e slice inside it, boot
gate green, terminal-suite verdict passed for the current fingerprint.** One operator
tree edit, disclosed and same-class as #8's fixture repair: the e2e test had
fabricated sourceKind "BLE" — a transport label owned by no contract (the enum's
frozen test and the seed both name device classes) — 7 literals corrected to the
enum's own values; the slice then went 8/8 green and the units replay-closed at
zero billed sessions. Day totals across all three drains: ~250 sessions for 257
units, every tooling-caused red closed at zero bill after its root fix.

## Post-drain (closed 2026-11-17, 11:18): PART III residuals G2/G3/G4 fixed at the ROOT — plan rules (s), (t), (u)

Method (standing): the evening inspection of the third drain's artifact named four
residuals; G1 was already closed the same day by plan rule (r) (item #12 — a
re-emitted plan cannot reproduce the pair). G2/G3/G4 were factory gaps, not tree
gaps, so the fix went to the skills/emit tier only: ZERO edits to the delivered
artifact (its frozen tests and README stay as delivered; the residuals remain
truthfully disclosed there as known limitations). Doctrine honored throughout:
the architect tier stays stack-agnostic — the new rules speak of identity axes,
mechanism tokens and counting meters and carry the STRATEGY'S OWN WORDS into the
plan's duties; every concrete name (`io.micrometer:context-propagation`,
`Hooks.enableAutomaticContextPropagation()`, Micrometer counters) lives only in
the tech-stack skills.

14. **(s) — the correction axis (G2).** The morning's rule (q) was HONORED by the
    third drain and that is exactly how the residual died: a natural identity that
    EXCLUDES the value reclassifies every value-correction as a duplicate no-op,
    while the seed says "corrections append new event revisions". The root cause
    sat two tiers upstream: the boundary file carried the corrections question as
    `Open question`/low-confidence `Ambiguity`, and `domain-driven-architecture`
    said "open questions recorded, never silently decided" with no operational
    meaning — decomposition answered the question by omission and no file on the
    board ever said so. FIX, three tiers: `task-decomposition-dag` plan-validity
    (s) — where the chain dedups inbound over a correcting append-only history, a
    contract sentence must state the VALUE-AXIS decision (identity excludes the
    payload + named discriminator: comparison / client-supplied version /
    correction flag, or includes it with the duplicate-payload posture declared),
    with BOTH resend classes tabled as test duties; machine core in the emit
    validator (correction vocabulary + dedup posture + no axis sentence = refusal);
    `domain-boundary-discovery` step 7 must now ASK THE AXIS QUESTION in the
    identity ambiguity itself, and `domain-driven-architecture` operationalizes
    "never silently decided" (a question some unit operationalizes is decided by
    omission - promote it to an explicit Assumption before decomposing). The
    range-less-metrics companion of G2 (the three honest `enabled:false` floors) is
    NOT a defect - it is the fidelity rule doing its job; the delta is discovery
    now INVENTORIES those gaps as one operator-facing decision list instead of a
    thrice-repeated silent surprise. Pins: **Y1/Y1b**.
15. **(t) — a promised mechanism is a scheduled duty (G3).** The strategy promised
    correlation "propagated to log lines via context-propagation"; the plan tabled
    the opposite in a unit intent ("no context-propagation library is used") — a
    KNOWN divergence once the records are read, invisible to every gate because
    nothing compared a promise to a duty. The day's stack-skill warning (the
    morning java-springboot3 REACTIVE MDC clause) guided the coder tier but had no
    architect-tier counterpart: java-reactive-patterns, the skill the ARCHITECT
    loads for reactive plans, carried no context-propagation clause at all.
    FIX: plan-validity (t) refuses the mismatch at emit — the strategy's own
    mechanism token must appear ADJACENT and UNNEGATED in some stage-2 unit's
    install duty (dependency + enablement at wiring/boot); an honest plan that
    will not install the mechanism amends the strategy first (the rule refuses the
    disagreement, not the choice). Machine core is stack-neutral BY CONSTRUCTION:
    it extracts the token from the strategy and searches the plan — no library is
    ever named at this tier. The concrete half shipped where it belongs: NEW
    "Correlation across event-loop hops" section in java-reactive-patterns (POM
    dependency + `Hooks.enableAutomaticContextPropagation()` + `contextWrite` as
    a named duty). Discovery during implementation worth recording: the naive
    "all mechanism words appear somewhere" matcher passed on v9's own board — the
    negation-aware matcher was written BECAUSE the live artifact's intent
    contained the refused sentence verbatim. Pins: **Y2/Y2b/Y2c** (c = the
    negated-mention class).
16. **(u) — no acknowledged outcome is unmetered (G4).** The morning's floor gate
    checked that PROMISED meters are claimed; G4 showed the floor itself can be
    promised incompletely: v9's metrics listed received/validated/reordered/
    appended/latency — no broadcast meter, no window meter, no drop counter — and
    the subscriber's `onErrorResume(Mono.empty())` after the FAILED audit was
    therefore "compliant" while a losing pipeline reported a healthy dashboard.
    FIX: floor completeness law, both layers refused at emit: (i) every strategy
    step log pairs with a metric (name/tag token overlap) or an explicit
    `uncounted_steps` entry WITH ITS REASON; (ii) every failure/drop/rejection/
    overflow outcome contracted in tabled `semantics` pairs with a counting meter
    in the floor, an owning unit's meter claim, or a declared `uncounted_failures`
    posture — audited-but-uncounted is now a refusal class, exemptions stay
    operator-decision-shaped, never silent. Stack tier: java-reactive-patterns
    backpressure section now spells the concrete shape (DROP_OLDEST /
    FAIL_OVERFLOW / subscriber-swallow ⇒ paired Micrometer counter with bounded
    tags, claimed by the same task). Pins: **Y3/Y3b/Y3c + Y4/Y4b/Y4c**.

Verification (live-fire on the artifact that revealed the rules — the same method
as III.2's grading of (k)–(r), READ-ONLY, zero billed sessions, zero board
mutations): a direct `plan_consistency` run over the delivered v9 board's 102 task
records + strategy now emits exactly the residuals: (s) fires for G2, (t) fires
for G3 (naming the strategy's own segment and token), (u) fires twice for G4 (the
two uncounted steps + the FAILED-audit semantics without a counter). Gauntlet:
engine decisions **162/162** (11 new Y pins over the 151 pre-existing), skill scripts
**53/53**. Fixture honesty, disclosed: three pre-existing gauntlet strategies
carried placeholder floors whose meters never paired with their own step logs
(`x done`/`pkts`) - rule (u) refused the PLACEHOLDERS, proving it fires, and the
fixtures gained the pairing meters (`packets.received`, `stock.reserved`,
`jobs.done`); no pin's asserted behavior changed. Rule letters shipped tonight
join the ledger: plan rules (s)/(t)/(u); prompts/agent-digest mirrors
(both agent tiers) and README §Plan-time contracts updated the same pass; the
README enumeration also corrected a now-stale claim that migration-location
portability is an assembly-gate probe - per item #12 it is EMIT-only.

17. **(2026-11-17, 11:35) — OPERATOR EDIT, DISCLOSED: the delivered `application.yml`
    re-serialized to native nested YAML; plan rule (v) shipped.** The operator's fifth
    drain finding was format-level: the delivered config document spelled every fact as
    a FLAT DOTTED KEY (`spring.r2dbc.url: ${VAR}`, `telemetry.boundaries[0].metric:
    HEART_RATE`) - the properties vocabulary written into a YAML file. Root cause was
    NOT a coder improvisation: the config unit's own intent demanded "FLAT dotted-key
    style (never mix nested mappings)", copied verbatim from the java-springboot3 stack
    skill's "flat dotted keys are this repo's single canonical form" clause - a pinned
    decision whose stated REASONING was itself wrong twice over (dotted LEAF keys ARE
    expressible nested, as one key at their level; list-of-objects config has a real
    YAML SEQUENCE form). The values were never the problem: the runtime loader flattens
    nested and flat spellings to identical property paths, and the tester contract had
    pinned `ApplicationYmlTest` to that loader - so the file could be fixed under the
    suite's own eyes. FIX, three tiers: (a) TREE (operator edit, disclosed, values
    byte-equivalent - including the disclosed G1 `filesystem:` line, which was NOT
    silently repaired): re-serialized to nested mappings + a real 7-entry sequence;
    proof: fresh offline `./mvnw -o test` = **258/258 green, 33 classes, zero test
    edits** + boot smoke started in-context. (b) STACK skill: java-springboot3's clause
    REPLACED by "CONFIG FORMAT FOLLOWS THE ARTIFACT KIND" (structured kinds nest; flat
    key-value kinds spell dotted keys; dotted leaf = one key at its level; sequences for
    list config; never one kind's syntax inside another's file), the false "only
    expressible flat" myth struck out; the coder skill gained a Non-code payloads
    section (a plan's KEY/VALUE table is a semantic path list, not a file layout); the
    tester skill now states the oracle reads property PATHS, never serialization shape
    (that is what made (a) legal); the assembly skill teaches the assembler the
    re-serialize-never-reVALUE recipe. (c) MACHINE HALF: assembly probe
    `_config_format_problems` (root-level dotted keys in .yml/.yaml = flagged;
    .properties files are native-flat and never touched), wired into `detect()`,
    opt-in per STACKS row (`config_doc_globs`); pins **X8/X8b/X8c/X8d**. Doctrine note:
    (v) is the ARGUED exception to the T4 livelock rule - (r) is EMIT-only because it
    moves VALUES against a frozen string; (v) lives at the delivered gate precisely
    because it moves only SHAPE: same keys, same values, no test can see it (a test
    that could see it would itself violate the loader rule). Gauntlet after the whole
    pass: **166/166** engine decisions, **53/53** skill scripts; the delivered tree
    passes the full `assembly.detect` with zero problems; agnostic tier unchanged in
    character - (v) speaks of file KINDS and serialization forms, never of Spring,
    Flyway or YAML-by-name at the architect level beyond the kind taxonomy.
