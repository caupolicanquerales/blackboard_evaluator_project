# Project inspection — 2026-11-18 (the security layer's two structural gaps, closed)

Method: the claim under review was that the security phase could still fail to reach the code.
Both gaps were reproduced against the **live engine modules** (not by reading prompts): a probe
imported `orchestrators/ddd.py` and `orchestrators/task_queue.emit_tasks` and ran them over
synthetic boards in a sandbox (`/tmp/opencode/probe_gaps.py` = before,
`/tmp/opencode/probe_fix.py` = after). Every reproduction below became a gauntlet case (Z1-Z17),
per the repo rule *no merge without a case*.

## 1. Verdict up front

| gap | state before | state now |
|---|---|---|
| **A** — phase 1 omits an inbound surface, so the spec tables no row and rule (y) discharges nothing | **REAL.** Phase 1 had no content gate at all (its post-check was `if not database_slugs()`); `validate_security_spec` never opened the strategy; a 2-surface plan with a 1-row spec passed, and so did a spec carrying a non-empty `open_questions` about the missing surface | **CLOSED.** Strategies carry a `surfaces` table (`name, kind, context, operations, traced_from`) + `contexts_without_inbound`; `ddd.validate_strategy` is phase 1's post-check on both backends and a pre-security pipeline gate; `validate_security_spec` joins the spec back to it (one row per declared name, invariant `owner_context` ∈ `bounded_contexts`, `principals[].source` traced into the slice, classification non-empty over a declared `data_model`); a spec with `open_questions` stops the run with the phase-1 remedy |
| **B** — a duty claimed by an island unit while the endpoint that needs it ships unguarded, in the wrong order | **REAL, and worse than reported.** The claim gate read `intent` of ANY `stage >= 1` record: an unwired entry+guard pair was accepted, the *same plan correctly wired* was accepted identically, a duty claimed **only by a stage-3 evaluator** was accepted, and a duty claimed **only by a stage-1 tester with no implementation unit at all** was accepted. Ordering is `dependsOn`-only (`tdd_engine`: `unmet = deps - complete`) and testers see only *pinned* collaborator tables, so the surface closed before its guard existed | **CLOSED.** Three emit refusals: **(y1)** the claim must sit on the stage-2 unit that enforces it; **(y2) reach** — the inbound adapter that IS the surface must pin the enforcing unit (`ast_hints.dependencies` and/or `dependsOn`), or the predicate lives on the lookup unit; **(y3)** that adapter's paired stage-1 test must carry the row id and its cross-owner case. Plus **surface ownership**: a declared surface no inbound unit names is refused, so the join cannot be dodged by silence. Ordering follows from (y2) — the edge *is* the schedule |
| **C** — on a board whose decomposition predates its spec, the whole security layer degraded to `[hint ] security …: N duty(ies) are unclaimed` and the drain continued | **REAL and live on this board** (`_application_tasks_queued() = True`, no `security-spec-*.json` yet, phase 1 skipped) | **CLOSED.** `task_queue.security_claim_gaps(slug)` reads the LIVE board with the same reading as the emit gate; a non-empty result is now `[fatal] security <slug>: N security claim gap(s)` with the remedy, and the remedy is a new one-flag operator tool: `--replan <slug>` |

## 2. Why the neighbouring rules did not see gap B

They are adjacent, not overlapping — worth recording so the next reader does not re-believe them:

- **(k) consumer closure** fires only for tabled methods that **publish a stream**
  (`_returns_publisher`). An `ownership-predicate` returns `boolean`: an island guard is invisible to it.
- **(p) request-path slice** demands one end-to-end test per inbound adapter, but ties it to no matrix
  row: the green slice proves routing and storage, never refusal.
- **(y) claim coverage** proved *a* duty was claimed, never *where*.
- `tasks.validate` checks `dependsOn` for shape, stage order and cycles only.

## 3. Shape of the fix

| layer | file | what moved |
|---|---|---|
| strategy contract + gate | `orchestrators/ddd.py` | `validate_strategy`, `strategy_surfaces`, `norm_surface`, `security_open_questions`, `_security_strategy_errors` wired into `validate_security_spec` |
| placement / reach / assertion | `orchestrators/task_queue.py` | `_security_reach_errors` (y1/y2/y3 + ownership), `_pins`, `_inbound_units`, `_unit_text`, `security_claim_gaps`, `replan_domain` |
| pipeline | `orchestrators/pipeline.py` | `--replan SLUG…`; strategy gate before the security phase; `open_questions` → stop; claim gaps → stop (replaces the hint) |
| phase post-checks | `orchestrators/opencode_backend.py`, `copilot_backend.py` | `run_architect("strategy")` now validates every written strategy, not just its existence |
| prompts | `orchestrators/prompts.py` | phase 1 surfaces contract; phase 2 placement law; security prompt row-per-surface + verbatim join keys + "an open question stops the run" |
| profiles (both backends, bodies byte-identical) | `.opencode/agents/agent-architect.md`, `.github/agents/agent-architect.agent.md`, `…/agent-security-architect.{md,agent.md}` | rule (y) + (y1)/(y2)/(y3) + ownership; surface law in phase 1 |
| skills | `architect-practices/security-strategy/SKILL.md` (+ `references/security-spec.schema.json` placeholders), `architect-practices/task-decomposition-dag/SKILL.md` | surfaces as the row source; new rule **(y)** in the DAG contract |
| pins | `gauntlet/test_engine_decisions.py` | Z1-Z17 (17 new cases) |
| docs | `README.md` | rule (y) placement law, the surfaces table, `--replan`, `blackboard/archive/`, case counts |

## 4. Consequence for the seed-002 board (read this before relaunching)

`blackboard/complete/execution-strategy-telemetry-ingestion-processing.json` declares
`modules: ["telemetry-ingestion-processing"]` and **no `surfaces`**, so its next launch stops with

```
[fatal] strategy telemetry-ingestion-processing: … declares no `surfaces` array …
[hint ] relaunch with --replan telemetry-ingestion-processing to archive this domain's plan and re-run the phases that read it
```

`--replan <slug>` archives that domain's strategy, spec and stage 1-3 records to
`blackboard/archive/` and re-runs strategy → database(skip) → security → tasks over the SAME
scaffold and sources (stage 0 and stage 4 records stay; delivered code is never deleted). Restore
an old plan by moving its files back. There is deliberately no "ignore" flag: draining over an
unenforced permission table is the state this note exists to end.

## 5. Residual limits (stated, not hidden)

- The join is **name-based**. It needs phase 1's `surfaces[].name` to be copied into the row and
  into the entry unit's intent; that is now enforced in both directions (ownership + row-per-surface)
  when a `surfaces` table exists. On a board with NO surfaces table the spec-join is vacuous and the
  reach law keys off the row's own `surface` text: an entry adapter that never mentions its surface
  has no join to police. The strategy gate is what closes that, upstream.
- Row→adapter matching reuses rule (p)'s inbound heuristic (`layer ∈ {interface, api, entry}` or the
  `INBOUND_RE` vocabulary). A stage-2 adapter deliberately written outside both heuristics evades the
  reach check — and trips surface ownership instead, because then no inbound unit names its surface.
- The gate never checks WHICH mechanism the architect chose for a capability token: that judgment
  belongs to the tech-stack skill, and a stack-neutral validator naming frameworks would be the leak
  the security phase exists to prevent.
- `skill`-level: `security-strategy/SKILL.md` is at 995/1000 words (its own Q7b cap) — the next
  rule added there must displace one.
- `.opencode/skills/read-write-file-ddd/writer-architect-file/scripts/writer_architect_file.py` is
  **unreferenced dead code** whose strategy/task contracts contradict the live ones (it refuses the
  real strategy for `language`, `tech_stack`, `observability`, and expects
  `module_layout.packages` to be a list). It now carries a docstring naming the live contract;
  deleting it is a separate, argued call.

## 6. Verification

```
python3 gauntlet/run_gauntlet.py        → SKILL-SCRIPTS 92/92, ENGINE-DECISIONS 229/229, GAUNTLET: ALL GREEN
python3 /tmp/opencode/probe_fix.py     → 16/16 (A1-A9 strategy+spec joins, B1-B7 placement/reach/assertion)
python3 -m py_compile orchestrators/*.py → ok
```

## 7. Same day — rule (y) stopped recalling: `tech-stack-architect/spring-security-architect`

The placement laws made the architect OWN the mechanism sentence, which exposed the next hole: it had
no table to copy from. `java-springboot3` (2353 words of stack law) contains zero security mentions,
and the security profiles are denied every stack skill — so phase 2 was naming Spring classes from
memory, the one place a wrong identifier becomes a frozen test nobody can edit.

**Tier split, and it was trimmed to it.** The architect's file carries *planning facts only*; the
idioms that only run at write/test time live in the skills that run them:

| file | loaded by | holds |
|---|---|---|
| `tech-stack-architect/spring-security-architect` (65 lines / 944 words) | architect phase 2 (granted
`spring-security-architect: allow`) | token → `unit_kind` + layer + the mechanism IDENTIFIER the intent must spell verbatim + token-triggered key;
the 4 build coordinates with their scopes; the import boundary; the chain bean signatures; the DAG order;
the route-vs-row trap |
| `tech-stack/spring-security` (66 lines) | coder stage 2 and tester stage 1, via a one-line pointer in
`coder-framework/java-springboot` §Security units and `tester-framework/java-junit5` §Security tests | the
chain DSL (`authorizeExchange…anyExchange().denyAll()`, `oauth2ResourceServer`, `.x509`, `.csrf(`,
`sessionManagement`, `SecurityWebFiltersOrder`, `exceptionHandling`), the single Spring-importing principal
adapter (fail CLOSED), `Cipher` AES/GCM/NoPadding + envelope + delegating encoder + `${ENV}` custody, and
the `spring-security-test` permitted / denied / CROSS-OWNER cases with the opaque-body assertions |

Content decisions worth the pin: **4 token groups are recorded as "no framework mechanism"**
(`field-encryption`/`envelope-encryption`, `tokenization`, `external-key-store`, `opaque-reference`) —
an honest `none` is what stops an invented class. Every cited property path was checked against
`spring-configuration-metadata.json` in the Boot 3.5 artifacts on disk; only token-triggered keys are
listed, the standard Boot defaults were dropped from the planning file. The headline row of the table
is the hole itself: exchange authorization decides a ROUTE, never a ROW.

Pins: **Q21** every declared capability token has a mechanism row · **Q22** unrealizable tokens say so
· **Q23** the delta classes are present (coordinates + test scope, both chain bean signatures, the
port/adapter duty, the trap) · **Q24** cited keys exist in Boot's metadata (skips, never passes
blindly, when no Boot jar is installed) · **Q25** the architect is actually GRANTED the skill and both
profiles name its path · **Q26** the TIER SPLIT is enforced: no execution DSL in the planning file,
and the idioms really present in the coder and tester skills. **S26** pins the architect's stated
budget to the engine's (12 → **13**: a mandatory seventh skill inside a twelve-call phase was a
budget lie, and the plan phase had already overrun at 19/12 live).

**Same pass, second trim (the tier law enforced).** The first draft still carried execution vocabulary
in the planning file: the CSRF/session posture DSL decision, the bean-body chaining, the test configurers.
All of it moved down a tier — the architect file now holds **65 lines / 944 words** (from 117 lines / 1670) and zero DSL (the statelessness
choice is `tech-stack/spring-security`'s `.csrf(…)` / `.sessionManagement(…)` /
`SecurityWebFiltersOrder` section; the mock configurers are the tester's), and **Q26** pins both halves
of that sentence: a forbidden-token scan over the architect file (`.csrf(`, `sessionManagement`,
`SecurityWebFiltersOrder`, `oauth2ResourceServer(`, `NoOpServerSecurityContextRepository`,
`Cipher.getInstance`, `mutateWith(`, `@WithMockUser`, `SecurityMockServerConfigurers`, `with(csrf())`,
`stateless`) plus a required-token scan over `tech-stack/spring-security`, so the mix cannot creep back.
The first pass deleted `tech-stack/spring-security` as a dead placeholder; it is restored as the
coder/tester-tier skill that now holds everything the planning table must not carry.

Still open: Python and TypeScript have no architect-tier security table, so rule (y) on those stacks is
still naming from memory.

### 7.1 The skill-id collision this exposed (worth remembering)

Both Spring security files were named `spring-security`. The loader keys skills by **name**, so the
second one registered REPLACED the first under the same id — `spring-security: allow` then handed the
architect the coder/tester bodies file, and phase 2's mapping table disappeared without an error.
Fixed by tier-distinct names (`spring-security-architect` for the planning table, `spring-security` for
the bodies/tests), with **Q27** pinning the pair: distinct `name` fields, distinct folders, the grant
naming the architect-tier id, and both framework skills carrying the security file's exact path (their
profiles forbid folder-searching, so an unreferenced file is an unread one).

Note the repo already carries same-name pairs across tiers (`java-springboot`, `python-fastapi`,
`typescript-nestjs`) — those are latent versions of the same bug: whichever one the loader registers
last is the one every grant by that name receives.

### 7.2 The paraphrase gap inside the mapping table (Q28)

The placement laws were fixed, but the table itself still had seven rows naming their mechanism in
PROSE - "role/authority authorization manager bound to the route", "the chain's terminal deny-all
clause", "delegating password encoder bean". That is precisely what rule (y) refuses: a paraphrase
copied into an intent is a citation with nothing mapped, and the emit gate only sees the
`spec_ref` + `capability` pair - it cannot tell whether a real identifier stands behind it.

