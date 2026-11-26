---
name: task-decomposition-dag
description: Use when the architect agent splits a component into a dependency-ordered task queue (DAG) for the TDD + AST coder loop. Produces task JSON files for the Blackboard only.
---
# task-decomposition-dag - the planning contract

`QUICKREF.md` is the syntax map a planning session reads by default; THIS file is the
fallback lookup: one declarative invariant per rule, keyed by the letter an
`ERR [pointer]: rule (x)` citation names. History lives in `DECISIONS.md` and is
never a planning input.

# Scope
- Granularity: one component/contract = one task: one `path`, one exported type;
  split above 1 layer, 3 collaborators, or 1 method group; never tasks for
  packages/folders/modules; no invented requirements - trace to the spec.
- The observability floor is UNCONDITIONAL for every executable context: a strategy
  lacking any of correlation key, step logs, audit trail, metrics, export is refused
  before claims are read; every floor step log pairs with a meter or an explicit
  `uncounted_steps` reason; every failure/drop outcome in tabled `semantics` pairs
  with a counter or an `uncounted_failures` posture (u); the export surface declares
  how records leave the process - the app writes files, the platform ships them, and
  a named direct-push destination needs the offline-substitute treatment.
- Decomposition order: value objects -> domain aggregates -> outbound interfaces ->
  use cases -> inbound adapters -> configuration; `dependsOn` = direct only; cycles
  => reject.
- Every unit = stage-1 test + stage-2 code + stage-3 refactor; the planner emits all three
  KINDS, and in a board file the engine COMPLETES the triple: a missing stage-3 is
  issued, a stage-1 without a table gets the code side's table mirrored (R4 - the
  CODE side owns the interface; typing derived records is the expensive habit).
- The stage graph is law: stage 1 depends ONLY on stage 0 and earlier stage-1 tasks;
  stage 2 on its own stage-1 and the code tasks of pinned producers; stage 3 on its
  own stage-2.
