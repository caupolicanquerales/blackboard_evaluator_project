# Project inspection — 2026-11-20 (the architect split: two carriers, per-context sessions, the linter as contract)

Supersedes nothing; builds on the morning's phase-2 duty digest (the `write_phase2_digest`
context-blow-up fix, uncommitted in the tree when this work began) exactly as the operator's
brief said it must: the digest is now the planner's PRIMARY input, extended per duty.

## 1. Verdict up front

The monolithic `agent-architect` is gone. Phase 1 runs as **`agent-strategy-architect`**, phase 2 as
**`agent-planner-architect` — one session per bounded context**. The 26-rule invariant wall (a)–(z)
left the resident profiles: `task-decomposition-dag/SKILL.md` carries the full contract and
the deterministic `--lint`/`--emit` tier enforces it, refusing with `ERR [T2-014.field]`
pointers and naming the rule by letter. The engine — not a session — now claims drafts
(id arithmetic, collision renumbering, dangling-pin refusal) and runs the single batch
`--emit`, routing a refusal to a bounded repair session that carries ONLY the error text.
Gauntlet after the change: **SKILL-SCRIPTS 156/156, ENGINE-DECISIONS 325/325, ALL GREEN.**

## 2. The five fixes, as shipped (operator brief, 2026-11-20)

| # | brief | shipped as | measured (static) |
|---|---|---|---|
| 1 | Split phase 1 and phase 2 into separate agent definitions | `agent-strategy-architect` + `agent-planner-architect`, four mirror profiles (bodies identical per pair, Q12), the old two files deleted, settings/backends/pipeline re-homed, session_audit classifying `strategy`/`planner`/`planner_repair` (historic `architect` phrase still classifies) | resident profile body: **18,374 → 3,437 (strategy) / 7,872 (planner) chars**; phase 1 no longer carries ANY decomposition law (Q13 pins `spec_ref`/`task-decomposition` ABSENT from the strategy profile), phase 2 no longer carries strategy law |
| 2 | Invariants (a)–(z) out of the prompt, into `--emit` | the profiles' letter-wall deleted; planner keeps a FIVE-law breath (a/b/f/z/y — the classes a fresh plan breaks most) plus the pointer remedy; `_format_error` makes every emit/lint refusal an `ERR [pointer]:` line in one batch report; Q14 rewritten: the skill lists a–z (26/26 pinned), the profiles enumerate ≤6, the linter carries the letters | the restatement was §9's own number: **~3.0–3.5K tok on EVERY turn** — now zero in phase 1, and phase 2 reads it once, in the skill it must load anyway |
| 3 | Pre-filter the digest: matched rows INTO each duty | `write_phase2_digest` attaches every duty its `table_row` (header + cells: identifier + config key), extracts the tables' `build_coordinates` into the digest, and a per-context `write_phase2_digest_slice` carries only this context's surfaces/duties/rules/rows; mapping tables load ONLY when the slice lists `unmapped_duties` (PF4b re-pinned) | live telemetry board: **27/27 duties carry their row, 0 unmapped** — the planner would never open the three tables; brief: **5,548 → ~1.7K tok**, ~1.2K words |
| 4 | Telegraphic prose + ONE positive example | the planner profile carries a valid stage-1 + stage-2 JSON pair (ast_hints tables, verbatim `AZ-02 tenant-scoped-query` claim beside the copied mechanism, reach geometry visible) instead of stacked prohibitions; AS4 pins the example | prohibitive "never X, never Y" chains replaced by the example + one-line laws |
| 5 | Cap context history between bounded-context drafts | BOTH branches: one planner session per context (strategy + its digest slice + the Python-built symbol table of drafted exports; contexts drafted provider-first via the context-map relationship graph — `context_draft_order`), AND a final lightweight batch run by the ENGINE (`emit_draft_batch`, zero sessions); at most 2 repair passes per domain, then a fatal naming `--replan` | no session's transcript ever carries a second context's draft (the 40,442-tok single-turn class and its residence); a miscounted id is healed by `claim_draft` renumbering, never billed |

## 3. Defects found and fixed while building the split (each pinned)