| token | mechanism cell now spells |
|---|---|
| `device-credential-proof` | `httpBasic` + `ReactiveAuthenticationManager` (or `ReactiveUserDetailsService`) |
| `mutual-tls-proof` | `x509` + `SubjectX500PrincipalExtractor` + `ReactivePreAuthenticatedAuthenticationManager` |
| `role-check` | `ReactiveAuthorizationManager.hasRole(...)` - or `@PreAuthorize` with `@EnableReactiveMethodSecurity` |
| `scope-check` | `ReactiveAuthorizationManager.hasAuthority("SCOPE_...")` via `JwtGrantedAuthoritiesConverter` |
| `deny-by-default` | terminal `anyExchange().denyAll()` (servlet `anyRequest().denyAll()`) |
| `hashing` | `PasswordEncoder` = `PasswordEncoderFactories.createDelegatingPasswordEncoder()` |
| `error-code-only` | `ServerAuthenticationEntryPoint` + `ServerAccessDeniedHandler` on `exceptionHandling` |

The audit found the same defect in six more rows, also fixed: `tenant-scoped-query` /
`owner-scoped-query` (`@Query(":tenantId")`, `DatabaseClient.bind(...)`, never concatenated SQL),
`key-separation` and `credential-rotation` (`SslBundles.getBundle("<purpose>")`, re-read rather than
cached), `audit-event` (`AuditPort` fed by an `ApplicationEventPublisher` listener),
`metric-tag-bound` (`MeterRegistry` behind a `MeterFilter`/`TagFilter`), `log-redaction`
(`RedactionPort`), `boundary-validation` (`jakarta.validation` + the `@Valid` ACTIVATION) and
`typed-deserialization` (`activateDefaultTyping` OFF on the codec's `ObjectMapper`).

**Q28** pins those identifiers row by row; **Q28b** is the general law - a row is either marked
`no framework mechanism` or it contains a backticked identifier / annotation / call shape, so bare
prose in that column fails the suite. The planning file stays DSL-free (Q26): the IDENTIFIER is a
planning fact, the composition of it belongs to the coder.

### 7.3 The dead branch: "or a reported risk" (Q28c/Q28d, SA1-SA7)

Reviewing the table's four `no framework mechanism` rows raised a question the wording could not answer:
if Spring realizes nothing, what discharges the duty? Four documents said "an added unit **or a reported
risk**". That second branch was unreachable twice over:

1. `task_queue._security_claim_errors` refuses any duty claimed by no unit — and it is unconditional:
   duty closure at spec-creation time guarantees every rule has a duty, so every rule ends up needing a
   unit;
2. the refusal's own remedy said *"or amend the spec"* while the architect's `edit:` grant is
   `execution-strategy-*.json` + `/tmp/**` only — the message ordered a write the session cannot perform;
3. and `risks[]` was read by nothing at all: `ddd.py` required the KEY to exist and counted `R-\d\d` as a
   resolvable `spec_ref` target, but no gate, pipeline line, or report consumed its contents. The
   security step's own posture rule ("never weaken a control to fit an implementation: record the
   conflict") points AT that field, so the honest channel was a write-only array.

Fixed on all three counts:

| change | where |
|---|---|
| Every unrealizable row now names its **DAG home and the assertion that proves it**: crypto → infrastructure `AesGcmPayloadCipher` adapter, real-substrate test asserting the stored column is not the plaintext; `tokenization` → `SurrogateReferenceStore.mint(...)`; `opaque-reference` → `OpaqueReferenceGenerator.next(...)` (the "not a security unit" cell that contradicted `(y1)` is gone); `external-key-store` / `credential-rotation` / `key-separation` → the **CONFIG unit**, tested by the absence of any literal | `tech-stack-architect/spring-security-architect` |
| A `unit_kind` → one-DAG-home map covering all nine shapes in `ddd.SECURITY_UNIT_KINDS`, so no duty arrives with a kind nobody owns | same file |
| `risks[].mitigation` must cite an entry this spec declares **or** state an accepted posture (`accepted:` / `none:` / `operator:` / `out-of-scope:`) with a non-empty `residual` — dangling, empty, and residual-less are all refused at the spec gate | `orchestrators/ddd.py::_security_risk_errors` (law six) |
| The pipeline prints the register on EVERY launch — fresh phase, skipped phase, and the resume path where the spec was already valid and nothing printed (`[risk  ] <slug> R-01: … -> ACCEPTED, not mitigated: …`) | `orchestrators/pipeline.py::_surface_security_risks` |
| The unclaimed-duty refusal no longer sends the session to amend a file it cannot write: it names the lawful landing unit (config / store / domain) and says a risk never substitutes for a claim; a genuine spec defect goes to the operator as "re-run the security phase" | `orchestrators/task_queue.py` |
| The four "added unit **or** a reported risk" sentences (both architect profiles, the phase-2 prompt, the table's Scope) now read: the unit is mandatory, the risk is a disclosure beside it | profiles, `prompts.py`, the skill |
| `SECURITY_PROMPT` step 4 tells the author the rule while it can still act on it | `orchestrators/prompts.py` |

Pins: **SA1-SA7** (register law, accepted-posture path, pipeline surfacing including the resume branch,
refusal wording checked against the profile's real write grant), **Q28c/Q28d** (every unrealizable row
names a home + assertion; the kind map covers all nine kinds; "not a security unit" may not return).
Gauntlet: **98/98 + 236/236.**

### 7.4 A servlet API inside the reactive example (Q29) - and a pin that was blind at first

Reported by review, confirmed against the API before touching anything:
`ServerHttpSecurity.SessionManagementSpec` exposes **`concurrentSessions(...)` only** (since 6.3) -
there is no `sessionCreationPolicy(...)` setter and no `SessionCreationPolicy` enum on the reactive
type (that is `o.s.s.config.http`, servlet). Yet `tech-stack/spring-security` §Chain DSL told the
coder, inside the WebFlux chain, to write

```java
.sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))   // does not compile
```

WebFlux statelessness is the **context repository**:
`.securityContextRepository(NoOpServerSecurityContextRepository.getInstance())`. Verified against the
javadoc while fixing: `ExceptionHandlingSpec.accessDeniedHandler(ServerAccessDeniedHandler)` and
`AuthorizeExchangeSpec.Access.denyAll()` DO exist (the architect table's names stand), and the
reactive `x509` defaults are `SubjectX500PrincipalExtractor` +
`ReactivePreAuthenticatedAuthenticationManager`.

Two secondary defects the same fix surfaced, both of which a coder would have paid for:
1. an identifier split across a line break inside a code span
   (`NoOpServerSecurityContextRepository\n.getInstance()`), which is not copyable;
2. a stray double backtick that unbalanced the section's code spans - the reason the new pin started
   reporting a violation the file did not have.

`# Chain DSL` is now two labelled blocks - `### WebFlux (ServerHttpSecurity)` and
`### Servlet (HttpSecurity)` - and the file says out loud that the servlet policy line does not compile
in the reactive chain.

**Q29** enforces it per BLOCK over CODE SPANS: no servlet-only identifier may appear inside a backticked
span of the WebFlux block, and no reactive-only identifier inside a span of the Servlet block (prose may
still name a forbidden type to forbid it). The case carries a **self-test**: the original buggy section,
fed through the same predicate, must report violations - because my first version of this pin scanned
*lines*, and a DSL chain is written across lines: the line-scoped check would have passed the very bug
that motivated it. **Q29b** pins the corrected facts (context repository = statelessness,
`sessionManagement` = concurrent sessions only, the servlet policy inside the servlet block, the
"does not compile" warning).

**Follow-up (same section, found in review).** The block split left a *third* defect: the old tail
sentence - "Never `block()` / `.blockFirst()` in an auth path, and never subscribe inside the chain" -
ended up stranded at the bottom of the **Servlet** block, where those constructs do not exist, and
duplicated the reactive rule that also closes the WebFlux block. It is now stated once, inside the
WebFlux block, labelled `Reactive-only, so it does not belong to the servlet block below`, and pointing
at `coder-framework/java-springboot` §Reactive for the subscription rule.

Why the pin missed it is the more useful half: Q29's reactive vocabulary listed chain TYPES
(`ServerHttpSecurity`, `SecurityWebFilterChain`, `NoOpServerSecurityContextRepository`, …) but no
reactive-only **operators**, and the file's own boundary sentence is not a type. So
`block()`, `blockFirst` and `subscribe(` joined `_REACTIVE_ONLY`, and Q29 gained a second self-test
feeding the stranded sentence through the predicate. A mutation check confirms the case now depends on
those tokens: with the pre-fix vocabulary the stray line reports no violation at all. (The first cut of
those tokens was written as `` `block()` `` - with backticks - and the scan compares against
span CONTENT, backticks already stripped, so it could never match; corrected to `block()` /
`blockFirst` / `subscribe(`, verified against the real sentence. `subscribe(` matches only when
the word is written as code, which is the intended scope: prose is not copied, spans are.

Gauntlet after the fix: **106/106 + 250/250.**

## 8. "Is security always implemented — and only omitted when the description says so?"

Audit question, answered in two halves.

### 8.1 The enforcement was already unconditional (verified, not assumed)

| layer | evidence | effect |
|---|---|---|
| phase order | `pipeline.run` loops the security phase over every planned domain; `_security_reason`: "the spec is mandatory for every domain" | no exemption by default |
| no operator escape | `build_parser` has no security-related flag (`--seed --output --force --watch --interval --timeout --verify --verify-scope --verify-timeout --limit --parallel --emit --retry --replan --skip-docker-check`) | not even a human can skip it |
| absence is fatal | `validate_security_spec` → `"security spec not found"`; phase prints `[fatal] security <slug>` and returns 1 | a phase that did not run stops the run |
| an empty spec is illegal | `authorization_matrix is empty`, `duties is empty`, duty closure, deny-by-default per row, the risk law | "nothing needed" cannot be written |
| claims are mandatory | closure + `(y1)/(y2)/(y3)` + surface ownership; predating boards `[fatal] … claim gap(s)` + `--replan` | a lawful spec cannot be decomposed away |

### 8.2 What was missing, and the hole that mattered more

1. **The waiver did not exist and could not be expressed.** No opt-out anywhere; and a spec author obeying "this seed needs no security" would produce either an invented row (refused by its own posture law) or an empty matrix/duties (refused by the gate) → `[fatal] security`. The flow turned the user's sentence into a crash.
2. **The input never reached the deciders.** Only discovery reads the description (`DISCOVERY_PROMPT` embeds it); the architect, the security phase and the emit gate read board artifacts, and the slice schema had no field to record a directive in.
3. **A domain could vanish without anyone noticing — the real threat to "always".** `database_slugs()` is derived from `execution-strategy-*.json`, and every later loop (database, **security**, and the claim gate's project set) iterates that list. Phase 1's post-check only asked whether *some* strategy existed. Four slices, three strategies → the fourth domain got no spec and no tasks, and `_security_claim_errors` skip (a) treats "no spec file" as a legitimate skip. A green drain, an unplanned domain. `validate_context_maps` already enforced a map per slice one phase earlier; the strategy counterpart had never been written.

### 8.3 What now holds

| piece | where |
|---|---|
| `security_directive{required, quote, source:"description"}` — optional slice key; shape refused at the writer (boolean decision, ≥20-char verbatim sentence, `source` must be the description) | `writer_file.py` (`SLICE_OPTIONAL_KEYS`, `validate_security_directive`) |
| the waiver is honoured only when the quote is found **verbatim** (whitespace/case-normalized) in the file named by `metadata.source_description`; unverifiable, unreadable or paraphrased ⇒ not waived, and the reason is returned to the discovery post-check that can still fix it | `ddd._waiver_note` / `security_waived` / `validate_security_directives`, wired into `validate_domain_files` |
| the security phase prints `WAIVED by the business description - "<quote>" (<file>)` and continues; no spec, no duties, nothing to claim | `pipeline.run` |
| the terminal verdict carries `SECURITY WAIVED by directive`, so a green run never reads as defended | `pipeline._terminal_tree_report` |
| a discovered slice without a strategy is FATAL (phase-1 post-check on both backends + a pre-database pipeline check), and coverage is verified BEFORE any waiver branch can skip anything | `ddd.validate_strategy_coverage` |
| a waiver recorded AFTER a spec exists discloses its own contradiction: the phase prints that the
   on-disk spec is stale and names the fix (remove it or `--replan`), the terminal verdict appends
   `BUT A SPEC IS ON DISK`, and until it is archived the emit gate keeps demanding its duties be
   claimed - the conservative reading, never a silent relaxation |
| the law is stated where each agent reads it: discovery prompt ("you do not decide it, you transcribe it"), both discovery profiles, the discovery skill, the architect's phase-2 brief (absence is either a waiver or a flow defect, report which) | `prompts.py`, profiles (both mirrors), skill |

Deliberately **not** built: keyword detection of "no security needed" in the seed text, and any engine flag. A waiver that rests on pattern-matching prose or on an operator's switch is how a security phase disappears quietly; here it rests on a sentence the engine can find in the file the user supplied.

### 8.4 Pins

**SB1-SB7** (engine): absent directive = required; missing strategy refused and cleared per slug; verbatim waiver honoured and its note names the quote and the file; paraphrase refused with the reason routed back to discovery; unverifiable waiver ⇒ the phase runs anyway; pipeline branch + terminal marker + both backends' post-check (source and ordering assertions, chosen over a full `run()` simulation, which would bill agent sessions).
**SC1-SC4** (skills): writer shape refusals; absent-vs-valid waiver; the law present in prompt + both profiles + the skill; and the waiver is unreachable from the phases that would want it (only the slice writer accepts the field; the spec gate still answers `security spec not found`).
**K1-slice** now requires the discovery docs to teach `security_directive` and `source_description`, so the doc-vs-schema pin fails if the field is ever dropped from the instructions.

Gauntlet: **104/104 + 246/246.**

## 9. The plan phase measured, then cut (token audit of 35 real architect sessions)

**Method.** `session_audit.classify()` isolated 35 sessions whose first user message *is* the
architect prompt (a naive grep matched my own development sessions too). Every tool call was then
attributed by `size × the turns that re-sent it` — the transcript is re-sent per turn, so residence,
not size, is the price. That logic now ships as `session_audit.py --burn-report`.

| measured | value |
|---|---|
| architect input | 7,766,593 tok — **85% cache reads**; 1,158,145 re-priced |
| architect output | **430,171 tok** ← the class that actually costs |
| worst single-turn output (2026-11-16) | **40,442 tok** — one draft file, one turn |
| emit-refusal rate | TASKS **19/36 = 53%**, STRATEGY 12/30 (pre-skip-(c)) |
| the one-domain plan | 23,585 tok of JSON; **`intent` = 52%** (13,378 tok), `ast_hints` 29% |
| folder hunting | 45 calls, **226,027 tok carried**, 12 failed loads returning 48-tok errors |
| skills | 826,184 tok carried (11% of input) — `java-springboot3` 455K, `task-decomposition-dag` 241K |
| contract evasion | **4 of 35 sessions wrote generator scripts** (`gen.py`, 39K tok carried) to avoid hand-writing 57 tasks — and then patched them blind, because the draft never entered the transcript |

**What was changed (all pinned).**

| # | change | evidence behind it |
|---|---|---|
| F1 | **one draft file per bounded context, all in a single `--emit` batch** (the runner already took `nargs="+"`, so zero engine change) | 40,442-tok turn → largest context is 8,283 tok (−65%); SD1 proves a pin whose producer lives in *another* file still resolves and SD1b proves ids stay one namespace, so batch-wide rules (provider closure, security reach) are untouched |
| F2 | refusal remedy = **edit the named task objects**, never regenerate | measured in the same sessions: a draft write cost **13,288 tok of output**, an edit **256–448 tok**; SD3 pins the new text and keeps the batch-report law that prevents re-emit loops |
| F3 | **intent wall**: target 40–80 words, **180 refused at emit — planning only**, resumed boards stay readable | intent = 52% of the plan; 3 records on the current board exceed it, all in `complete/`, queue empty, so no live record is retroactively illegal (SD2) |
| F4 | profile lists **exact skill paths per phase** and forbids reading the other phase's | 45 hunt calls / 226K carried / 12 failed loads; the security profile was already the proof (paths given → 8 calls). Q30 asserts every path resolves |
| F5 | rule (y) prose in the profile compressed now that the mechanism table + the gates carry it | profile body 4,165 → **3,871 tok** *while* the phase-path block was added; net of this week's security growth (2,499 at HEAD) it is +1,372 tok of genuinely new law, ~300 tok of it now recoverable |
| F6 | **phase 2 stops re-reading phase 1's inputs**: the tasks prompt now names the strategy and the spec as its inputs and forbids the slice/map re-read unless a concept is genuinely missing (then: report the gap, the fix belongs to phase 1) | the burn report's single LARGEST item: `view domain-boundary-….json` = 44,943 raw tok carried **381,965 tok = 11% of all architect input**, and the profile had never asked for it — the phase-2 prompt was ordering it, contradicting the profile | Q31 |
| — | `session_audit.py --burn-report [--role X] [--since-hours N]` | the re-measurement is now one command, per item, per role |

**Still open, quantified, deliberately not done.** The profile re-lists the 25 refusal classes
(a)–(y) in its own words (≈3.0–3.5K tok/turn) while `task-decomposition-dag` carries the full contract
(8,188 tok) — literal sentence overlap is ~0, semantic overlap is total. Deleting the profile's restatement
is the single largest remaining trim, but it requires rewriting **Q14**, whose `ARCH_MARKERS == a..y`
assertion is what currently guarantees the profile's one-line-per-rule scannability. And phase 2 still
carries ~16.2K tok of skills; that is the floor unless the skills themselves are compressed.

### 9.1 After the change (static, verifiable now; the session numbers need the next drain)

| carrier | before | after |
|---|---|---|
| architect profile body (resident every turn) | 4,165 tok (2,499 at HEAD) | **3,961 tok** — while gaining the per-phase path block and the waiver/placement law |
| phase-2 prompt | 5,585 tok | 5,548 tok, and it no longer orders a ~5.8K-tok slice re-read |
| skills the profile asks for | "load all" (18,147 tok if obeyed) in **both** phases | phase 1 **6,446 tok**, phase 2 **16,218 tok**, each at exact paths |
| draft emission unit | 23,585 tok in one file | **8,283 tok** worst-case (largest context), one batch |
| refusal remedy | full rewrite: 13,288 tok output | edit pass: 256–448 tok output |
| intent volume | unbounded (mean 100 words, max 276) | target 40–80, **180 refused at planning**; resumed boards unaffected |
| re-measurement | manual forensic pass | `session_audit.py --burn-report --role architect` |

Pins added this round: SD1/SD1b (per-context files, one batch, one id space), SD2 (the wall bites at
planning, never at resume), SD3 (edit-not-rewrite text), Q30 (paths per phase, and they resolve),
Q31 (emission shape + intent law in all three carriers + phase 2 reads only strategy and spec).

---

# Addendum — the afternoon: the security layer's first live drain

Method: a fresh board (folders cleaned, project deleted), seed-002, GitHub Copilot backend,
supervised stop-the-line. Every defect was reproduced against the LIVE engine before being fixed,
every fix went to the root (law/carrier/tool, never artifact bytes), and every root became a
gauntlet case per the repo rule. Gauntlet at the end of the day: **SKILL-SCRIPTS 111/111,
ENGINE-DECISIONS 264/264, ALL GREEN.**

## A1. The verdict the day was built to produce

**`agent-security-architect` does its job.** After one lawful-but-doomed first session (see D2):
one session, 8/8 calls, spec gate-clean — 3/3 matrix rows keyed verbatim to the strategy's
`surfaces`, deny-by-default, ownership predicates, principals traced VERBATIM to the slice,
10/10 fail-closed invariants, 13/13 rules discharged by 18 duties under 12 abstract tokens,
zero framework vocabulary, zero `open_questions`, four risks each control-backed or stated as an
accepted posture with residual. Downstream: the tasks phase emitted with **zero refusals**, claimed
25 distinct spec refs/tokens with correct (y)/(y1)/(y2)/(y3) placement, and the live-board gap scan
reads 0. Every failure the drain then hit traced to a seam DOWNSTREAM of its artifact — the agent
was innocent of all of them except one, and that one was its skill's own schema placeholder.

## A2. Defect catalog (symptom → root → fix → pin)

| # | symptom (live evidence) | root | fix | pin |
|---|---|---|---|---|
| D1 | first launch died pre-session: `Unrecognized flag: --dir` | OpenCode v2.2.5 removed `--dir`; command shape was written for the old CLI | build via subprocess cwd (which `run_agent` already sets); echoes matched | none (flag day; backend switched per operator) |
| D2 | `[fatal] security`: spec refused — `assumptions[N].source` names `domain-boundary-….json` | the skill's OWN machine reference taught `"<input file or baseline rule>"` while `SECURITY_LEAK_RE` refuses file names — schema instructing an author INTO the gate | placeholder rewritten to the concept form, naming `metadata.inputs` as the sole file-citation exemption | Q2b + S11 (assumption-source case) |
| D3 | plan phase: `gen_telemetry_tasks.py` (91k carried), heredoc patch loops, **41,451-tok worst single-turn output**, DAG skill loaded ×3 | the tasks brief said "write a single JSON document" for the whole domain while step 3 said per-context — the contradiction made hand-writing feel impossible; no carrier banned scripts (the §9 hole) | draft_rule rewritten (direct writes, per-context, one batch); ban + evidence in brief and BOTH profiles | SD4 |
| D4 | first red compile imports `org.springframework.security.*` → FatalPipeline, every gate would fail forever | the planning table ordered a "stage-0 build-manifest duty" the tasks brief FORBADE ("Do not emit stage 0") — a duty with no lawful channel; container `edit:{"*":deny}` meant nobody could touch the pom | one lawful exception in brief + both profiles + the table's channel wording; fatal now NAMES the remedy; duty emitted via `--emit` (T0-007) | SD5 |
| D5 | relaunch died at the resume gate even with the duty queued; a package no file imports (`shared.audit`) blocked forever | the gate reads the PRE-duty pom before the drain (deadlock by construction); recovery only re-recorded when the repair *changed* a file — a reroute-clean file kept its stale verdict | `BUILD_FILE_NAMES` + `_manifest_duty_pending` deferral (`[defer ]`); re-record UNCONDITIONAL (zero-session) | SD6 |
| D6 | `[done] T0-007` in 55 s with the pom untouched | stage-0 completion is file-EXISTENCE - true for created artifacts, meaningless for a MUTATION duty whose file always exists since the scaffold; the container's honest "no pom was moved" read as delivered | `_build_manifest_duty` (export ≠ `project_scaffold`): skip-guard exempted, mtime-at-session-start verification, failure named as what it is | SD6, SD7 |
| D7 | container halted mid-duty: `unknown --require entry 'spring-security-test'` | the scaffold tool's require table knew only `test`/`reactor-test` — the security tier's own coordinate was not deliverable | table extended (BOM-managed, test scope, verified by direct `transform` run) | P4b |
| D8 | T2-029 quarantined + 13 cascades: `'permits' cannot be used as an identifier as it is a keyword` | JavaParser 3.25.10 at BLEEDING_EDGE rejects a JLS-LEGAL restricted identifier used as a method name; the frozen test compiled fine with javac — tool strictness, not plan, not code | javaparser → 3.26.4 in the weaver AND the extractor (same setting, same blind spot); regression case in the weaver's own suite | weaver `weave_methodNamedPermits_*` |
| D9 | fatal "scheduling hole … run closure.py --emit" on a healthy domain at task 8 | `import org.springframework.r2dbc.core.Parameters` - a class missing from an EXISTING package is not schedulable by anyone; the classifier saw a bare unowned token | excerpt `location: package X` pairs resolved against `external_type_index`: proven payload defect, not hole; unknown packages stay conservative | SD8, SD12 |
| D10 | all 75 units deferred on each other; the enum owner was never charged | attribution read only `member_demands`, and the normalizer EXCLUDED `symbol: variable` wholesale; nested owners collapsed to `Inner` (`TelemetryEvent.Type` → `Type`); `owner != export` never matched a qualified spelling | tool emits `variable` demands (only when the located class ≠ the failing file's own type); `OUTER.Inner` preserved; engine `_owner_matches_export` + `_unambiguous_member_demand` (a javac-proven member of MY type is charged even when every blamed file is a peer's call site — method demands keep the seed-002 wait) | G18, SD9 |
| D11 | a T2-019-class own-file import error still deferred: the ANY-foreign cascade rule | own-file symbol misses read as "cascade from a foreign definition" even when the symbol lives in an EXTERNAL package no peer can produce | `_own_hallucinated_import`: classpath-proven bad import = structural to the owner, charged | SD12 |
| D12 | zero-progress passes after the memo version bumped: full evidence in the log, zero demands in the field | the per-unit memo version moved, the WAVE cache's grammar stamp stayed a literal `v9` in three places — the wave replayed PRE-demand verdicts tree-wide | `WAVE_GRAMMAR` constant (one source, all three doors); wave verdicts may not carry a status the memo can launder - phantom `not_run` serve on OSError removed too | SD10, SD11 |
| D13 | every gate began returning `status=error, tests=0`, blame `ForkStarter.java` | an operator SIGTERM mid-build left a truncated `.class`; every fork died at LOAD, and the machinery laundered that empty verdict into memo + wave + ledger signatures - tooling damage charged as forty unit failures | `_fork_boot_corruption` (surefire dumpstream marks): scoped gate wipes `target/` and re-runs BEFORE any memo/publish; the wave and terminal doors refuse to serve a corrupted boot | SD13, SD13b |
| D14 | rollback chain: `SliceTestSupport` vanished mid-drain and the whole test tree stopped compiling | a DEPENDENCY-CASCADE quarantine reverted a never-adjudicated victim's woven payload; each revert broke another unit's WOVEN-CLEAN probe, which reverted that unit — mutual destruction through mutual blame | a cascade victim keeps its payload; a dependent reverts only when the blocker's own evidence proves tree-breaking poison (`WOVEN-CLEAN`/`dependsOn` reasons never do); `[keep ]` prints the decision | SD14 |
| D15 | T2-015 burned 9 coder sessions on `variable id of type java.lang.Object` | `TelemetryMetricsTest` chained `flatExtracting` stages — AssertJ 3.27 degrades the ELEMENT to `Object` from the first hop: a FROZEN test uncompilable against EVERY implementation, invisible at red because the missing-production error masked it | tester-skill law: local typed stream projection, assert ONCE on the local; T1-015 was REOPENED (record + red record + the tester-owned file removed) and the **tester itself regenerated the test** - the new file verified to use the lawful pattern | P5b |
| D16 | after D15/D14 healed: all 8 slice tests boot, then die `SSL is enabled but no trust material` | `mutual-tls-proof` was claimed, `server.ssl.client-auth` was written, and NO unit contract owned the test-boot substitute — the per-unit gates could not see it (the yml unit's own test does not boot the server; the slice cannot fix the yml) | bootability law in BOTH security tiers: the planning table assigns the substitute to the slice-support contract; the execution file says HOW and what must never be neutralized (chain/authorization/codec stay asserted) | Q32 |

## A3. The artifact-discipline incident (worth remembering)

Mid-D15 I hand-edited the frozen test and the delivered pom's absence-of-fix hid behind my edit.
The operator rule held: **the delivered tree carries flow bytes only.** Both edits were reverted;
the test was repaired the lawful way (reopen the contract to its author agent, board-state moves
exclusively: `mv` between queue/complete, red-record removal, payload-owned file removal so the
tester re-authors, `--emit` for new duties, ledger removals where the world that produced the
signature was tooling-poisoned). Nothing in `projects/` was written by supervision.

## A4. Token accounting (measured, `session_audit --budget-report/--burn-report`)

- Plan phase before the fixes: architect tasks 920k in / **51.4k out** (the D3 bleed; capped by SD4 for the next plan).
- Security phase total cost of the contract clash: exactly 2 sessions (113k/11.6k refused + 153k/10.8k lawful) — D2 made structurally impossible afterward.
- Retry storms D8–D16 burned bounded sessions (3+grants per unit, replay-closes at zero cost once signatures matched) — the storm guard held; the genuine bleed was D3, not the guard.
- Budget overs persist in two informational spots (strategy architect 14/13, database 14/10 — the latter still hunts `glob tech-stack/**`; the DB profile lacks the exact-paths block F4 gave the architect). Flagged, not yet fixed.
- `agent_scratch` violations observed in coder sessions (4 calls) — noted, unpinned, low volume.

## A5. State at stop (18:10)

109/115 complete; queue 0; error 11 = the five T2/T3 pairs (017/025/033/035/037 + twins) and
T4-001. Assembly got the graph to BOOT (the 8-test starting suite runs; one `Ingress…` case red —
down from 15 errors + 7 failures; behavior-level, not plan-level). Resume command:
`python3 -u orchestrators/orchestrator_github.py --seed seed/002_description.md --watch --retry`
— it restores the family, finishes the drain, and prints the terminal tree report.

## A6. Open tomorrow, in order

1. Finish this drain; confirm the terminal gate + `--verify`.
2. A FRESH run to exercise the plan-phase laws on a real architect: manifest duty self-emitted,
   no gen.py, schema-safe spec, bootability assigned at decomposition — the true test none of
   today's fixes could receive on a board whose plan predates them.
3. The database profile's exact-paths block (D-note in A4) + the D1 CLI-shape pin.
4. README case-count refresh; consider the `agent_scratch` law.

Not a plan defect anywhere in the remaining 11: the boot gate proves the plan wires. The fresh
process is the NEXT experiment, not this run's replacement.

**⟸ THIS SENTENCE IS FALSE — retracted by the 2026-11-19 addendum below. Four of the five roots are
plan/contract defects. The evening read the cascade names (WOVEN-CLEAN) as health; the surefire
evidence under them says unsatisfiable.**

---

# Addendum — 2026-11-19 morning: STOP fired on the error board. It is plan-level after all.

Operator instruction: restart the process, determine the root problem of the `error/` tasks, and
**stop if an architect defect is detected because the skills are missing something**. The stop
condition is met, so the restart was aborted **before launching any session** — the drain would
only replay yesterday's failure signatures (the memo replays them at zero cost and the same three
roots would burn three coder sessions each). No agent was billed today; the board is frozen exactly
as left at 18:12. Method: pure forensics on the frozen evidence — error records, `attempts/`,
surefire reports, the delivered sources, the frozen tests, and the task records that wrote them.

## B1. The ledger of the 11 (+1)

Suite truth: **180 tests, 8 failures + 7 errors = 15 red across 6 test sets** (the two error
records that blame each other's aggregate were both telling half-truths):

| red set | n | owner unit |
|---|---|---|
| `IngressPacketControllerTest` | 6×400/401/403/202 expected, **got 500** | T2-025 (cascaded, WOVEN-UNVERIFIED) |
| `WindowBroadcastControllerTest` | 3× context-load ERROR | T2-033 |
| `IngestPacketUseCaseTest` | 2× `MeterNotFoundException` | T2-017 |
| `TelemetryConfigurationTest` | 1 FAIL + 1 ERROR (`users cannot be null or empty`) | T2-035 (cascaded) |
| `IngressRequestPathSliceTest` | 1 FAIL (`expected 1L but was 5L`) | T1-037's slice; T2-037's support |
| `TelemetryIngestionApplicationTests.contextLoads` | 1 ERROR (`users cannot be null or empty`) | scaffold smoke; blocks T4-001 |

T3-017/025/033/035/037 are pure `dependsOn` cascades. T4-001 sits in `queue/` (moved back at
18:14 after one attempt) and cannot close: its gate IS the slice, and the slice is red.

## B2. The five roots, each traced to its contract (coder-innocent)

**R1 — T2-017, the meter-name collision.** The frozen use-case test asserts
`registry.get("telemetry.samples.validation_failed")` and `"telemetry.revisions.appended"` — which
is what the ARCHITECT's own documents spell: T2-015 intent ("Meters: … telemetry.samples.
validation_failed(metric), … telemetry.revisions.appended(reason) …") and T2-017's `semantics` line
name them identically. The delivered `TelemetryMetrics` registers `telemetry.validation.failed` /
`telemetry.revision.appended` / `telemetry.window.broadcast`, and the D15-REGENERATED T1-015 test
pinned those drifted names. The use case receives only `TelemetryMetrics` (its constructor has no
`MeterRegistry`), and the façade + its test are gated artifacts T2-017's coder may not touch. **No
lawful implementation of T2-017 can make its frozen test pass.** Three sessions burned on an
unsatisfiable contract — correct engine behavior, wrong board.

**R2 — T2-025, the route-path collision.** T1-025's frozen test posts `/ingress/packets`; the plan
spells the route `/telemetry/ingress` in THREE places (T2-024 chain intent, T2-025 controller
intent, T1-037 slice). With the gated chain's `anyExchange().denyAll()` and its custom
entry-point/handler, no controller mapping makes the test's URI answer 400/401/202 — the board
observed 500s for all six. Same defect class as R1: the identifier lives in prose in one unit and
in a frozen test in another, and nothing joins them.

**R3 — T2-033, the slice-that-imports-the-chain.** T1-033 `@WebFluxTest`s the controller and
`@Import`s the gated `TelemetrySecurityConfiguration`, whose bean method demands the CONCRETE
`DeviceCredentialAuthenticationManager`. By the plan's own wiring law — T2-035 intent: *"sole
registration mechanism for non-controller beans"* — that bean exists only inside
`TelemetryConfiguration`, which a WebFlux slice by design excludes. `NoSuchBeanDefinitionException`,
×3. The sibling test T1-025 solved the identical import by `@MockBean`ing the manager: two answers
to one question, both frozen, no law deciding it. Q32 (yesterday's bootability fix) assigned the
test-boot substitute for the **mTLS full-graph boot** and stopped there; chain-dependency supply in
CONTROLLER SLICES is unassigned in both security tiers.

**R4 — T2-035 + `contextLoads`, the credential-shape contradiction (architect-authored).** Two
halves, one surface:
- The ARCHITECT wrote both incompatible contracts: T2-034 pins `devices`/`consumers` as
  `List<Credential(id, secretHash, scope)>`, while T2-036's intent dictates the yml as
  `devices: secret-hash: ${TELEMETRY_DEVICE_SECRET_HASH}` — a scalar map that (a) binds to nothing
  and (b) could not carry an id+scope even if it could. One env var cannot hold a triple; the plan
  never says where device IDs and scopes come from at runtime. Result: a plain boot has ZERO
  credentials, and `new MapReactiveUserDetailsService([])` throws `Assert.notEmpty` → the
  scaffold's `contextLoads` can never pass → T4-001's terminal gate has a permanent red.
- The frozen T1-035 test then asserts the context `hasNotFailed()` AND
  `hasSingleBean(MapReactiveUserDetailsService)` **with no credential properties supplied at all**.
  Spring's constructor law makes that pair unsatisfiable by any fail-closed implementation; the
  only way to "pass" is fabricating a sentinel principal — forbidden by the spec's own posture.
  (Note test 3, `context_blankDataKeyOutsideTestProfile_failsToStart`, is GREEN **for the wrong
  reason** — it fails on `userDetailsService`, never reaching the data-key guard. A passing test
  laundering a different defect is exactly the pattern §8 was built to end.)

**R5 — the slice's global counts on shared state.** `IngressRequestPathSliceTest` asserts
`COUNT(*) == 1` and `MAX(revision_number) == 2` against one named H2
(`DB_CLOSE_DELAY=-1`, same `device-1/temperature` row) written by five tests of the same class, with
no isolation, no cleanup, no `@TestMethodOrder`. Whether it passes is JUnit method-sorter luck; the
log shows the revisions of one fork climbing 2→3→4→5, and the victim line saw 5. T2-037's coder
cannot fix this from production code; the support unit's own contract is the problem.

## B3. What the skills/gates are missing (the stop's substance)

One class, five members — **shared identifiers are carried in prose, not in machine fields, and no
emit gate joins them across units**:

1. **Single-owner vocabulary law.** Every cross-unit identifier (meter name, route path, config
   property SHAPE) must live in the OWNING unit's machine field (`ast_hints.methods[].semantics` or
   a dedicated table) and be cited VERBATIM by consumers; the emit gate must refuse a board where
   two units spell one surface differently. Precedent to clone: rule (y) already does exactly this
   for surfaces→rows→adapters — it simply has no analogue for the observability/HTTP/config
   vocabulary. (R1, R2, R4a.) Note the tester skill's law *"the meter NAME is the contract from
   ast_hints"* is currently a null pointer: T2-015's ast_hints carries NO meter names — the names
   exist only in its intent prose.
2. **Bootability with empty custody.** The security planning table must refuse a custody design
   that cannot deliver the credential STRUCTURE (id+hash+scope), and must decide, per profile,
   what an EMPTY credential store means: fail-fast at boot with a named remedy (then the scaffold
   smoke test needs profile-scoped seed properties) or seeded test-profile credentials in the yml
   contract. A frozen test asserting "bean exists" over a Spring type whose constructor forbids
   emptiness is illegal at spec time — the §7.3 "no framework mechanism" honesty applies here:
   `MapReactiveUserDetailsService` has no empty-legal state. (R4.)
3. **Slice-imports-chain law** (completes Q32): a test that `@Import`s the security chain must
   supply every CONCRETE bean parameter of the chain bean (mock or real stand-in) in the same
   contract, or the chain must depend on a framework interface with an autoconfigured default. The
   DAG/config unit must not be the only place the manager exists while slices import its consumers.
   (R3.)
4. **Anti-convergence law for regens.** When a frozen test is REOPENED (the D15 channel), the
   oracle is the task's intent + ast_hints as they were QUEUED — never the delivered implementation
   standing next to it in the tree. The regen that closed D15 pinned the drifted names and made
   R1 permanent: the repair channel itself needs the law, and the `red-phase` record should store
   the intent hash it was written against (the attempt ledger's `contract` field proves the engine
   can already carry one). (R1.)
5. **Slice state-isolation law.** End-to-end slice tests over a shared in-memory store must assert
   RELATIVE deltas or own-identity rows, or carry explicit per-test cleanup/ordering — a global
   `COUNT(*)` equality freezes method order into the contract. (R5.)

## B4. Disposition (per operator: this process is done)

- **Do not resume this board.** 4 of 5 roots are unsatisfiable frozen contracts; a drain replays
  signatures and re-bills the same three roots for nothing. The five T3 twins and T4-001 are
  cascade-only and will re-queue themselves under a lawful plan.
- The fixes above belong to the SKILLS and the EMIT GATES, then a **fresh run** (item A6.2) is the
  real experiment: R1–R5 are all things a plan-phase law + gate could have refused at emit.
- Yesterday's A6 line "not a plan defect anywhere in the remaining 11" is retracted above; its
  premise ("the boot gate proves the plan wires") held for the WIRING and missed the VOCABULARY —
  the graph boots precisely because each unit obeys a different document.
- Board state at freeze: complete 110, queue 1 (T4-001), error 10, attempts: 3 consumed on T2-017
  and T2-033, 1 on T4-001. No process running; nothing was launched today.

## B5. Same afternoon — R1 and R2 closed (rules (l)/(z): the vocabulary gets fields, a gate, and every carrier)

Operator scope: fix R1 (meter-name collision) and R2 (route collision), stack-agnostically.
The diagnosis this builds on (operator-supplied, verified): the profile promised "every
stage-1/2 task carries a COMPLETE ast_hints table — prose is never the only place a signature
exists" and "meter names in the consuming unit's table", but **`ast_hints` had no schema field**
for meter names or HTTP routes — only `package, implements, dependencies, methods`. Rule (l)
named "shared literals have ONE owner" and its own Plan-validity tail admitted defeat:
*"(l)'s agreement of values written in prose… the wider letters stay the architect's duty
because structure cannot see them."* Step logs (rule (j), `observability.step_logs`) and
security surfaces (rule (y), `surfaces[].name`) had machine fields and gates; the vocabulary did
not. The strategy floor ALREADY spells meter names in a machine field
(`observability.metrics[].name` — correctly, on the live board); the corruption happened at the
floor→unit hop, the only hop with no field and no join.

**The fix — machine field + emit gate + carrier law, in that order:**

| piece | what it is |
|---|---|
| schema | `ast_hints.meters: [{name, duty: owns\|uses}]` and `ast_hints.routes: [{method, path, duty: serves\|uses}]` — optional keys (`AST_HINT_OPTIONAL_KEYS`); legacy 4-key tables stay valid (superset validation, F3 doctrine: planning bites, resume reads) |
| gate z1 | every meter name `owns`ed by exactly ONE unit; every `uses` matched VERBATIM against the owners, refusal naming the closest tabled spelling (difflib ≥0.75 — `telemetry.validation.failed` ≠ `telemetry.samples.validation_failed` refuses NAMING both); tabled names must exist in the strategy floor (the step-log off-plan doctrine); once the whole domain carries the fields, every floor meter must have an owner (completeness — the half rule (u)'s fuzzy `_meter_pairs` token-prefix heuristic could never see verbatim) |
| gate z2 | every (method, path) `serves`d by exactly one unit; every `uses` (guard, caller, slice) matched verbatim — "the chain protects a route nobody answers" is now an emit refusal, not a 500 |
| gate z3 | **prose→table**: a route-shaped literal or a floor meter name spelled in a STAGED unit's intent or tabled `semantics` while its own table omits it is refused, naming the unit and the literal. This is what arms the law on a fresh plan: prose may not stay the only home of a shared literal (the R1/R2 mechanism itself) |
| gate z4 | one unit, one table: T1/T2 twins staged together must carry IDENTICAL `ast_hints` (the prompt law, now machine-enforced); against a twin already on the board, every key present in both must match — a regen may ADD the vocabulary keys, never re-spell shared ones (`--replan <slug>` named as the remedy, same channel as the security claim-gap story) |
| false-positive discipline | the route scan requires a leading slash + ≥2 alphabetic-led segments and skips file-extension tails (rule (a)'s territory); media types (`application/json`), env placeholders, relative paths, `classpath:` locations cannot match; SF10 pins it — "over-refusing a lawful plan is the same defect wearing the other uniform" |
| tester tier | `java-junit5`: the meter law now points at `ast_hints.meters` (it used to say "from ast_hints" while ast_hints carried no names — a null-pointer law), a new route law points at `ast_hints.routes`, plus the **anti-convergence law**: a REGENERATED test takes its oracle from the task record as queued, never from the delivered implementation beside it (R1's second half, the D15 regen) |
| carriers | `prompts.py` (ast_hints field rules + (z) + observability bullet now true), both architect profiles (byte-identical bodies, (z) marker line added in order, widest line 594 < 600), `task-decomposition-dag` (payload contract, meters bullet, rule (l) pointer "(z)", (z) paragraph, the Plan-validity tail sentence rewritten: prose-only duties are now only the OTHER literals), tester skill. The coder/tester briefs already carry `ast_hints` verbatim (`PROMPT_KEYS`), and `_collaborator_tables` now shows a pinned producer's `meters:`/`routes:` beside its methods, so the tester never re-derives a spelling |

**The emission/tools discrepancy (same fix pass).** The skill said "write /tmp/tasks/…", the
OpenCode profile grants permissions (`edit: /tmp/**` — the key that governs file creation), the
Copilot profile lists `tools: ["read","search","execute","edit"]` — no write. Both profiles'
own sentences said "your write tool", an instruction to a tool the backend does not carry. Every
carrier now says **create with your edit tool**; SE4 scans all four carriers for the lie.

**Pins (repo rule: no merge without a case).** Engine: **SF1–SF12** — SF1 replays R1 exactly
(facade drifts its registration, consumer + floor keep the planned name: refused, BOTH
spellings named, off-plan owned name refused); SF2 accepts the same plan with one verbatim
spelling; SF3 double-owner; SF4 unowned floor meter once the domain carries the fields; SF5
replays R2 (test spells `/voc/packets`, its table does not carry it — refused); SF6/SF6b
guard-cites-served / cites-unserved; SF7 route served twice; SF8 divergent staged twins; SF9
staged task vs delivered twin (names `--replan`); SF10 false-positive guard; SF11 duty enum at
shape time; SF12 laundering-by-silence (empty the owner's field → `uses` with `OWNED by none`).
Skill/docs: **SE1–SE5** (both fields + rule (z) in every carrier; IDENTICAL-twin law in every
carrier; tester skill names the fields + the regen law; no "write tool" anywhere; every refusal
message carries literal + ids + the exact edit). Q14 extended (a)→(z), 26 markers.
Fixtures dogfooded, not weakened: the Z/X2b/X3b/Y1/Z2 blocks that spell routes in prose now
TABLE them (per-family hint dicts — the first attempt at sharing one serve-table across families
tripped SF7's own double-serve law, which is the gate working on its author).

**Verification.**
```
python3 gauntlet/run_gauntlet.py → SKILL-SCRIPTS 116/116, ENGINE-DECISIONS 277/277, GAUNTLET: ALL GREEN
resume sweep over the 119 live records (planning=False) → zero new refusals (the 10 reported
are the error/ ledger shape: the extra `error` key was never a queue record and is never
validated on resume - pre-existing, unchanged by this pass)
```

**What R1/R2 needed and this did NOT do (stated, not hidden).** R3 (slice-imports-chain), R4
(credential-shape / empty-custody bootability) and R5 (slice state isolation) remain open —
their refusals need spec/strategy-level fields (bootability of chain dependencies per test slice,
the custody SHAPE law, the isolation law), not the meter/route vocabulary join. The live board
stays frozen: these fixes protect the FRESH run (A6.2), which is now the experiment for
(z) as much as for the security laws. A residual by design: a plan that never spells a floor
meter in any tabled unit and never mentions it in prose still passes — (u) pairs it fuzzily and
the (z) completeness half arms only once the domain uses the fields; closing that means
demanding `meters` on every stage-2 unit, which the F3 readability doctrine argues against on a
board with zero meter obligations. README case counts still pending (A6.4, unchanged).

## B6. R3, R4, R5 and the anti-convergence close-out (same day, second pass)

The operator's breakdown was verified carrier-by-carrier before acting; four of its placements
needed correcting (recorded here because each is a defect class of its own):

| claim | correction applied |
|---|---|
| R3: "slices that @Import the chain must supply/mock every concrete chain parameter **(@MockBean)**" | **wrong tier + stale API.** `@MockBean` is deprecated Boot ≥3.4 (the live board itself carried both spellings in sibling tests); the planning tier may not name either annotation (Q26). More importantly the proposal left the law as prose while the (z) precedent shows it is JOINABLE: the guard unit's own table declares its products, so **z6** was built — a surface unit pinning a guard must also pin every PROJECT product the guard's table declares (dependencies ∪ method-parameter types); untabled product = emit refusal naming both units. The HOW (double the COLLABORATOR, never the chain/authorization/entry-points; pom decides the annotation) went to `tech-stack/spring-security`; the plan-assignment sentence to the table's Bootability section (with the deny-default caveat: an autoconfigured framework default principal is a fabricated user, never an option). |
| R4: "mandate the YAML structure matches the bound type in the SECURITY table" | **half right.** The custody SHAPE (a credential is the (id, secret-hash, scope) TRIPLE — one scalar env var cannot carry it; no empty legal state; posture declared per profile) is the `device-credential-proof` row's fact ✓ added there. The general law is stack-neutral plan validity → **rule (h) gained SHAPE MIRROR + BOOT-PATH PLACEHOLDERS** (a boot-path `${VAR}` must be defaultable `${VAR:}` or seeded in the document the test profile activates — the scaffold's plain `contextLoads` was the permanently-red victim), and the machine half is **z5: `ast_hints.config` [{path, kind: value\|list\|map, fields?}]** — the binding record owns the shape, every other unit cites path/kind/fields VERBATIM (relaxed-binding canonicalization: `secretHash` IS `secret-hash`, as the runtime reads them); refusals: two kinds for one path, conflicting field sets, any dotted child under a tabled list prefix, and (once the domain tables paths) a config-artifact unit carrying none. The tester-tier law ("a runner supplies every property the booting contract needs; a type rejecting empty collections has no 'bean exists' over an empty store") went to `java-junit5` beside the substitute-credentials law of the same family. |
| R5: carriers "tester skill AND java-springboot3 (or coder java-springboot)" | **the coder-tier pair was dropped as a carrier** (the coder implements the contract; if the plan never assigned isolation there is nothing lawful to write). Two placements: rule (p) now says **STATE IS A CONTRACT TOO** — the slice's support-unit contract NAMES the isolation choice (own-identity / relative delta / cleanup) and the slice intent says which; the tester skill forbids the global `COUNT(*)`/`MAX()` equality ("JUnit method order is not a contract"). No machine check was faked: detecting it means reading test source, which the engine's structured-fields doctrine forbids. |
| Anti-convergence: "add the rule to the tester skill + prompts" | **half was already shipped in B5** (the skill law + SE3). The real remaining gaps the proposal had not identified: `SCOPE_RULES` — *"read a source file only to copy an exact signature"* — was the LITERAL channel the D15 regen entered through; it now reads *"…NAMED BY THIS UNIT'S ast_hints TABLE - the delivered tree is never the source of a name you assert"*. Both tester profiles' Truth clause named only `methods/package/collaborators` — a field the profile omits is a field harvested from the tree — now names `meters/routes/config` + the guard-product duty. The tester MESSAGE (single and batch, via `_tester_tool_paths`) opens with the ORACLE line. The red-phase contract-digest idea (reuse the attempt ledger's `contract` hash) stays DEFERRED - law now, measurement at the fresh run. |

**Pins.** Engine: **SF13–SF18** — SF13 replays R4 (list record vs scalar-child seed: refused
naming both paths), SF14 accepts the citation pair across camel/kebab spellings (canonical form =
runtime's own), SF15 the config-unit obligation, SF16 replays R3 at EMIT (surface pins the guard
but not the guard's manager — the exact live shape of T2-033's table vs T2-025's), SF17 accepts
the T2-025 pattern generalized, SF18 proves framework-only parameters trigger nothing. Docs:
**SE6–SE9** (z6 in all three tiers, z5 + empty-store + placeholder laws in their owners, the
isolation pair, the three anti-convergence message surfaces). Q14/Q26/Q28/Q32 held unchanged —
the planning file still carries no execution DSL and the row identifiers Q28 pins still stand.

**Verification.**
```
python3 gauntlet/run_gauntlet.py → SKILL-SCRIPTS 120/120, ENGINE-DECISIONS 283/283, ALL GREEN
resume sweep: all queue+complete records validate (the 8 reported lines are the frozen board's
own error/-cascade dependsOn, pre-existing); config-shape probes refuse `kind: scalar` and
slash-paths at schema time.
```

**State for the fresh run.** All five rules ((z) family: z1–z6) now guard the vocabulary, the
custody shapes and the guard visibility the 2026-11-18 drain could only discover at the frozen-
test gate. The plan-phase laws from §9/SD4/SD5, the security closure from A1, and this pass
converge on the same experiment: a FRESH board is the first process where (z) bites at emit
instead of at autopsy. Residuals deliberately open: z5 arms by field-use (a domain that tables
no paths and mentions no meter in prose keeps (u)'s fuzzy pairing as its only net — closing it
means forcing the keys on every unit, against the F3 readability doctrine); the z6 join reads
project PRODUCTS, so a guard consuming an unexported inner type stays invisible (the weaver's
own product rules make that shape rare); the isolation and regen-convergence laws are carrier
laws by doctrine, not gates. The board stays frozen (complete 110, queue 1, error 10); the fresh
process owns the tuning from here.

## B7. Same day — two new planning agents: `agent-performance-architect`, `agent-ai-architect`

The operator's placement brief, executed with four corrections recorded at the time of analysis
(tier placement of the R3 law, the stale `@MockBean` mandate, the coder-tier carriers dropped
for R5, half the anti-convergence law already shipped). Both agents clone the security
step's contract — the one that keeps a specialist honest — not its content.

**Pipeline order now:** discovery → map → architect phase 1 → database → **security →
performance → AI(conditional)** → architect phase 2 → drain. Artifacts:
`blackboard/complete/performance-spec-<slug>.json`, `ai-spec-<slug>.json`.

| law cloned / new | where |
|---|---|
| **Performance is the unconditional floor** (like security, like the observability floor): workload entry per `surfaces[].name` VERBATIM, `surfaces_exempt` with a REASON, budgets with a `measurement.kind` from a CLOSED DETERMINISTIC enum (query-count / config-key / status-code / payload-size / queue-depth / deterministic-count — **no clock kind exists on purpose**, the R5 lesson enforced at the spec), worst-case invariants, duty closure, risk register, `open_questions` stops the run | `ddd.validate_performance_spec`, `performance-strategy` skill + schema, profile ×2, `PERFORMANCE_PROMPT`, pipeline loop + risks printed |
| **AI runs ONLY on a description-verified directive** — the security waiver's mirror, polarity flipped: slice `ai_directive{required:true, quote≥20, source:"description"}`, quote re-read VERBATIM from `metadata.source_description` by the engine; writer refuses `required:false` ("not-wanted IS the absent default"); discovery transcribes, never infers (all four discovery carriers updated); absent+unverifiable = fatal, absent+none = the correct silence | `writer_file.py`, `ddd.ai_required/validate_ai_directives`, `AI_PROMPT` (carries the verified quote as mandate AND boundary), terminal verdict prints `AI BY DIRECTIVE` |
| **Closed AI token vocabulary** (the user's list): prompt-contract, structured-output-guard, context-budget-cap, fallback-model-route, retrieval-scope-guard, tool-call-guard, eval-golden-set, memory-boundary, offline-model-port, token-cost-cap — an unmappable token has no realization channel, so the gate refuses it; **the offline-port invariant is mandatory** (no gate may reach a live endpoint: "a plan that CAN call the world from CI will, billing real tokens") | `ddd.validate_ai_spec`, `ai-strategy` skill + schema |
| **Claim law (y1-form) extended**: every performance/AI duty must be claimed by a stage-2 unit spelling spec_ref + capability VERBATIM (WB-/PB-/PI-, AR-/AC-/AM-); emit refuses, the resume branch fatals (`planning_claim_gaps`), `--replan` is the one remedy. (y2)/(y3) reach geometry stays security's — a load policy or model port may sit anywhere defensible, "but never nowhere" | `task_queue._planning_claim_lines`, pipeline, prompts |
| **Leak gate reused, vocabulary extended** (hikaricp, resilience4j, langchain, openai, ollama…), agent-name regex grows `performance|ai`; both new specs scan the same `_security_leaks` | `ddd.py` |
| **Phase-2 mapping tables, compact and conditional**: `tech-stack-architect/spring-performance-architect` (490 body words) + `spring-ai-architect` (499) — real identifiers only (`retryWhen(Retry.backoff(...))`, `spring.r2dbc.pool.max-size`, `BeanOutputConverter`, `ChatPort`, `spring-ai-bom`), honest **no framework mechanism** cells where the stack supplies nothing; the architect profile loads EACH only when its spec exists; architect budget 13→**15** sized for three tables, stated == engine (S26 re-pinned) | profiles, skills, settings |
| **A4 fixed for the database profile** (the operator's explicit item): exact skill paths per F4's shape — and the PF5 pin caught MY bug writing two of those paths (the two DB skills live under `tech-stack/`, not `architect-practices/`); stated budget == engine, 10→12 | DB profiles ×2 |

**Files:** new — 4 agent profiles (mirror-identical bodies), 2 authoring skills + 2 machine
schemas, 2 spring mapping tables; modified — `settings.py`, `ddd.py`, `task_queue.py`,
`prompts.py`, `pipeline.py`, both backends, both architect profiles, both DB profiles, both
discovery profiles + discovery skill, `writer_file.py`.

**Pins:** engine **PG1–PG13** (spec gates both ways, wall-clock refusal, verbatim keying,
vendor leak, closed AI vocabulary, offline-invariant mandate, directive verbatim/paraphrase,
claim refuse/accept, `--replan` archives the new specs, pipeline phase ORDER asserted from
source); skill-scripts **SC5–SC6, PF1–PF6** (unique skill ids — Q27's collision class prevented
at birth; edit-grant = own spec file only; schema placeholders teach the Q2b lesson; table caps;
the A4 paths; the measurement laws' prose spine). Gauntlet: **SKILL-SCRIPTS 131/131,
ENGINE-DECISIONS 299/299, ALL GREEN.**

**What the fresh process now tests in one run:** the plan-phase laws (SD4/SD5), the security
closure (A1), rule (z1–z6) at emit, and BOTH new phases end to end — three specs, three
mapping tables, one decomposition that must claim every duty to pass. Python/TypeScript still
have no architect-tier tables for security, performance or AI (the Java stack is the reference
implementation of the pattern; the others name from memory until a run demands the table).

## B8. Operator review pass - the two watchouts, closed before the live run

**1. The performance phase could not have survived seed-002.** The first draft carried, in the
skill and the profile alike, *"where the inputs state nothing, say 'undeclared' and, if it
blocks a budget, file an open_questions entry"* and *"Undecided input (missing **volume**,
missing surface) goes to open_questions - which STOPS the run"* - and the profile even said
*"name the missing input precisely (which surface, **which volume**, which file)"*. Functional
seeds describe behavior, not RPS: every live run would have halted at the performance phase's
open-question check. The law now reads, identically in all four carriers (skill,
PERFORMANCE_PROMPT, both profiles - PF7 pins the phrase wrap-proof):

> **A MISSING NUMBER IS A BASELINE ASSUMPTION, NEVER AN OPEN QUESTION.** Record one assumption
> (PA-01: "single-node baseline ceiling assumed wherever the description omits rates and
> volumes"), bound the budgets conservatively from it, cite it in the driver ("per PA-01").
> `open_questions` stays reserved for what only phase 1 can answer: a missing surface, flow or
> persisted concept, or conflicting requirements.

The schema's driver placeholder changed from `'undeclared' beats invention` to citing the
assumption - the machine reference cannot teach the halt the skill just outlawed (the D2/Q2b
lesson: a schema placeholder that points into its own gate). Residual, stated: the reservation
is carried by prose + pins, not by a gate - an open question naming RPS still stops the run by
design (the halt channel is honest, its trigger is now bounded); teaching the gate to classify
question TEXT would be the keyword-detection class §8.3 deliberately refused.

**2. The phase-2 tier split: verified, with two real gaps found and fixed.** The wiring existed
from B7 (the brief reads `performance-spec-<slug>.json` when present; the claim law demands
spec_ref + capability VERBATIM beside the mechanism copied from the table;
`spring-performance-architect` exists; `_planning_claim_lines` refuses unclaimed duties). The
review's own checklist surfaced:

- **a hunt-shaped path bug I had written into the phase-2 brief:** it said
  `tech-stack-architect/<stack>-performance` / `<stack>-ai` while the real directories are
  `<stack>-performance-architect` / `<stack>-ai-architect` - a wrong pattern in a prompt is
  exactly the folder-hunt F4 killed for skills. Corrected, and PF7b pins the pattern plus the
  "beside the copied mechanism" requirement.
- **Q28b applied at birth to both new tables:** the AI table's `eval-golden-set` cell named its
  mechanism in prose only - the precise invitation to recall an identifier. It now says **no
  framework mechanism** and names the plan's own golden-set resource + assertion class.
  **PF4c** pins the law per row: every mechanism cell carries a backticked identifier or the
  honest none, so a Resilience4j/Hikari the draft "remembers" is refused by the suite before it
  can be copied into an intent.
- the pool row got the blocking-stack pair (`spring.datasource.hikari.maximum-pool-size` +
  `server.tomcat.threads.max`) beside the reactive one - the table is the only lawful place
  those names appear; the spec gate's leak list already refuses them upstream. Body caps held
  (490/499 words).

Gauntlet after the pass: **SKILL-SCRIPTS 135/135, ENGINE-DECISIONS 299/299, ALL GREEN.** The
fresh process can start.

## B9. Review round 2 - the two new tables get Q24's and Q28d's treatment, and it pays at once

Operator instruction: verify the performance table's cited Boot keys against the installed
Boot-3.5 configuration metadata (clone of Q24), and verify `unit_kind` coverage of
`ddd.PERFORMANCE_UNIT_KINDS` (clone of Q28d). Both pinned; the verification caught a real
defect in the OTHER table:

1. **PF8 (Q24 clone, performance table).** Scanner over the 43 local `org.springframework.boot`
   3.x jars' `spring-configuration-metadata.json`: all nine cited keys are **exact** metadata
   entries — `spring.codec.max-in-memory-size`, `spring.lifecycle.timeout-per-shutdown-phase`,
   `spring.cache.type`, `spring.cache.cache-names`, the pool five. The first version cited
   `.max-idle-time` / `.max-acquire-time` as SHORTHAND after the full `spring.r2dbc.pool.max-size` -
   and a shorthand the scanner cannot extract is a key nobody verifies; the row now spells all
   three in FULL, and PF8 requires ≥8 extracted keys before its `all()` means anything (no jar
   on disk skips the case, never passes it blindly - Q24's own doctrine).
2. **PF8b (Q23/Q24 clone, AI table) - the catch.** The local `org.springframework.ai` artifacts
   are the 1.1.8 **model + MCP** jars only; no provider autoconfigure is installed. The
   context-budget row cited `spring.ai.openai.chat.options.max-tokens` — a key **recalled from
   memory**, unprovable on this machine: exactly the crime the table exists to prevent,
   committed inside the table. Replaced with the class-grounded form (ceiling on the call's
   `ChatOptions`, provider keys as the namespace `spring.ai.<provider>.chat.options.*` -
   placeholder characters are the scanner's honest skip). PF8b also grounds seven framework
   identifiers (`BeanOutputConverter<T>`, `ChatOptions`, `EmbeddingModel`, `ChatMemory`,
   `MessageWindowChatMemory`, `InMemoryChatMemoryRepository`, `@Tool`) as present in the local
   spring-ai jars, and keeps `ChatClient` in a NAMED ungrounded list (its artifact is not on
   disk) so silence cannot make an unchecked class checked - a future run that installs
   `spring-ai-client-chat` moves it into the grounded set deliberately. Any non-placeholder
   `spring.ai.*` key the local metadata cannot prove fails the case.
3. **PF9 (Q28d clone).** Every value of `ddd.PERFORMANCE_UNIT_KINDS` (10) and `ddd.AI_UNIT_KINDS`
   (10) appears as a unit-kind cell in its table - a duty arriving with a kind no row owns is
   claimed by a filler that recites the token and bounds nothing (Q28c's class, closed before
   the first live performance duty is ever emitted).

The review's other two observations were confirmed as already satisfied and re-pinned: the
tier split holds (identifiers + property keys, no bodies, no test DSL - PF4's caps still pass
at 491/497 body words), and the honest `no framework mechanism` cells (admission, rate-limit,
eval-harness) are exactly what keeps the table from inventing a Boot autoconfiguration or
smuggling a library past the stage-0 manifest-duty channel; PF4c refuses a mechanism cell
without a backticked identifier or the honest none.

Gauntlet after the pass: **SKILL-SCRIPTS 138/138, ENGINE-DECISIONS 299/299, ALL GREEN.**

## B10. Review round 3 - the field-only mechanism cell and the missing execution-tier legs

Two observations, both correct, both converted into law + pins:

1. **`counted proof` passed Q28b only by a loophole in MY check.** The cell cited
   `` `ast_hints` `` and `` `query-count` `` - backticks, yes, but a BOARD FIELD and a KIND
   NAME are not Java identifiers; the plan-owned decorator class deserved the honest prefix.
   Fixed on both sides: the cell now reads **`no framework mechanism: the plan's OWN counting
   decorator wrapping the port...`**, AND PF4c was tightened so a mechanism cell passes only
   with the prefix or a backticked token that is class-shaped (capital/@/$-led), call-shaped
   (contains `(`), or a dotted property key. **PF4c-selftest** feeds the ORIGINAL defective
   cell through the predicate and requires it to be reported - a check that cannot fail
   cannot pass (Q29's law). The tightening re-verified every other cell of both tables
   (retry `retryWhen(Retry.backoff(N, Duration))` call-shape ✓, `LIMIT :limit` capital-led ✓,
   pool keys dotted ✓) - all pass on their real identifiers.
2. **The tier split had no second leg for the new domains.** `spring-security-architect`
   pairs with `tech-stack/spring-security` (Q26/Q27); the two new architect tables said
   "bodies and test idiom live in the coder/tester tier" and that tier had NO FILE - the
   half-starved-pair class Q27 documented. Created and wired:
   - `tech-stack/spring-performance` - the counting decorator composed (same-interface
     wrapper + `AtomicLong`, one registration via the wiring unit, rule (n)); `Retry.backoff`
     with config-read bounds; `.flatMap(mapper, CONCURRENCY)` (no shared state where the
     operator suffices); the admission `WebFilter` (429 + `Retry-After`, release in the
     completion callback); `@Cacheable` + the `@EnableCaching` ACTIVATION law + the
     self-invocation trap; `.timeout(...)` + declared `onErrorResume`; and the tester half:
     **`StepVerifier.withVirtualTime` instead of any clock**, structural saturation
     (`permits + 1` concurrent requests → at least one refusal - bounded permits make the
     refusal a theorem, not a race), the decorator as the `query-count` oracle;
   - `tech-stack/spring-ai` - the import-boundary adapter, `.call().entity(T.class)` + the
     one-reask-then-refusal path, `MessageWindowChatMemory` by statefulness, `@Tool`
     delegation only, and the STUB-port registration for the test profile (live keys absent
     from the activated document; golden-set = property assertions via
     `@ParameterizedTest`, never wording equality; `stub-call-count`/`schema-validation`
     measurement bodies);
   - both named by EXACT PATH from `coder-framework/java-springboot` and
     `tester-framework/java-junit5` (§Performance/§AI units + tests, same "the task's table
     wins, disagreements reported" clause), the two architect tables name their destination,
     and both new names enter PF1's collision sweep (unique ids - `spring-ai` vs
     `spring-ai-architect` verified distinct, Q27's class watched at birth).
   Budget note (honest): the pair adds ONE conditional read to coder/tester sessions that
   carry performance/AI claims; single-session caps (6/8) absorbed the security pair's
   identical read on the live drain, and the batch shapes already scale per unit.

Gauntlet after the pass: **SKILL-SCRIPTS 140/140, ENGINE-DECISIONS 299/299, ALL GREEN.**

## B11. The AI agent grows its multi-agent legs (operator review round 4)

The review's three points, resolved as claimed - the first two were real blind spots, the
third was already built (B7/B10) and is now extended and re-verified:

**1. Multi-agent topology vocabulary — three tokens, three unit kinds, three machine laws.**
`AI_CAPABILITY_TOKENS` grows `agent-handoff` / `loop-budget-cap` / `human-approval-gate`;
`AI_UNIT_KINDS` grows `orchestration-router` / `loop-governor` / `approval-gate`. The engine
now enforces what the vocabulary implies (all refused at the spec gate, pinned PG14d/e/f):
- **TOPOLOGY TERMINATION**: an `agent-handoff` capability with no `loop-budget-cap` invariant
  is refused - each call valid and small while the LOOP spins forever is the AI class of the
  unbounded queue, and the proof channel already exists (`stub-call-count`);
- **approval-around-nothing**: a `human-approval-gate` with no `tool-call-guard` is refused -
  the gate must guard the high-impact tool that splits into propose/execute;
- **closed topology**: capabilities/invariants gained the optional `roles` list (AR- ids
  only); a binding to an undeclared agent is refused - every agent in the graph must be an
  agent in the plan. Plus one prose law where machines cannot reach: **the resume channel is
  a NEW inbound surface** - it must already be in the strategy's `surfaces` table (the
  widened-actuator trap, same shape), else it is an `open_questions` entry, never a silent
  hole in the permission table.
Bodies composed in `tech-stack/spring-ai` (Router-with-edge-table, `LoopGovernor` with
`.take(maxTurns)`/`takeUntil` shapes, propose/approve/deny persisted state - never a blocked
thread), planning rows in `spring-ai-architect` (the router and the gate are honest **no
framework mechanism** cells: delegation graphs and approval workflows do not ship in Spring
AI core); deterministic tester patterns (handoff-refusal, turns<=max + cycle-break outcome,
approve-executes-ONCE via the stub counter, foreign resume-id refused) ride the same trio.

**2. The `spec_ref` schema bug — real, and it was my own.** With duties allowed to cite
`AR-`/`AA-` rows, "the SAME closed token as the rule it discharges" was undefined (roles and
assumptions carry no capability field). Resolution: **only AC-/AM- rows are dischargeable** -
a role is a SUBJECT realized through the capabilities that bind it via `roles`, an assumption
is the record of a decision; both are cited inside an obligation's sentence, never as its
target. Machine-enforced (PG14b/c), schema corrected, law stated in the skill ("rules are
discharged, context is cited"), the phase-2 prompt, both AI profiles - and the two architect
profiles' claim lists, which still advertised `AR-/AC-/AM-` as duty targets (fixed; pin
followed). Two dead regex constants I had left in `task_queue.py` (`PERFORMANCE_REF_RE`,
`AI_REF_RE`, no reader) removed by the artifact's own doctrine.

**3. Phase-2 mapping + coder/tester pair — verified present, extended.**
`tech-stack-architect/spring-ai-architect` and `tech-stack/spring-ai` existed from B7/B10;
this pass adds the trio rows, grounds `VectorStore`/`ToolCallback` against the local
spring-ai jars (PF8b's grounded list grows to nine; `ChatClient` remains the one NAMED
ungrounded identifier - its artifact is not installed here), and the table cap was
re-justified (body <560, documented in PF4: thirteen grounded rows now; the alternative to
the raised cap was deleting identifiers - the defect the file exists to prevent). Because
thirteen tokens now live in five carriers, **PF12 pins vocabulary PARITY**: engine tuple ==
skill table == schema enum == architect-table rows == (profile inline ⊆ engine), tokens AND
unit kinds - hand-maintained lists in five places are the R1 disease wearing a vocabulary
hat, and PF13 caps the two authoring skills' sizes.

Gauntlet after the pass: **SKILL-SCRIPTS 142/142, ENGINE-DECISIONS 305/305, ALL GREEN.**

## B12. Two synchronization details from the operator (the drift the parity pin was built to catch)

1. **The skill's prose unit-kind list lagged its schema.** `ai-strategy/SKILL.md` §Duties still
   listed the original ten kinds while `ai-spec.schema.json` and the engine had carried
   `orchestration-router`/`loop-governor`/`approval-gate` since B11 - an author reading the
   skill at write time would emit a duty whose kind the schema accepts and the table maps,
   but the SKILL forbids: prose that lags its schema is a law read wrong. List completed to
   thirteen; **PF12 extended to pin it**: the skill's parenthetical unit-kind set must EQUAL
   `ddd.AI_UNIT_KINDS` (a fifth carrier now in the parity lock).
2. **`roles` was asymmetric across the two rule-row kinds.** The engine's role-binding check
   has always walked `capabilities + invariants` (PG14's lawful AM-02 exercised it), and the
   skill says a termination law names the agents whose cycle it caps - but the schema spelled
   the optional `roles` field only on `capabilities`. Added to `invariants` (documented on the
   `loop-budget-cap` row: name exactly the AR- agents in the cycle), pinned by PF12
   (`"roles" in invariants[0]`), and the negative path made explicit with **PG14g**: an
   invariant binding `AR-77` - an agent the plan never declares - is refused ("the cycle it
   caps involves a ghost").

Both details are the same class one layer up from (z): the closed sets live in several
carriers, and any carrier not pinned is a carrier that drifts. Gauntlet after the pass:
**SKILL-SCRIPTS 142/142, ENGINE-DECISIONS 306/306, ALL GREEN.**

## B13. Blocking SDK, reactive flow - the Spring AI dual-API trap, closed across every carrier

Operator review round 5, three items:

1. **The dual-API inconsistency was real and it was mine.** Spring AI's `ChatClient` terminal
   `.call()` is BLOCKING; `.stream()` returns `Flux<String>`. The tables mixed them silently:
   `.call().entity(T.class)` beside `Mono.timeout(...)`, `.take(maxTurns)` beside whatever the
   coder found first - and on the WebFlux default plan an unwrapped `.call()` is the
   `block()`-on-an-event-loop-thread defect in a model costume, exactly what §Reactive forbids
   elsewhere. Closed as a PLAN law, not a coder hint:
   - **`spring-ai-architect` Scope: "INVOCATION MODE IS A PLAN FACT"** - the unit's table names
     the shape (wrap `Schedulers.boundedElastic()` or stream), never the coder under a frozen
     test; the structured-output row marks `.call()` blocking-inline; the governor row says a
     reactive cycle bounds itself `Flux.take(n)`/`takeUntil(done)`, blocking hops per mode.
   - **`tech-stack/spring-ai` new section "Blocking SDK, reactive flow"**: the two lawful
     shapes (`Mono.fromCallable(...).subscribeOn(Schedulers.boundedElastic())` /
     `.stream().content()` composing `.timeout`/`.take`/`.onErrorResume` natively); NEVER
     `block()`/`blockFirst()`/`blockLast()`; `boundedElastic` treated as the bounded resource
     it is (its sizing is a performance-plan duty - the two new domains meeting at exactly the
     right seam); the timeout-composition consequence (an in-chain `.timeout()` cannot see a
     raw blocking call - that deadline is the provider client's request timeout, a config key);
     governor loops re-invoking the model run on the bounded scheduler, never a blocking
     `while`; timed paths keep `StepVerifier.withVirtualTime`.
   - **`java-springboot` §AI units** states the rule in the coder's own voice (the mode is
     contract, §Reactive applies to model hops).
2. **The two honest-none prefixes** (`context-budget-cap`, `loop-budget-cap`) applied as asked -
   both mechanisms ARE plan-owned classes (the assembler policy, the turn counter), with the
   one genuine framework element named inside the honest cell (`ChatOptions` ceiling, reactor
   bounding shapes). With them, every plan-owned row in both tables wears the prefix, and the
   strict PF4c rule (framework identifier or honest none) has no cell resting on a plan-class
   backtick alone. Body 558 (<560), file 609 (<640).
3. **The pins the review asked for, one of them already true:**
   - **PF8c**: `Mono`/`Flux`/`Schedulers`/`Retry` verified present in the local
     reactor-core-3.7.11 jar (no jar => skipped, never passed blindly - Q24's doctrine);
   - **PF8d**: the mode law is asserted in all four carriers by substring (architect table,
     exec AI file, coder framework, the two lawful shapes + the never-block list);
   - **Q30 extended**: the two new architect tables' PHASE-2 membership is now pinned per
     document - the path-resolution half was already green (all nine literals resolve; proved
     before claiming it), the membership clause makes it permanent.

Gauntlet after the pass: **SKILL-SCRIPTS 144/144, ENGINE-DECISIONS 306/306, ALL GREEN.**

## B14. Stub-bean precedence - the offline-port invariant's missing half (operator review round 6)

1. **Cross-skill pointers: verified already true, not re-asserted blindly.** Both framework
   skills carry the exact path (java-springboot §AI units line 28, java-junit5 §AI tests line
   31), and PF11 has been pinning both pointers - for the spring-performance AND spring-ai
   pair, in both files - since B10. Evidence shown before claimed; no change.
2. **The precedence bug was real - twice over.** My stub snippet
   (`@TestConfiguration { @Bean ChatPort stubChatPort() }`) had two failure modes the review's
   first covers and its second class implies:
   - **ambiguity**: the production adapter IS registered (the wiring unit, rule (n)) - a second
     `ChatPort` bean with no precedence decision is `NoUniqueBeanDefinitionException` at every
     `contextLoads`/slice boot. Fix, as law not hint: **the stub carries `@Primary`** - it wins
     explicitly in every test context and the production unit never has to know (making two
     frozen contracts coordinate is the failure class (z) exists to prevent);
     `@ConditionalOnMissingBean(ChatPort.class)` on the production bean is the alternative only
     when the plan tabled it there - one side carries the marker, decided AT PLAN TIME, named
     in both intents.
   - **silent non-registration** (the deeper twin, caught while fixing): a TOP-LEVEL
     `@TestConfiguration` is not picked up unless nested or `@Import`ed - a stub nobody imports
     boots the production adapter and reaches live, the offline-model-port violation disguised
     as green wiring. Closed with the **witness case**: a frozen test asserts the context's
     `ChatPort` bean IS the stub (`isInstanceOf`) - the substitute is proven bound, not assumed.
   Carried at all three tiers: exec (`tech-stack/spring-ai`, both traps + the shapes + the
   witness), plan identifier (architect row now reads "binds a `@Primary` STUB port" - the fact
   the intents copy), and stack-neutral (ai-strategy: "the stand-in must WIN WITNESSED -
   an override assumed is an override not delivered"). **PF8e** pins all three; ai-strategy
   body 1166 < PF13's 1200 cap; architect table 559 < 560.

Gauntlet after the pass: **SKILL-SCRIPTS 145/145, ENGINE-DECISIONS 306/306, ALL GREEN.**

## B15. The AI execution tier learns it has two runtimes (operator review round 7)

The `tech-stack/spring-ai` file (and one sentence of the architect table) had generalized the
WebFlux DEFAULT into the only execution model: every terminal was taught wrapped, every loop
bounded reactively, every test on `StepVerifier` - a servlet/MVC plan following it would add
scheduler hops to blocking threads and import reactor-test into gates that never compose a
`Mono`. Split cleanly, mirroring `tech-stack/spring-security` §Chain DSL (the Q29 pattern):

- **Shared core, runtime-neutral**: the one-import boundary, the prompt/options assembly,
  `BeanOutputConverter` validation and the re-ask-then-refusal path, embeddings, memory by
  statefulness, `@Tool` delegation, the topology classes (Router edge-table, Governor
  counter + cycle-break result, propose/approve/deny approval state) - and the offline stub
  section (registration, `@Primary` precedence, the pickup gotcha, the witness case), which
  is explicitly "both runtimes".
- **### Reactive (WebFlux)**: `.stream().content()` → `Flux<String>` with in-chain
  `.timeout`/`.take(maxTurns)`/`.onErrorResume`/`takeUntil(done)`; typed answers through
  `Mono.fromCallable(...call().entity(T.class)).subscribeOn(Schedulers.boundedElastic())`;
  the never-`block()`/`blockFirst()`/`blockLast()` law; the wrapped call's own deadline is
  the provider request-timeout key; `StepVerifier(.withVirtualTime)` tests.
- **### Blocking (Servlet / Spring MVC)**: `call().entity(T.class)` / `call().content()`
  direct on the request/worker thread, `spring.threads.virtual.enabled` when tabled;
  deadlines via the provider client's connect/read timeout keys; fallback as ordinary
  `try { call } catch (<declared failure>) { return <declared route>; }`; the governor as a
  plain `turns.incrementAndGet() > max` check; assertions synchronous
  (`assertThat`/`assertThrows`), no reactive verifier or reactor-test scaffolding - "a
  servlet gate importing the other block's test vocabulary tests the wrong runtime".
- **Plan tier**: the architect table's scope now reads "the unit's table names the RUNTIME
  (WebFlux default; an MVC plan takes the blocking pair)" - the runtime choice stays a plan
  fact, and the structured-output cell points `wrapped per §Reactive` instead of assuming it.
  Body 558 < 560.
- **Pins**: **PF8f** clones Q29's hermeticity law for this file - per `###` block, CODE SPANS
  only (prose may name a forbidden form to forbid it): blocking vocabulary in a reactive span,
  or reactive-only identifiers in a blocking span, is a failure; and **PF8f-selftest** feeds
  the predicate a reactive wrap pasted into the blocking block and requires it to be reported
  - the same meta-lesson that made Q29's first version blind. PF8d's needles followed the
  renamed sections.

Gauntlet after the pass: **SKILL-SCRIPTS 147/147, ENGINE-DECISIONS 306/306, ALL GREEN.**

## B16. The tester/coder load chain compressed - laws kept, narrative moved to this ledger

Operator ask: the skills the stage-1/2 agents read had grown huge. Compression rule applied:
**the skill is the instruction; the incident story is the ledger** - every law, code shape,
pinned identifier and refusal channel survived; the dates, unit numbers and mechanism
narratives came out of the skills (they live here, in B5-B15, permanently). Files, before ->
after:

| file (read by) | before | after | what went |
|---|---|---|---|
| `tester-framework/java-junit5` (every tester batch) | 1455 | 983 | incident clauses from the R1/R2/R4/R5 laws, the duplicated app-context rule folded into one place, prose tightened; ALL laws and every pinned needle kept (`ast_hints.meters/routes`, REGENERATED/TASK RECORD, PLAN HOLE/cross-cutting, method order/RELATIVE delta, `;USER=sa;PASSWORD=`, `Cannot decode value of type`, `flatExtracting`/`java.lang.Object`/`assert ONCE on the local`, the three tech-stack pointers) |
| `tech-stack/spring-ai` (AI-claim units) | 1311 | 997 | header prose, merged the duplicated PLAN-HOLE bullet, telegraphed the multi-agent/stub bullets; kept: runtime split + block purity, `Mono.fromCallable`/`subscribeOn`/`.stream().content()`/never-block, `@Primary`/`NoUniqueBeanDefinition`/pickup-gotcha/`isInstanceOf` witness, golden-set |
| `tech-stack/spring-performance` (PB-/PI- units) | 620 | 514 | example narration; kept every body law + the deterministic tester list |
| `coder-framework/java-springboot` | 619 | 619 | already telegraphic - left alone deliberately |
| `tech-stack/spring-security` | 1155 | 1155 | the Q29-tuned Chain DSL blocks and the twelve pinned idiom needles - a candidate for the same pass, deferred, not forgotten |

Chain total for the new domains' heaviest combination (tester of an AI unit): java-junit5 +
spring-ai + pointers = ~2.0K words where it was ~2.8K; the ALWAYS-loaded tester base alone
dropped a third. Load-on-demand keeps working as designed: the two tech-stack files ride only
sessions whose task actually carries a PB-/PI- or AC-/AM- claim.

Verification: the whole functional surface is what the suite measures - **SKILL-SCRIPTS
147/147, ENGINE-DECISIONS 306/306, ALL GREEN** after every cut; nothing was deleted that a
pin, a pointer or a law requires. If a future needle needs a phrase that was compressed out,
the suite says so at merge time - which is precisely the safety this kind of edit needs.

## B17. The writable channel - a prompt contract cannot live in a template file (operator review round 8)

The review traced a deadlock-to-be across the carrier chain: `spring-ai-architect` said
"versioned resource tabled in ast_hints", `tech-stack/spring-ai` said `contract.system()`,
and `agent-coder` writes ONE payload routed to ONE weaver. The mechanism audit:

- the dispatcher DOES have a text route (`yaml_weaver`, full-file write via
  `_text_write_exec`) - but it is the CONFIGURATION channel: its builder probe keys on
  `.yml/.yaml` under resources, and nothing teaches or validates it for `.st`/`.txt`/`.md`;
- a stage-2 unit planned at `src/main/resources/prompts/system.st` therefore has no lawful
  writer: the java weaver cannot splice a template, the text channel does not claim it, the
  stage-0 channel belongs to container/migrations, and the architect cannot write project
  files - the D4 class (a duty without a channel) discovered at the first red gate, per
  attempt, billed;
- and a template file would ALSO have failed the design's own security even if writable: no
  tabled members for the tester to assert, no `ast_hints` surface, no claim the (z) machinery
  could join - the contract would be folklore with a file extension.

Resolution - both of the review's options, the first one made machine-enforced:

1. **The prompt contract is a SOURCE TYPE.** `PromptContract` (record/class): the FIVE
   elements - version, role identity, input placeholders, output-schema reference, refusal
   text - are tabled members; `ChatClient.prompt()` assembles ONLY through them; the unit's
   intent states the elements inside the 40-80-word budget so the coder needs no other
   skill. Carried in: ai-strategy (row), AI_PROMPT, both AI profiles, the phase-2 tasks
   brief (HOME OF THE ARTIFACT), both architect profiles, `spring-ai-architect` (row, body
   559/560), `tech-stack/spring-ai` (generation body + "never a `resources/*.st` template -
   plan hole"). **SE10** pins the law across all of them.
2. **The WRITABLE CHANNEL, generically and at emit.** `_writable_channel_errors`: a stage-1/2
   unit's `path` must end in a language source suffix (reusing `test_gate.SOURCE_SUFFIXES` -
   one home, no second spelling) or a configuration document (.yml/.yaml/.properties);
   anything else is refused naming the path and the remedy (move the artifact into a type or
   the config document). This closes the whole class, not just `.st` - a future plan that
   invents `docs/*.md` or `fixtures/*.json` units meets the same wall at zero sessions.
   **SF19/SF20**: the template path refused; the same unit as `PromptContract.java` accepted.

Also fixed en route: a dead constant of my own (`TEMPLATE_SUFFIXES_NOTE` - the allowlist
made it dead the moment it was born; removed per the artifact's own doctrine), the PF8d
needle for wording I had trimmed, and the refusal upgraded to name the FULL path - SF19's
own assertion caught the diagnosis being weaker than its remedy.

Gauntlet after the pass: **SKILL-SCRIPTS 148/148, ENGINE-DECISIONS 308/308, ALL GREEN.**

## B18. The delivery-shape token - the AI spec learns to say *stream* without saying *SSE*

The review caught the last unowned decision on the AI path: nothing in the 13-token
vocabulary told phase 2 whether a flow holds a request-response connection or pushes
incremental events, so the SSE-vs-JSON wiring would be improvised by a coder under a frozen
test. Adopted as the **14th closed token, `incremental-progress-stream`** (unit kind
`stream-delivery`) - the token form over a `delivery_mode` field deliberately: the parity
lock, the closed-vocabulary gate and both mapping tables key on tokens; a mode field would be
a second, free vocabulary to police.

**The law, by tier:**
- **Spec (transport-FREE)**: the row states the SHAPE - "incremental chunk/progress events
  over a non-blocking push channel, ending in a terminal completion" - and the TRIGGERS: emit
  when the directed capability is multimodal analysis, a handoff loop, or user-facing
  generation whose time-to-first-token would stall a call; where completion is polled from
  the durable store, record the assumption instead - "silence about the shape is undecided
  delivery". A new gate refusal (PG16): naming SSE/websocket/gRPC/long-polling IN the spec
  is rejected as a TRANSPORT - an internal consumer may not be HTTP at all; the protocol is
  phase 2's mapping onto the concrete surface.
- **Measurement law honored**: proof is `stub-call-count`/`deterministic-count` - the stage-1
  test asserts N events THEN the terminal completion, never that the call blocked to
  completion first (PG15 walks the whole law: closed token, role-bound, duty on a rule row).
- **Phase 2 (transport HOME)**: the architect table gained the row - `Flux<ProgressEvent>`
  port shape, handler streams via `ServerSentEvent`/`text/event-stream` (blocking plan:
  `SseEmitter`), idle-timeout key owned by the config unit; bodies compose per block in
  `tech-stack/spring-ai` (reactive: map `.stream().content()` chunks + concat terminal, one
  progress event per governor turn; servlet: `SseEmitter` push or the polled assumption -
  whichever the plan tabled); the tasks brief and both architect profiles state: an
  incremental-progress-stream claim MAKES the inbound unit stream, never hold, and the
  stream's bounds are the performance spec's (an unbounded stream is a queue-depth budget -
  the two domains meeting again at the right seam).

**Carriers**: engine (token + kind + transport scan), schema enums, ai-strategy row (1191/1200
after retightening), AI_PROMPT, both AI profiles, spring-ai-architect (14 rows, body 612;
PF4 cap re-raised to 620/700 with the documented-growth justification), spring-ai exec tier,
tasks brief, both architect profiles. **PF12 parity auto-extended to 14** and paid for itself
twice inside this very pass: it refused a profile phrase ("the delivery-shape token") whose
hyphenated prose the extractor read as a ghost token - the law now lists the token bare -
and the new gate's own insertion order (a scan before its binding) died on first suite
contact, exactly the class the pins exist to catch at merge, not on a live drain.

Gauntlet after the pass: **SKILL-SCRIPTS 148/148, ENGINE-DECISIONS 310/310, ALL GREEN.**

## B19. Final sync checklist - all three rows verified landed, then sharpened to the letter

The checklist's three files already carried the 14th token from B18 (verified, not assumed:
schema enums show `incremental-progress-stream`/`stream-delivery`; the architect row exists;
the exec bullets exist). Verified state per row:

1. **`ai-spec.schema.json`** - capability enum + duties unit_kind enum both include the new
   names (PF12 parity: engine == schema == skill == table == profile, 14/14/14, kinds 14).
2. **`spring-ai-architect`** - the row now maps exactly as requested: `Flux<ProgressEvent>`
   port events, handler answers `Flux<ServerSentEvent<T>>` at
   `@GetMapping(produces = MediaType.TEXT_EVENT_STREAM_VALUE)`, MVC plan `SseEmitter`,
   idle-timeout key. Body 614/620.
3. **`tech-stack/spring-ai`** - composition snippets added per block: reactive builds events
   as `ServerSentEvent.builder(chunk).event("progress").build()` and the chunk-then-terminal
   test is literal - `StepVerifier.create(port.deliver(req)).thenConsumeWhile(e ->
   !e.terminal()).expectNextMatches(ProgressEvent::terminal).verifyComplete()`; the blocking
   block pushes `SseEmitter.event().name("progress").data(chunk)` per turn, terminal last,
   `complete()`/`completeWithError()`, or the spec's POLLED-COMPLETION posture - and a
   second send-after-complete throwing is asserted. (One self-caught defect: my B18 text had
   typo'd "polled-composure" - gone.)

**Pins**: PF8c extended to ground the four transport identifiers (`ServerSentEvent`,
`MediaType`, `GetMapping`, `SseEmitter`) against the local spring-web/webmvc jars - same
skip-never-pass-blindly doctrine; PF8d now asserts the delivery composition by name in both
tiers (table: `MediaType.TEXT_EVENT_STREAM_VALUE`; bodies: `ServerSentEvent.builder`,
`SseEmitter.event()`, `thenConsumeWhile`, `expectNextMatches`).

Gauntlet: **SKILL-SCRIPTS 148/148, ENGINE-DECISIONS 310/310, ALL GREEN.** The validator, the
Phase-2 mapping and the composition tier speak the same 14-token language, every grounding
claim proven against jars on disk, the fresh process ready.

## B20. Memory gets a decision rule and a technique - three of the four triggers are now gate laws

The review's gap was real in both halves: `none|session|durable` was picked with no criteria
(a workflow that must survive restart could lawfully pick `session`), and `durable` with no
technique left phase 2 choosing between a window, a compactor and a vector index - the last
of which drags `retrieval-scope-guard` and the compaction half of `context-budget-cap` with
it. Adopted as fields + gate laws, deliberately NOT a 15th capability token (the closed set
gates what duties claim and tables map; the technique refines one token's obligation - PF12
parity stays 14 by design).

**Schema/engine** (`model_roles[]`): `memory_technique: sliding-window|rolling-summary|semantic-episodic`,
enforced by `ddd.validate_ai_spec`:
- tier-without-technique refused (PG17): statefulness is half a decision;
- stateless-with-technique refused (PG17b): `none` has no memory to manage;
- **approval ⇒ durable** (PG18): a `human-approval-gate` bound to a non-durable role is
  refused - an `awaiting_approval` that resumes through an inbound surface cannot live in a
  process that may restart or rebalance;
- **semantic ⇒ scoped** (PG19a): a `semantic-episodic` role with no `retrieval-scope-guard`
  capability is refused - unscoped embedded recall is a tenant-to-tenant disclosure with
  good recall;
- **durable ⇒ persisted concept** (PG19b): a durable role whose `data_classes` match nothing
  in the strategy's `persistence.data_model` is refused with the `open_questions` route named
  - the shared-blackboard/audit trigger decided twice and stored nowhere;
- PG19c accepts the full lawful combination.
Trigger (1), cross-session continuity, stays the author's call - it is not decidable from
the artifact, which is precisely why the field it must write down is mandatory: the invisible
decision becomes a readable one. The skill states this split explicitly ("provable triggers
are gate laws; the rest is the author's, made visible by the fields they read").

**Carriers:** ai-strategy new section "# Memory: the tier and the technique" (triggers + the
three techniques, each paired with `context-budget-cap`: sliding-window drops,
rolling-summary *is* the compaction mechanism - bound it too, semantic-episodic retrieves
top-K behind the guard); AI_PROMPT + both AI profiles (mirrors identical) carry the decision
rule; `ai-spec.schema.json` documents the field and the mandatory-durable triggers; the
`spring-ai-architect` memory row now maps ALL THREE techniques - `MessageWindowChatMemory`
(sliding-window) plus two honest **no framework mechanism** cells (rolling-summary: the
plan's compaction step over `ChatMemory` + store; semantic-episodic: memory reads via
`VectorStore` behind the scope guard), with the summary-interval key.

**Caps after the round:** ai-strategy 1398/1400 (PF13 raised once, documented: 1200→1400 for
the delivery + memory laws, each word gate-enforced vocabulary); architect table body 615/620;
PF12 parity holds at 14/14/14 + kinds 14/14. The pin layer again audited the fixer: a
memory-law block inserted before its `roles` binding died as `UnboundLocalError` on first
suite contact (second ordering catch today, same class), a PF8d needle broke on a line wrap
and is now wrap-aware (Q13's FLAT idiom applied to itself), and one assertion disagreed with
its own refusal wording. Suite: **SKILL-SCRIPTS 149/149, ENGINE-DECISIONS 316/316, ALL GREEN.**

## B21. The three memory techniques get bodies at the composition tier

The architect table mapped `sliding-window`/`rolling-summary`/`semantic-episodic` (B20) but
`tech-stack/spring-ai` still showed only the window - a coder handed a `rolling-summary` spec
would have invented the compaction flow, i.e. the mapping tier promised what the composition
tier did not teach. Fixed in the memory bullet of `# Shared core - both runtimes`:

- `sliding-window`: the full builder chain, window from config, older turns dropped;
- `rolling-summary`: **no framework mechanism** (echoing the architect row's honest cell) -
  the plan's compaction step; the crucial import-law nuance stated out loud: the
  summarization is itself a model call, so the compactor runs **through `ChatPort`** - no
  `ChatClient` outside the adapter, not even inside the mechanism that shrinks the memory;
  summary persists to the durable store beside the retained window; test = compaction fires
  once per interval crossing (`stub-call-count`);
- `semantic-episodic`: embed via `EmbeddingPort` into `VectorStore` **with owner/tenant
  metadata**; top-k from config, but `permits(...)` re-checks before hydrating context -
  "the scope guard lives in the flow, not behind the store"; test = two seeded owners, query
  as one, foreign memories absent (`deterministic-count`).

Grounded names only (`MessageWindowChatMemory`, `InMemoryChatMemoryRepository`,
`VectorStore` - all jar-proven; `ChatPort`/`EmbeddingPort` plan-owned). PF8d extended with
five wrap-aware needles pinning the three bodies, so the two memory tiers cannot drift apart
again. File grew 1140->1280 words, all of it gate-enforced vocabulary at the tier that
composes it, and it still loads only for AC-/AM- units.

Gauntlet: **SKILL-SCRIPTS 149/149, ENGINE-DECISIONS 316/316, ALL GREEN.**
