# task-decomposition-dag - QUICK REFERENCE (planning sessions)

The full contract (rules (a)-(z), history) is `SKILL.md`; this map is the default read.
Open SKILL.md ONLY on an unsummarized `ERR` pointer or a first new-stack plan.

## Draft record - what you write

TWO honest shapes, both expanded by the engine, never mixed mid-file: BOARD TASK
OBJECTS - the T1+T2+T3 per unit in id order, keys exactly `id`
(T<stage>-<3 digits>), `targetAgent`, `stage`, `dependsOn`, `path`, `kind`, `layer`,
`feature`, `export`, `project`, `intent`, `ast_hints` (required 1-2) - or the COMPACT
TRIAD `{"n": 7, "test": {...}, "code": {...}}` (ids derive from n). Never a script or a
file per task. T1 and T2 carry IDENTICAL `ast_hints` tables (z4); the lone exception:
the ONE canonical stage-0 build-manifest record.

## Stage / agent / kind / path

- stage 1 -> `agent-tester`, kind `test`, path = the test file (never production, never
  the paired stage-2 path - rule w); stage 2 -> `agent-coder`, kind `code`, path = the
  production file; stage 3 -> `agent-evaluator`, kind `refactor`, shares stage 2's file.
- The (p) request-path slice may stand as a lone stage-1 (green at the terminal suite),
  asserting only outcomes the plan tables; no second contract.
- The stage graph: T1 dependsOn stage-0 scaffold + earlier T1 tasks - NEVER a stage-2
  task; T2 on its own T1 + the T2 tasks of pinned producers; T3 on its T2.

## `ast_hints` - the single interface truth (assert and build from THIS, ONLY)

Keys are BOARD SLOTS - the active tech-stack skill's Record-keys section spells each
one, and may declare some not applicable. `package`, `implements`, `dependencies`
[{type, task_id}] - one pin per collaborator, to the task producing it; a consumed
type's table spells every member consumers touch. `methods`
[{signature, returns, semantics?}] - types as the language declares; `returns` ""
when none; `semantics` REQUIRED when the intent rejects null or bounds an argument
(rule d).
`meters` [{name, duty: owns|uses}] - meter names live ONLY here (rule z): `owns` on the
ONE registrant, `uses` on every recorder.
`routes` [{method, path, duty: serves|uses}] - inbound addresses live ONLY here:
`serves` on the ONE unit answering each.
`config` [{path, kind: value|list|map, fields?}] - property paths live ONLY here (rule
z5): the unit whose record BINDS a path owns its shape; others cite it VERBATIM.

## Claim form (machine-checked at emit)

Digest duties arrive COMPLETE - every key, matched `table_row` in hand. Discharge each
INSIDE the enforcing STAGE-2 unit: spell `spec_ref` AND `capability` VERBATIM beside the
copied mechanism - a bare id cites, it does not map. Security adds the geometry: the
unit that IS the surface (intent names `surfaces[].name` verbatim) pins the enforcing
unit and its T1 carries the row id + the CROSS-OWNER case (y1/y2/y3). Performance/AI
ride (y1) only; assumptions and role entries never claim. Board keys take their language
meaning from the active tech-stack skill.
(y4) ONE ROOT GATE: ONE entry-admission decision for the root (the stack's own inbound
gate), owned by the context that drafts it FIRST - it admits-and-guards its own tabled
addresses and ADMITS foreign ones in `composition_root_surfaces` unguarded;
default-closure ends the rest. A later context PINs that gate, adds at most rules for its own surfaces, and tables no foreign
address.
(y5) SURFACE ENTRY IS PER-KIND: `kind` picks the entry - `http` or routed
`consumer`: the unit whose `routes` answers the tabled `method`+`path` (cross-owner = a
valid identifier owned by another); `internal-call`/address-less `consumer`: the adapter
events ARRIVE at (cross-owner = a forged producer's valid event refused + audited);
`job`/`cli`: the runner.
RULE VALUES: slice `rules` literals land in the enforcing intent or a config DEFAULT
VALUE - never invented, never an open bound closed. COORDINATES: `build_coordinates`
empty => schedule no manifest; a unit needing a scaffold-missing coordinate dependsOn
the build-manifest task id, scheduled by the first finder, present before red compile;
the engine wires missing edges.

## Emission

ONE array per context at the brief's draft path, edited in the fewest calls (cascades
re-send the transcript). Lint with the command the brief prints; fix `ERR [id.field]:`
pointers; a defect shape repeated across tasks is ONE law missed. The
ENGINE runs `--emit` on the batch after the last context; claims, provider closure and
literal joins are batch laws DEFERRED past lint.

## observability floor

Every strategy step log (either floor spelling) is claimed VERBATIM by exactly ONE
stage-2 unit's `observability.step_logs` (rule j); every floor meter owned once and
paired with a step (rule u); correlation: one unit; sink/format/rolling: config literals.

## intent and shared literals

Intent 40-80 words; 180 refused at planning. Prose carries what the gates demand
(claim, literals, both signal branches); a tabled fact is never re-spelled; a
collaborator's method NAMED, never its parameters. Rule (z): one owner per literal, one
verbatim spelling, tabled in `ast_hints.meters` / `ast_hints.routes` /
`ast_hints.config` - never prose. SKILL.md (z4)-(z6).
