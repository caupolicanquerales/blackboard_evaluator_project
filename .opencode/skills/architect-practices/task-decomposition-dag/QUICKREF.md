# task-decomposition-dag - QUICK REFERENCE (planning sessions)

The FULL contract (rules (a)-(z), every incident's history) is `SKILL.md` beside this
file. A per-context planning session loads THIS quickref; it loads SKILL.md ONLY when a
lint/emit `ERR` pointer cites a rule letter or shape not summarized here, or when
drafting the first plan on a new stack. The linter and the batch emit are the contract's
teeth; this page is its map.

## Task object - exactly these keys, no others

`id` (T<stage>-<3 digits>; suffix matches the stage; ids unique board-wide, never reused),
`targetAgent`, `stage`, `dependsOn`, `path`, `kind`, `layer`, `feature` (null unless
layer is features), `export`, `project` (the domain slug), `intent`, `ast_hints`
(required stage 1-2, optional elsewhere).

## Stage / agent / kind / path

- stage 1 -> `agent-tester`, kind `test`, path = the TEST artifact the tester creates -
  never the production file, never the paired stage-2 path (rule w).
- stage 2 -> `agent-coder`, kind `code`, path = the production file.
- stage 3 -> `agent-evaluator`, kind `refactor`, shares stage 2's file.
- Every unit of work = the T1+T2+T3 triple, ONE per unit; T1 and T2 carry the IDENTICAL
  `ast_hints` table.
- The stage graph: T1 dependsOn stage-0 scaffold + earlier units' T1 tasks - NEVER a
  stage-2 task (red precedes green, the drain orders by `dependsOn` only); T2 dependsOn
  its own T1 + the T2 tasks of pinned producers; T3 dependsOn its own T2.

## `ast_hints` - the single API truth (testers assert ONLY this, coders build ONLY this)

`package` (every segment a legal identifier - never a reserved word like "interface"),
`implements` (supertype names), `dependencies` [{type, task_id}] - one pin per
collaborator, pinned to the task that produces it; a consumed type's own table spells
every member its consumers touch.
`methods` [{signature, returns, semantics?}] - boundary methods, parameter and return
types spelled exactly as the language declares them (the tech-stack skill is the
spelling source); `returns` "" when none; `semantics` REQUIRED whenever the intent
rejects null or bounds an argument (rule d).
`meters` [{name, duty: owns|uses}] - meter names live ONLY here (rule z): `owns` on the
ONE unit that registers the name, `uses` on every unit recording or asserting it.
`routes` [{method, path, duty: serves|uses}] - request paths live ONLY here: `serves` on
the ONE inbound unit that answers the pair.
`config` [{path, kind: value|list|map, fields?}] - property paths live ONLY here (rule
z5): the unit whose record BINDS the path owns the shape; the config unit cites
path/kind/fields VERBATIM.

## Claim form (machine-checked at the batch emit)

The digest slice delivers duties already COMPLETE: `spec_ref`, `capability`,
`unit_kind`, `obligation`, `surface`/`test_duty`/`measurement` where they exist, and the
matched `table_row` cells. Discharge each one INSIDE the enforcing STAGE-2 unit by
spelling its `spec_ref` AND `capability` VERBATIM beside the mechanism copied from the
row - a bare id is a citation, not a mapping. Security adds the geometry: the unit that
IS the surface (intent names `surfaces[].name` verbatim) pins the enforcing unit and its
T1 carries the row id + the CROSS-OWNER refusal case (y1/y2/y3). Performance/AI ride the
(y1) form only. PA- assumptions and AI roles never carry claims.
A unit whose copied mechanism needs a coordinate the scaffold lacks
dependsOn the build-manifest task id - classpath before first red compile.

## Emission - one file, one lint, then the engine

ONE JSON array per bounded context at the brief's draft path, created directly with the
edit tool - never a generator script, never one file per task. `python3 <runner>
--lint <file>`; fix what the `ERR [id.field]:` pointers name; ONE defect shape repeated
across tasks is a law missed - rewrite the file once, do not cascade edits. The ENGINE
runs the single batch `--emit` after the last context; duty claims, provider closure and
the shared-literal joins are batch laws and are DEFERRED past lint.

## observability floor

Every strategy step log - flat list or per-context `{context: [logs]}` mapping, both
flatten - is claimed VERBATIM by exactly ONE stage-2 unit's `observability.step_logs`
field (rule j); every floor meter is owned once and paired with a step (rule u);
correlation gets one middleware unit; sink/format/rolling are config-unit literals.

## intent

40-80 words; 180 refused at planning. Prose carries what the gates demand (claim,
literals, both signal branches); a fact a table pins is never re-spelled, and a
collaborator's method is NAMED, never spelled with its parameter list.

## Shared-literals law in one line (z)

One owner per literal, one verbatim spelling per value, tabled in `ast_hints.meters` /
`ast_hints.routes` / `ast_hints.config` - never in prose. Full text: SKILL.md rules
(l), (z), (z4), (z5), (z6).