- The ONE sanctioned unpaired task a planning draft may carry: the (p) slice's lone
  stage-1 - and the ONLY extra object a session types: no stage-0 record is ever a
  context extra (the build manifest is ENGINE-queued, PHASE 1.5; the scaffold is
  phase 1's own task).
- PHASE 1.5 singletons: the ONE stage-0 build-manifest is ENGINE-queued from the stack table's Build coordinates rows against the PLANNED capability set (`plan_build_manifest`) - no session schedules or patches it; the ONE config unit and the ONE root gate belong to the ROOT pass (`ROOT_CONTEXT`), drafted before the bounded contexts, whose ids every context PINs from the symbol table; the `missing_coordinates`/`config_paths` gap channels are DELETED.
- Draft shapes, ONE per file: the COMPACT UNIT FORM or the BOARD TASK OBJECTS; both
  expand through ONE validator, which derives ids from `n`, materializes the triad,
  mirrors the code-side table byte-identically onto T1 and T2 (z4 by construction),
  and renumbers id collisions at claim.

# Hydration - references in, canonical entries out
The session REFERENCES shared facts it consumes; `hydrate_batch` tables the canonical
entry VERBATIM from the owner at claim (world = this file + drafted contexts + board;
unresolvable references are refused at lint naming the closest tabled spelling):

| reference key (code side)   | canonical field written                          | resolution ladder                    |
|-----------------------------|--------------------------------------------------|--------------------------------------|
| `uses_meters: [name]`       | `ast_hints.meters` {name, duty: uses}            | owner's `owns` entry, then metric floor |
| `uses_routes: ["M /path"]`  | `ast_hints.routes` {method, path, duty: uses}    | serving unit's `serves`, then strategy surface table |
| `uses_config: [path]`       | `ast_hints.config` {path, kind, fields?}         | the binding unit's entry (one shape) |
| `claims_steps: [string]`    | `observability.step_logs` (VERBATIM floor string) | strategy floor; refused on double claim |
| `root_gate: true` (marker stays; typed by the ROOT pass only) | root's addressed surfaces -> the gate's `routes` | every strategy surface with method+path |

What stays the session's typing: `owns`/`serves` entries, `dependencies` pins,
methods with `semantics`, claim texts, intents. The batch joins below remain the
last-line defense.

# Payload contract
- `ast_hints` = THE interface table: `package`, `implements`, `dependencies`,
  `methods`, `meters`, `routes`, `config` are BOARD FIELD NAMES - structural slots;
  their language reality comes from the active tech-stack skill's `# Record keys`
  mapping (some may be declared not applicable).
- A member is INSTANCE unless its signature begins with `static`; `semantics` is
  REQUIRED when the intent rejects null or bounds an argument; consumers' testers
  write against the TABLE, never prose.
- `intent`: target 40-80 words, hard ceiling 180 (refused at emit); it carries the
  claim, the literals, both signal branches; a tabled fact is never re-spelled; a
  collaborator's method is NAMED, never its parameter list.

# Plan validity - one invariant per letter (refused at emit)
- (a) Duty ownership: every file artifact an intent names is that unit's own `path` or another task's `path`; "also provide <other file>" inside an intent is prose, not a plan.
- (b) Config unit: any externalized value => ONE configuration-artifact unit per domain, scheduled by the ROOT pass (PHASE 1.5) carrying the spec-named keys and the strategy-tabled defaults; bounded contexts table {path, kind, value?} on their BINDING unit only and `wire_config_coverage` copies every tabled path VERBATIM into the config unit at the batch - no gaps file, no per-context seeding duty, no second config unit; two binders with different values for one path stay a refusal.
- (c) Request-encoding alignment: a pinned request-parameter type and the body shape the paired test mandates agree (streamed vs array bodies are an impossible pair).
- (d) Nullability and bounds: a null-rejecting or range-claiming intent requires the producing table to carry the encoding/bound in `semantics`.
- (e) Prose never fights the table: an unconstructible-shape claim cannot coexist with instance-bound members; a static-form call must match the producer's binding.
- (f) Provider closure: every injected type has a named provider duty in the DAG (producer self-registration XOR wiring factory - never both, rule (n)).
- (g) Composition-root visibility: the entry package is an ancestor-or-self of every component package and of every context-booting test package; scan directives do not waive the search half.
- (h) Config-surface completeness: the config intent enumerates EVERY document its test activates with keys and literals; SHAPE MIRROR - the config unit cites each binder's path/kind/fields VERBATIM; BOOT-PATH PLACEHOLDERS - every `${VAR}` a constructor reads is defaultable or seeded in the activated document.
- (i) Stream egress: every published stream port names a consumer unit or an explicit out-of-process boundary in the strategy; the return TYPE is read wherever it sits - an envelope hides nothing.
- (j) Step-log claim coverage: every strategy floor string (flat list or per-context mapping) is claimed VERBATIM by exactly one stage-2 unit's `observability.step_logs`; unowned, double or off-floor claims are refused naming the string.
- (k) Consumer closure: every rule-implementing unit is reachable through the pin graph from an entry unit; an unpinned published return type is a dead source - a factory's own pin never counts; the lawful exemptions are the consumer pin, the wiring routing duty, the publisher's OWN intent spelling out-of-process/external-subscribers words, or a boundary sentence naming the source in an EXISTING strategy text field (never a new key).
- (l) Shared literals: one owner per literal; consumers reference or pin the owner; two spellings of one named fact are a refused impossible pair; one config key feeding differently-shaped readers must split into DISTINCT keys.
- (m) Signal branches: a decision/signal return demands on_true AND on_false behavior in EVERY consuming contract and a test case per branch.
- (n) One registration mechanism per product (factory duty XOR self-registration); declared validation is activated by the ENTRY unit's contract with the stack's mechanism.
- (o) Real substrate: a unit executing statements against a schema pairs with a test running the ACTUAL migrated schema against the embedded substitute; a mocked-client case may be extra, never the only substrate test.
- (p) Request-path slice: a project with inbound address-bearing adapters schedules the end-to-end slice; its stage-1 intent literally spells the marker the gate greps (`end-to-end`, `integration slice`, `request-path`) and asserts ONLY the chained units' TABLED outcomes, citing them; STATE IS A CONTRACT TOO - the support contract names its isolation choice (unique identity, relative delta, or cleanup); a bare global count on a shared store freezes test order into the contract.
- (q) Idempotency: retryable inbound over an append-only chain names a dedup identity in the receiving contracts, or the strategy declares at-most-once beside the inbound words.
- (r) Migrations travel packaged: a config unit enabling a runner names the PACKAGED location form, never a CWD-relative path; portability is never re-demanded at a delivered gate.
- (s) Identity axis: a dedup identity over a correcting chain states whether the payload is part of the identity or excluded by a named discriminator; both resend classes become test duties; an upstream open question arrives RESOLVED in the strategy, never silently answered downstream.
- (t) Promised mechanisms are scheduled duties: the strategy's "via <mechanism>" token appears as some unit's install duty - or the strategy is amended to what ships BEFORE emitting; the gate refuses the mismatch, not the choice.
- (u) No acknowledged outcome is unmetered: step logs pair with metrics (or `uncounted_steps` reasons); failure vocabularies pair with counters (or `uncounted_failures` postures).
- (v) Config artifacts carry their KIND's format: table the semantic path; the serialized file uses its own kind's native form; the delivered half is the assembly gate's re-serialization (shape only, values untouched).
- (w) Test-file path: a stage-1 `path` is the TEST artifact the tester creates - never equal to its paired stage-2 path; stage 3 may share stage 2's file.
- (x) Handler registration executability: an inbound handler names ONE mechanism its stack can execute (its own-class marker OR a functional router bean) - forbidding the marker while crediting the factory alone is the impossible pair.
- (y) Security duty lifecycle: each spec duty is discharged INSIDE the enforcing STAGE-2 unit spelling `spec_ref` AND `capability` VERBATIM beside the mechanism copied from its `table_row`; the surface unit pins the enforcing unit and its stage-1 pair carries the row id + the CROSS-OWNER case. (y1-row) COVERAGE IS NOT SCHEDULING: every `covers` row also needs its id + the covering duty's capability spelled at the unit that IS that row's surface entry, its pair tester asserting the row's test_duty (the digest inherits the case from the covered row when the duty's own row states none) - an unspoken row is refused at emit exactly like a missing duty.
  (y4) ROOT-WIDE ADMISSION - ONE GATE PER ROOT: the root has ONE entry-admission decision, scheduled by the ROOT pass and marked `root_gate: true`; the engine tables every addressed surface into its routes (own guarded, foreign admitted unguarded), and `wire_root_gate` closes the gate's chain composition from the batch's claims; every context pass PINs it and cites no foreign address - a second root-wide admission is refused naming the first. The gate's `dependencies` pin ONLY the collaborators its chain composes (principal adapter, entry/denied handlers, authentication managers); a protected surface reaches the gate through the engine-hydrated routes table - pinning every unit behind every protected address turns the ONE gate into a fan-in the drain must wait for.
  (y5) SURFACE ENTRY IS PER-KIND: the declared `kind` picks the entry unit - addressed: the unit whose `routes` answers it (cross-owner = a valid identifier owned by another); internal/address-less consumer: the adapter events ARRIVE at (cross-owner = a forged producer's valid event, refused and audited); job/cli: the runner.
- (z) Shared-literal joins: one `owns` per meter name, one `serves` per (method, path), every `uses` matching its owner VERBATIM (near-miss spellings named); floor meters all owned; route-shaped and floor-meter literals in a unit's text required in its own table; T1/T2 pairs IDENTICAL.
  (z4) pair identity: one unit, one table, byte-identical on both sides.
  (z5) property paths: one path, one kind, one field set, no dotted child under a tabled list, and the config-artifact unit's table COVERS every path a stage-2 unit binds.
  (z6) guard visibility: a surface serving a route a guard cites carries every project product the guard's table declares - closed by the engine at the batch, asserted by the join behind the wire.
  (z7) budget assertion closure: every performance budget the spec tables is asserted by some stage-1 test - an enforced limit proved nowhere is a limit that regresses silently.

# Rule values
The strategy `rules` array is the plan's ONLY copy of the description's bounds,
windows and status tokens; every tabled value lands in an enforcing intent or a
config default with ONE owner; a value no unit carries is a reported gap for phase 1
- never an invented replacement, never a closed one-sided bound.

# Emission (a token budget, not a style rule)
ONE JSON array **per bounded context** (`/tmp/tasks/<slug>-<context>.json`); the
ENGINE runs the single batch `--emit` after the last context, validating the whole
plan - cross-context pins, provider closure, reach laws, every join - at zero
sessions. On refusal: **edit** the named objects and re-emit once; never rewrite the
plan for a pointer fix, never write `blackboard/queue` directly, never reuse ids.