| # | symptom found in the new code | root | fix | pin |
|---|---|---|---|---|
| X1 | `claim_draft` rewrote a VALID backward pin: Beta's collaborator pin to Alpha's id was renamed with Beta's own colliding ids | the rename map keys are ambiguous when a misnumbered file re-uses a drafted id — dependsOn has no type, but a `dependencies` pin DOES | pins follow the rename only when their `type` names one of the file's OWN renamed exports (or the id resolves nowhere else); a pin the world answers keeps the world id | SP1 |
| X2 | the Build-coordinates extraction returned `[]` for every table | the section header is a TWO-line `#` comment; the stop-scan saw the continuation line and cut before the pipe table | collect pipe rows after the marker until the first non-pipe line once the table started; comment continuations before the table are skipped | DG3 |
| X3 | lint reported a dangling `dependsOn` twice (validator's resolvability line + the split-law line) | two independent scans, no dedupe | the split-law line is skipped when the per-task validator already named that exact ref; pins (which validate does not scan) always get the field-pointer line | SP2 + live `--lint` check |
| X4 | a `--lint` fixture id `T1-993` on a stage-2 task refused as "id stage suffix differs" — the refusal itself was right, the fixture was wrong | id↔stage agreement is a validate law; the new cases must pair T2 ids with stage 2 | fixture corrected; the law re-proved in the suite | SP1–SP4 |

## 4. Engine surface moved (the B7 checklist applied to a SPLIT instead of an ADD)

new — `.opencode/agents/agent-strategy-architect.md`, `agent-planner-architect.md`, `.github/agents/*`
mirrors (mirror-identical bodies, Q12); modified — `settings.py` (two agent constants +
budgets 12/12, `ARCHITECT_AGENT` deleted), `prompts.py` (strategy brief re-headed,
`ARCHITECT_TASKS_PROMPT` deleted, `ARCHITECT_PLANNER_PROMPT` + `ARCHITECT_PLANNER_REPAIR_PROMPT`
+ `build_planner_prompt`/`build_planner_repair_prompt`), `ddd.py` (per-duty `table_row`,
`build_coordinates`, `context_stem`/`context_draft_order`/`write_phase2_digest_slice`),
`task_queue.py` (`--lint` engine half: `lint_draft`, `claim_draft`, `draft_symbol_table`,
`emit_draft_batch`, `draft_path`/`clear_drafts`/`draft_world`, `_format_error` pointers,
`replan_domain` now drops the domain's /tmp digests/slices/drafts/symbols),
`pipeline.py` (`_plan_domain_tasks` loop, `PLANNER_REPAIR_ROUNDS = 2`, `--lint` CLI,
phase strings kept for PG13), both backends (`run_strategy`/`run_planner`/`run_planner_repair`,
`run_architect` deleted), `session_audit.py` (role markers + budgets),
`orchestrator_opencode.py` docstring; skills touched only in the four
`tech-stack-architect/*/SKILL.md` DESCRIPTIONS (phase-2 owner renamed to `agent-planner-architect`).

## 5. Residual limits (stated, not hidden)

- Contexts in a CYCLE at the context-map level draft in strategy order; a pin the cycle
  makes unavoidable surfaces at the batch emit and lands in the repair pass. Two rounds,
  then the fatal names `--replan` — the operator decides, the session does not loop.
- `dependsOn` self/world ambiguity in a misnumbered file resolves in favor of SELF (the
  misnumber is the common case; a legitimate backward `dependsOn` on a re-used number is
  rare and the emit still sees the final bytes — no silent wrong edge survives the batch).
- The per-context sessions re-load the decomposition skill each session (~8.2K tok). That
  is residence in a SHORT transcript (~6-8 turns) instead of a long one; the next drain's
  `--burn-report --role planner` is the authority, §9's method, and the claim below is
  honest-static until that report exists.
- Python/TypeScript still have no architect-tier tables (unchanged from B7); the digest
  records their duties as unmapped and the planner is sent to the mapping table path the
  brief states — the `unmapped_duties` channel exists precisely for this.

## 6. Verification

- `session_audit` classification run against the three real templates (AS5, live in-suite).
- Real-board smoke, read-only: draft order `Telemetry Sample Ingestion → Windowed Telemetry
  Streaming`, digest 27 duties / 42 rules / 4 build coordinates, slices 17 + 10 duties,
  `--lint` CLI refusal prints `ERR [T2-999]` + `ERR [T2-999.ast_hints.dependencies/...]`, exit 1.
- Gauntlet: **SKILL-SCRIPTS 156/156** (+7: Q14/Q25/Q27/Q30/Q31 re-homed, SF1 rewritten for
  slices, AS1–AS6 new), **ENGINE-DECISIONS 325/325** (+9: S17b/S20 re-homed to the planner
  brief, S26 per-agent budgets, SA7 planner edit-grant, SD4/SD5 carrier re-homes, DG3–DG5
  digest/slices/order, SP1–SP4 lifecycle, Z15 extended with the /tmp planning state).

## 7. What the fresh process now tests in one drain

Per-context planner sessions against a real 2-context domain, the claim/emit/repair loop,
zero table loads when the slice maps (the live telemetry board's 27/27), the ERR-pointer
remedy under real refusals, and — measurable for the first time as separate roles —
whether the split delivered the §9 projection. The static bytes say the resident profile
wall is down ~57-81% per phase and the per-turn rule restatement is gone; only a live
`--burn-report --role planner` says what that was worth in tokens.

## 8. Operator review, same day — the profile's content errors and the family naming, closed

The operator read `agent-planner-architect` (then still `architect-planner.agent.md`) and
found the file wrong in two independent ways; both are roots, both became cases.

| # | symptom (what the operator saw) | root | fix | pin |
|---|---|---|---|---|
| X5 | the GitHub mirror's "frontmatter" WAS the body: no `name:`, no `description:`, no `tools:`, and the whole document appeared twice (once inside the `---` header region, once as the body) | the mirror-copy script rebuilt the header by string-splitting a file a previous script had already corrupted — split(`---`, 2)[1] picked up the leaked body, and the corruption compounded on the next copy | both mirrors rebuilt from the `.opencode` sources with explicit, correct headers; the copy step now asserts (body identical, exactly one `# Global rules`, `name/description/tools` present) | AS4c (per mirror: one fenced example, exactly one body — and a frontmatter that parses as frontmatter is what Q12's body equality alone could not see) |
| X6 | the "Valid pair" example taught a plan the emit gate would REFUSE | three separate content errors: `"ast_hints": "THE SAME OBJECT AS T1-021"` is a prose placeholder where JSON demands the object (and rule (z4) demands the BYTE-IDENTICAL twin spelled out); the route carried `"duty": "uses"` on the unit that ANSWERS it — (z) requires `serves` on the one inbound unit; the claim sat in the entry's intent beside `permits(...)`-on-the-pinned-store — (y1) places the claim on the enforcing unit, so the mechanism must be the entry's own lookup (`byIdAndTenant` at the lookup, the lawful co-located form the reach law names) | example rewritten: valid JSON, twin tables literally identical, `serves`/`owns` duties, `AZ-02 tenant-scoped-query` beside the copied `byIdAndTenant(...)`, the T1 twin carrying the row id + the cross-owner case; the caption states the peer-enforcement alternative instead of faking the geometry | AS4b (parses the fenced block, asserts the twin identity, the duties, and both intent shapes — the example is now machine-checked law, not decoration) |
| X7 | agent names broke the roster's structure: the family is `agent-<specialty>-architect` (security/performance/database/AI all obey it) and the split's two carriers had invented `architect-<phase>` | the split named after PHASES while every neighbour is named after its SPECIALTY; the Copilot resolver, settings, pins and docs all read the id | renamed to `agent-strategy-architect` / `agent-planner-architect` across the four profile files, settings, both orchestrator docstrings, the four `tech-stack-architect` descriptions, both gauntlet files, README and this report; audit roles (`strategy`/`planner`/`planner_repair`, classified from the PROMPT phrases) stay as they are — they name the session kind, not the agent | AS1 (settings equality) + every path-bearing case re-pointed; a stale filename fails Q12/AS2 mechanically |

Gauntlet after the review: **SKILL-SCRIPTS 159/159, ENGINE-DECISIONS 325/325, ALL GREEN.**

## 9. Operator edge cases, same day — three tightenings (X8–X10)

| # | edge (operator review) | root | fix | pin |
|---|---|---|---|---|
| X8 | the planner profile cited "the ONE rule (t) strategy promise amendment" — but rule (t) lives in the skill, which loads AFTER the profile is read: a label pointing into an unloaded document is a folder hunt wearing a citation | the split's item-2 (invariants moved to skill + linter) left one reference behind that still needed the wall to be understood | the ten-word meaning now travels with every (t) reference, in both profile mirrors AND the per-context brief ("a promised mechanism the plan will not install"); the letter stays as the pointer to the skill's full contract | AS4e |
| X9 | the Valid pair spelled `byIdAndTenant(id, tenantId)` in the T2 intent directly under the law "what `ast_hints` pins is never re-spelled in prose" — the parameter list is SampleStore's table's business, and an LLM copies the example, not the caveat | examples were tuned for claim geometry, not for the prose-conciseness law they sit under | prose now carries the bare NAME (`byIdAndTenant`); the intent bullet states the naming law ("a collaborator's method is NAMED, never spelled with its parameter list"); the example footer calls out rule (e) explicitly | AS4d (+ AS4b's `byIdAndTenant(` / `(id, tenantId)` absence clauses) |
| X10 | both agents may schedule stage-0 build-file work: the strategy emits the ONE scaffold, each planner context may notice a missing coordinate — two contexts, two manifests, one pom.xml; last-write-wins picks the delivered build file and the first duty silently vanishes, while the "ONE lawful stage-0 build-manifest task" law was carried by prose only | the manifest duty predates the split; the split made the twin-duty race possible | `_stage0_family_errors` runs in BOTH tiers (lint + batch emit): at most one `project_scaffold` and one `build-manifest` per project, keyed by the export marker (never path shape — the S16 lesson), a twin refused naming the FIRST task; `draft_symbol_table` gained `build_manifest` (id + path + VERBATIM intent) and `scaffold`, with stage-0 tasks kept OUT of the unit pin vocabulary; the brief teaches consult-first / report-don't-duplicate — the repair pass, not the planning session, amends the ONE task | SP5 (lint cross-file, lint twin-in-file, emit), SP6 (symbol data), AS4f (carriers) |

Gauntlet after the tightenings: **SKILL-SCRIPTS 162/162, ENGINE-DECISIONS 327/327, ALL GREEN.**


## 10. X11 - the reported gap must LAND where the machine reads it (operator catch, same day)

**Symptom (design defect, caught before any live run):** the planner carriers told context
B - which may neither duplicate the build-manifest task nor edit context A's file - to
"report the gap" when the ONE scheduled manifest lacked a coordinate. The report died in
the session transcript: no engine step read it, the batch emit ran with the coordinate
unscheduled, and the hole surfaced exactly where D4 surfaced on 2026-11-18 - the first red
compile importing a class no build file carries. A hand-off the machine cannot read is not
a hand-off.

**Root:** the gap channel was prose-only while the split made cross-context coordinate
discovery a routine event (each per-context session sees only its own slice's need).

**Fix (law + channel + gate):**
- the brief names each session its structured channel - `/tmp/tasks/<slug>-<context>.gaps.json`,
  `{"missing_coordinates": ["<verbatim build_coordinate>", ...]}` - and the carriers now say
  in one line what happens to it: the ENGINE reads it and appends to the ONE task;
- `task_queue.apply_coordinate_gaps(slug, contexts)` runs after the last claim and before
  the batch emit: reported coordinates (deduped, first-seen order) are appended VERBATIM to
  the ONE build-manifest task's intent - skipping coordinates it already carries, so a
  re-run is a no-op; gaps files are excluded from the pin-world scan and from the batch;
- a report with NO manifest to amend is a claim-grade problem line naming the coordinates -
  it enters the existing bounded repair loop (the repair session schedules the ONE task;
  the engine never authors planning intent), and the pipeline still fatals after two rounds;
- `clear_drafts`/`replan_domain` already match `*.gaps.json`, so no stale report survives
  the plan it described.

**Pins:** SP7 (append lands verbatim in the FIRST task's file - B never touched it, the
engine did; already-carried coordinate not doubled; second apply is a no-op; the emitted
batch is clean; a lonely report is a problem line, bare-list and dict shapes both accepted);
AS4f extended (both mirrors + the brief teach `missing_coordinates`/`{gaps}`, the engine
consumes `apply_coordinate_gaps`).

Gauntlet after X11: **SKILL-SCRIPTS 162/162, ENGINE-DECISIONS 328/328, ALL GREEN.**


## 11. Carrier compression (operator brief, same day) - the profiles' own prose tax

The split removed the OTHER phase's law from each carrier; this pass removed the FIRST
phase's redundancy from its own. Method and guard: every string the pins assert (raw or
FLAT) was extracted into a compliance harness and verified against the compressed bodies
BEFORE the suite ran - compression that silently breaks a pin string is a silent
pin- weakening. Three pins legitimately moved, with their old assertions deleted, not
loosened: Q13.1/2 (the strategy's narrative "the database, security... run AFTER you; a
separate PLANNING agent..." became the hard boundary "Output: execution-strategy-<slug>.json
+ ONE T0 scaffold task. No code, no task decomposition, no git, no foreign domains" - the
pin now demands exactly that, and still the negatives: no spec_ref, no task-decomposition,
no table_row in the strategy carrier); Q14 (the five-law breath is deleted too - letters
survive ONLY as inline cross-reference tags (b)/(y)/(z) inside the Draft-law bullets; the
pin asserts no line-start letter-wall in either profile, the marker block absent, the
inline tags present, the skill still listing a-z); PF4b ("a load policy... never nowhere"
became the telegraphic "Performance (PB-/PI-, or WB- if uncovered) and AI (AC-/AM-) claims
follow the same T2 placement without the reach law" - pinned on the replacement phrase).

| carrier | before | after | where the bytes went |
|---|---|---|---|
| agent-planner-architect body | 9,789 chars | 7,377 (-25% file, -31% prose; the 1986-char Valid-pair block kept BYTE-VERBATIM - AS4b machine-checks it) | 13 lines of example commentary -> 3-line caption; five-law paragraph deleted; build-manifest 5 lines -> 2 crisp sentences (emit-one / append-to-gaps), the gaps channel and the never-a-second-manifest law intact; narrative clauses cut ("measured 2026-11-18: 91k carried, 41k worst single-turn" -> "never a generator script that produces or patches drafts") |
| agent-strategy-architect body | 3,437 chars | 2,902 (-16%) | the downstream-phase narrative collapsed into the boundary line; surfaces + observability bullets condensed to their schema constraints ("an unnamed surface gets no row, no duty, no guard" and the double gate-clause merged into one; export-entry wording halved). Honest note: the brief projected ~25%; what remains after the identified redundancies IS the schema law (key lists, join-key spelling, the floor) - cutting it to hit a percentage would remove binding content, so the number is reported as measured, not as promised. |

Resident-cost math at §9's basis (~4.6 chars/token): the planner profile saves ~520
tokens EVERY turn of every per-context session; the strategy profile saves ~115 every
turn of the strategy session; the five-law deletion also removes the one block whose
content the Draft-law bullets already carried (pure duplication by the audit's own rule).
Mirrors rebuilt and re-verified identical (Q12); harness then suite: SKILL-SCRIPTS
162/162, ENGINE-DECISIONS 328/328, ALL GREEN.


## 13. Supervision round 2 (run 3) - the planner's context was the problem, and it is measured now

Operator call: "something happen with the agent-planner-architect - check the size of the
context or the agent cannot read the reports". The process was stopped mid-context-2 and the
session records answered the question exactly: **the agent CAN read (every report loaded, the
drafts obey every law now) - the context was the cost.** run-3's ctx-1 session (14 calls,
6.0K lines... 69 units, LINT-CLEAN, gaps file written correctly):

| turn | fresh input | cache-read | output | what happened |
|---|---|---|---|---|
| 1 | 22,360 | 4,251 | 283 | the COPILOT FLOOR: system + profile + brief before any file read - ~22K tokens is the CLI's own overhead, not ours |
| 2-6 | 26K -> 55K | rising | ~100-250 | reads: strategy 9.2KB, slice 36.7KB, DAG skill 37.7KB, both stack skills - plus TWO re-views of the slice (truncation pagination from oversized inputs) |
| 7 | 55,470 | 55,077 | **21,041** | the draft create |
| 8 | 76,562 | 76,560 | **31,000** | first lint refused (real defects) -> ONE pattern rewrite per the new remedy law - 31K of output, resident forever in this session |
| 9-10 | 108,244 | 107,698 | ~1.8K | relint clean, gaps file, finish |

Total: **601,904 input (498K cache-reads) / 54,992 output** - and the two fat inputs were
ours to fix, so they are:

| # | finding (measured) | root | fix | pin |
|---|---|---|---|---|
| X12 | ctx-1's digest slice was 36.7KB - nearly the FULL digest: rule entries carried the specs' rationale/notes prose, mechanisms repeated the WHOLE table while every duty ALSO carried its matched row, headers were copied per duty, build_coordinates of all three phases rode every slice, data_model was whole-domain | the slice was filtered by CONTEXT but not by PURPOSE | slice trims: prose keys dropped from rule entries (full digest keeps them - the repair pass reads that), mechanisms carry header+table once and NO rows array (the cells travel on the duties), duty table_rows are cells-only, coordinates and data_model scoped to the slice's phases/context. ctx-1 slice 36,707 -> 24,785, ctx-2 22,026 -> 17,655 | DG4 extended (no rows array, cells-only rows, ghost-slice pruned) |
| X13 | the ctx-2 symbol table was 46.7KB: 69 units = 23 tables written THREE times (T1, T2, T3 carry IDENTICAL tables by law z4!) | the fold did not exist | symbol table folds: the stage-2 entry is the table's ONE home (plain string lists), same-suffix T1/T3 with an identical table become `table_of` pointers, stage-0 families unchanged - 46,733 -> 29,674 bytes, every pinnable id still present | SP9 (fold lossless: pointers, lists, ids) |
| X14 | /tmp held slice files of TWO contexts this board no longer has (dead names from a previous generation) | slices were only ever written, never pruned | write_phase2_digest prunes every phase2-slice-<slug>-<stem> not in the current draft order | DG4 ghost clause |
| X15 | the session's 14 calls exceeded the stated 12 (warning line, not fatal; hard kill is 24) | honest measurement so far: reads 6 (incl. 2 truncation re-views) + create + lint + rewrite + relint = the minimum for a FIRST context whose draft then needs one pattern rewrite | budget stays 12 (stated==engine, S26) - the slice/symbol diet removes exactly the re-view calls; if run 4 measures over again, the number moves in ALL carriers together, never one | S26/AS2 unchanged |
| X16 | Copilot's own floor: turn 1 was 22,360 input tokens BEFORE any file read | CLI system prompt + tool schemas + profile + brief - not ours to shrink beyond profile/brief bytes | documented, not actioned (the profile/brief ARE already at ~2K each); the fix surface is every byte we DO control: X12/X13 | - |

The resume state proves the earlier fixes work end to end: ctx-1's draft carries **23 exact
T1+T2+T3 triples, ZERO inverted stage edges, LINT-CLEAN, and a correctly spelled gaps file**
(the first manifest-less report the gap channel was built for). A restart claims it without
a session ([resume]), plans ONLY ctx-2 with the slimmed slice+symbols, then the gap step turns
that report into the ONE manifest task (repair path, SP5/SP7's shape), and the engine emits.

Gauntlet after the round: **SKILL-SCRIPTS 165/165, ENGINE-DECISIONS 330/330, ALL GREEN.**


## 14. Operator analysis round 3 - the input FILES themselves (A/B/C applied, one variant, one refusal)

The operator's analysis was verified against the real board BEFORE deciding: strategy file
8.6KB whole in every session ✓; digest slice 14.9-17.7KB of which a **5.2KB rules map
duplicating the duties' own joins** ✓ (assumptions/principals/risks were NOT in the slice -
the round-2 trim had stopped at the section level, not the KEY level); three full skill
files every session ✓ (dag SKILL.md alone: 38.3KB / 5,967 words).

| # | operator proposal | decision | what shipped | pin |
|---|---|---|---|---|
| A | Pre-slice the execution strategy by context | **APPLIED, with one documented variant**: `ddd.write_strategy_slice` -> `/tmp/strategy-slice-<slug>-<context>.json`: surfaces filtered to the context, `observability.step_logs` re-keyed to the context alone, risks/build_order dropped (operator-facing phase-1 output, not planning input), ghost contexts pruned for BOTH slice prefixes. **Variant:** persistence stays IN FULL when the domain owns a store instead of null-ing for non-owning contexts - one domain ships one schema and a streaming context READS what the ingestion context writes; the data_model strings carry no context attribution, and a heuristic that guessed ownership would delete the store law the repository units plan against. The projection's "persistence: null for Distribution" is exactly the silent-gap class this board has bled on; kept-while-owned is the honest filter. | DG6 (surfaces/step_logs/persistence/keys-set), DG4 ghost clause |
| B | Strip the digest slice to pure actionable records; join the authorization row INTO the duty | **APPLIED exactly**: each duty now arrives with `surface`, `test_duty`, `measurement`, `effect_on_deny`, `statement`, `operation`, `class`, `threat` MERGED off its rule row into itself (`SLICE_DUTY_KEYS` closed set), `table_row` cells-only; the `rules` map, `surfaces`, `data_model`, `observability` are GONE from the digest slice - zero assumptions/trust_boundaries/principals/risks bytes, the specs themselves stay closed, and the FULL digest remains the repair pass's forensic input. ctx-2's digest slice: 17,655 -> 8,409 bytes | DG4 rewrite (keys-subset, AZ-* carry surface+test_duty ON the duty, no rules/surfaces/observability keys) |
| C | QUICKREF instead of the full manual, OR inject stack hints | **APPLIED for the dag skill; DECLINED for the stack skills.** `task-decomposition-dag/QUICKREF.md` (689 words / 4.4KB, cap-pinned at 800): schema keys, stage graph, claim form, emission shape, the (z) vocabulary fields, and the escape hatch - the profile now loads QUICKREF by default and the full SKILL.md ONLY when an ERR pointer cites a letter or shape the map does not summarize. The stack skills are NOT stripped and hints are NOT injected: java-springboot3 / java-reactive-patterns are the sanctioned spelling source for signature language (the Q24/Q28 recall class this repo pinned twice - Boot keys verified against metadata on disk, identifiers from tables never from memory); a Python-fabricated "stack hints" block would put an UNVERIFIED paraphrase exactly where the verified text used to be. They load once per session, which is the same as before, minus the 34KB manual. | AS13 (exists, <=800 words, schema literals, profile conditional phrase), SE1 (quickref is now a (z)-carrier), SF1 (strategy-slice routing in the slicer + template) |
| #3 | profile line 10 + explicit paths + batch-rewrite rule | **APPLIED**: profile Inputs line reads "the context's strategy slice (phase 1's plan filtered to YOUR context...)"; the brief's item 1 carries `{strategy_slice}` with the full file named CLOSED ("a fact the slice lacks is a REPORTED GAP for phase 1, never a silent re-read"); the batch-rewrite rule already shipped in §13 (X-remedy lines), re-pinned by S17b's new clauses ("arrives COMPLETE", "joined ONTO the duty", "strategy-slice-") | S17b extension |

Resident input bytes for the ctx-2 session: **114,447 -> 68,923 (-40%)**; at §9's
4.6-chars/token basis that is ~24.9K -> ~15.0K tokens of loaded material - and the loaded
set is now ~10K tokens smaller BEFORE the first edit, every turn of the session paying
the difference again. Gauntlet: **SKILL-SCRIPTS 166/166, ENGINE-DECISIONS 331/331, ALL
GREEN.** The next launch runs the resume path: ctx-1's fresh draft claimed with no
session, ctx-2 planned against the diet'd slices, `--burn-report --role planner` as the
authority.


## 15. The §14 consistency check the operator asked for - and the hierarchy it exposed

Verified against the live board, not asserted: `write_strategy_slice` exists and the exact
path the rendered brief promises IS the file the pipeline wrote (6,242 B); every AZ-* duty
carries `surface` + `test_duty` JOINED onto it, every PB-* duty carries `measurement`; the
digest slice holds NO rules/surfaces/observability/data_model keys; `QUICKREF.md` exists in
the skill folder and resolves through the Copilot `.github/skills` symlink (689 words);
the Draft-law bullet's family-level reference ("Schema = task-decomposition-dag") is
intentional: it names the CONTRACT FAMILY, and the profile two lines up says which member
to read by default (QUICKREF) and which conditionally (SKILL.md).

The check earned one fix: making QUICKREF a freshness input would have re-planned ctx-1's
draft (written 17:06, the quickref created 17:25) - ~700K tokens re-billed for a MAP
addition that changed no law. `draft_is_fresh` now gates on the NORMATIVE carriers only
(strategy, specs, SKILL.md) and SP8 pins both directions of the hierarchy: a SKILL.md
rewrite invalidates the resume, a QUICKREF rewrite does not - map drift is caught by the
batch laws, the same guarantee that moved the (a)-(z) wall out of the profiles. Real-board
state after the fix: `Telemetry Ingestion draft_fresh=True` (resume, zero sessions),
`Telemetry Stream Distribution draft_fresh=False` (one dieted session).

Gauntlet: **SKILL-SCRIPTS 166/166, ENGINE-DECISIONS 331/331, ALL GREEN.**


## 16. Run 4 - the split measured end to end: the plan completed, the diet worked, ONE fat spot remains (and is closed)

Launched supervised, stopped at the batch emit. Full planner-phase forensics from session
records (usage_records + tool-call traces), not from logs' impressions:

| step | run-2 (monolith carriers) | run-3 (law fixes) | run-4 (context diet) |
|---|---|---|---|
| ctx-1 session | 40 calls, 965K in / 70K out - KILLED at 25, run died | 14 calls, 602K / 55K, LINT-CLEAN result kept | **[resume] - ZERO sessions** (draft newer than every input incl. normative SKILL.md) |
| ctx-2 session | never reached | never reached | **13 calls, 7 turns, 318K in (257K cache) / 30.6K out** |
| gap -> manifest | channel did not exist | channel born | T0-007 scheduled BY the ctx-2 session from its slice's build_coordinates; `[gap ] T0-007 already carries every reported coordinate` - X11's loop closed with no repair session |
| batch emit | - | - | refused 5 law-(w) lines (stage-1 paths on production files in ctx-2 draft) -> **1 repair session: 25 calls, 371K / 12K** -> re-emit ACCEPTED |
| plan integrity | - | - | 118 queued tasks = 37 T1+T2+T3 triples + 7 stage-0; **30/30 duties and 25/25 capability tokens cited in queued stage-2 units**; exactly ONE build-manifest (agent-container/bootstrap/dependsOn empty, both security coordinates VERBATIM in intent); zero stage-1 path violations |

The repair session is the round's ONE fat spot, diagnosed from its call trace: the batch
of pointers described FIVE instances of ONE shape (a stage-1 task path on the production
file); the brief's wording - "EDIT ONLY the named task objects" - was obeyed LITERALLY:
~20 individual edits, files opened and re-grepped, lint runs on files it never changed.
Max turn input 45K (vs 108K in run-2) - the diet holds; the WORDING was the waste. Fixed
in the repair carrier: locate a repeating shape with ONE grep, batch the repairs or
rewrite the affected file, re-lint each edited file ONCE, never re-lint what you did not
change - pinned by AS14.

Supervision's own defect, same class, also closed: a polling kill races the drain's first
billed session in the SAME second the emit marker prints - one container cold-start (3
calls, 59K/1.6K) leaked before the process died; T0-001 stayed queued untouched, so the
leak cost one premium request, not state. The engine now has the flag supervision
should have had from the first supervised drain: **`--plan-only`** - run every plan
phase, queue the finished plan, STOP before the docker gate and the drain, exit 0.
Verified live: a re-launch with the flag printed `[plan  ] --plan-only` and billed ZERO
sessions. AS14 pins the ordering (the return sits after the plan-complete print, before
any gate in the flow) and the repair doctrine's literals.

Budget accounting (stated 12 vs measured 13/25): warnings, not kills (slack + factor
held the hard cap at 24); the 13-call clean draft says the number is right-sized, the
25-call repair is exactly the wording waste AS14 closes. Next full plan projection:
~470K input / ~38K output for BOTH contexts including one bounded repair - against
run-2's 965K/70K for a session that never even finished a context.

Gauntlet after the round: **SKILL-SCRIPTS 167/167, ENGINE-DECISIONS 331/331, ALL GREEN.**


## 17. Full task audit against the three reports - 28 PASS, 2 real defects, and BOTH had a gate hole as root

Every queued artifact (118 tasks) audited against `execution-strategy` +
`security-spec` + `performance-spec` with 30 independent checks (not re-running the emit
gate - re-deriving the laws from the reports themselves). Three initial FAILs were MY
audit's artifacts and are named as such so the ledger is honest: per-task meter counting
double-flagged every pair (T1/T2 twins are one unit - pair-folded: 7/7 floor meters owned
EXACTLY once, by T2-004 and T2-025); SI-01 is declared (spec invariants - the declared-id
set must include every section, not just rows+duties); PB-02/04/07 DO carry their proofs
(`deterministic-count`, `config-key`, `query-count` assertions in the claim + twin T1 -
the vocabulary check was too narrow). The 4 "SQL units without db deps" resolved
likewise: the true SQL adapters (T2-009, T2-013) reach the V-scripts; the rest were the
meter registrar, a repository PORT (no SQL), an orchestrator, and the config unit.

Verified PASS (selection): complete 37 T1+T2+T3 triples, identical twin tables (z4), no
stage-1 path on production (w), zero forward-stage edges, every pin resolves, 3/3 surfaces
named VERBATIM by entry units (y2-ownership), 16/16 security + 14/14 performance duties
claimed spec_ref+capability inside enforcing stage-2 units (y1), y3 cross-owner assertions
on every surface entry's own tester, no PA- cited as duty, dedup identity + BOTH resend
classes tabled (q/s), one config unit (b), one scaffold + one build-manifest with both
coordinates VERBATIM (X10-X11 lifecycle end to end), versions pinned Java 21 / Boot 3.

The 2 REAL defects - both in the frozen queue records, both root-caused ABOVE the plan:

| # | defect | gate hole that let it pass | fix shipped | pin |
|---|---|---|---|---|
| 1 | 4 step logs (`event.consumed`, `window.buffered`, `window.broadcast`, `window.overflow`) promised by the strategy, claimed by NO unit | `_steplog_claim_errors` read `step_logs` as a LIST only; this strategy writes the per-context MAPPING the carriers teach → `wanted` stayed empty → the completeness law silently SKIPPED (V1's 2026-11-13 class re-born in a new spelling); the meter-pairing reader in `tasks.py` had the same blind spot | `tasks.step_log_entries()` flattener, used by BOTH readers; SKILL (j) + QUICKREF now teach both spellings explicitly | V9 + V9b (dict floor half-covered REFUSED naming the entry; full coverage ACCEPTS) |
| 2 | T2-019 spells `@EnableWebFluxSecurity` + `httpBasic` - classes that exist only once T0-007's coordinate lands - yet nothing in its `dependsOn` orders the manifest before its tester; the security table's own "schedule the manifest duty BEFORE any tester runs" had no line in the carriers a claim reads, and no stack-neutral gate can see an annotation | carrier gap (and it is provably a PROSE-TIER law - the (l)-class: engine-blind by design) | the wiring law now ships in all three carriers (profile, quickref, per-context brief): "a unit whose copied mechanism needs such a coordinate lists the build-manifest task id in `dependsOn` (its T1 twin inherits through the pair)" | AS15 |

Remedy for the frozen records (doctrine: the board moves through lawful flows only):
`--replan telemetry-ingestion-processing` - archives strategy/specs/stage-1-3 records,
drops drafts and digests, re-runs the cycle; with the plugged (j) gate the new emit
REFUSES an unowned log by construction (V9-pinned), and the new carrier line wires the
manifest. Expected: ~5 sessions, ~500-700K tokens - cheaper than draining a plan with a
known hole, and the first cycle that runs under fully-armed gates.

Gauntlet after the audit: **SKILL-SCRIPTS 168/168, ENGINE-DECISIONS 333/333, ALL GREEN.**


## 18. Root-fix pass - both defects promoted from prose to machine tier, stack-neutral by construction

The §17 close was half a fix: a flattener + three carrier lines. The operator's rule -
**agents stay agnostic, the orchestrator stays generic** - forced the deeper question:
what made each defect POSSIBLE? Both were shape/structure facts the engine already owns;
neither needs any framework vocabulary. Promoted accordingly:

| root | the actual mechanism | now enforced by | pinned |
|---|---|---|---|
| an ambiguous floor shape | two readers disagreed because the WRITE BOUNDARY accepted a third spelling nobody could flatten; the flattener at the readers was defence, not root | `ddd.validate_strategy` refuses any `step_logs` that is not (a) a list of step strings or (b) a `{context: [strings]}` mapping - the shape dies in phase 1's post-check, in the same session that wrote the file, when it costs one lint-round not one board | **V10** (bare string + context-mapped-to-string refused; both lawful shapes pass) |
| the manifest-wiring prose law | I had assumed enforcement needed to SEE an annotation - it doesn't: the module-wide test compile is a STRUCTURAL fact of every stack (Maven, Gradle, npm, pip). If the project schedules an export=`build-manifest` stage-0 task, EVERY stage-1/2 task must reach it transitively through `dependsOn` | `task_queue._manifest_order_errors(staged, index)` wired into BOTH tiers: `--lint` (single-file, before any batch) and `--emit` (whole plan) - reads only the export marker and the dependency closure; zero artifact/annotation names in the check | **SP10** (refused at emit AND lint naming both ids; transitive reach counts via the pair; manifest-less projects untouched) + SP5 fixture corrected to the lawful shape; AS15 stays as the carrier tier the agent reads BEFORE the gate has to refuse |

Live-board evidence the root was real: the new gate finds **46 of 74** stage-1/2 tasks
without a path to T0-007 - not the single T2-019 the prose audit caught. The frozen
records stand; `--replan telemetry-ingestion-processing` is now the only lawful way to
re-issue them, and the armed gates make the next plan provably correct BY CONSTRUCTION:
an unowned step log cannot pass emit (V9), a malformed floor cannot leave phase 1 (V10),
an unwired unit cannot leave the batch (SP10), and none of it names a framework.

Doctrine check: every new line is shape/structure (lists, mappings, export markers,
dependency closures). The mapping tables keep their monopoly on mechanism vocabulary.

Gauntlet: **SKILL-SCRIPTS 168/168, ENGINE-DECISIONS 335/335, ALL GREEN.**
