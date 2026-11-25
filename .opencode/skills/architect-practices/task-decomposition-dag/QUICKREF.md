# task-decomposition-dag - QUICK REFERENCE (planning sessions)

Default read. `SKILL.md` = one-line invariants keyed by the `ERR` pointer's letter;
open it ONLY for shapes this map does not summarize. `DECISIONS.md` = history, never
read.

## Draft record - what you write

TWO honest shapes, one shape per file, both expanded through ONE validator. The
COMPACT form is the taught DEFAULT; board objects stay honest but pay ~3x the
output tokens:
- COMPACT UNIT FORM:
  `{"n": 7, "project", "layer", "feature", "dependsOn": {"test": [], "code": []},
  "test": {"path", "export", "intent"},
  "code": {"path", "export", "intent", "ast_hints",
  "uses_meters"?, "uses_routes"?, "uses_config"?, "claims_steps"?, "root_gate"?},
  "refactor_intent"?}`
- BOARD TASK OBJECTS: full T1+T2+T3 records, keys exactly `id` (T<stage>-<3 digits>),
  `targetAgent`, `stage`, `dependsOn`, `path`, `kind`, `layer`, `feature`, `export`,
  `project`, `intent`, `ast_hints` (required 1-2), `observability` (stage-2).
Extras allowed: the (p) slice's lone stage-1 (the build manifest is ENGINE-queued;
the config unit and the root gate belong to the ROOT pass). OMISSIONS the engine
COMPLETES (R4): in BOARD objects you may omit T3 records and T1's `ast_hints` -
the code side owns the interface; claim issues the triple and mirrors the table.
Never a generator script or a per-task file. In the
COMPACT form the step-log syntax is `claims_steps` ONLY: never type
`code.observability` - the engine creates `observability.step_logs` at hydration
(rule (j) names the canonical field because the BOARD side - and the claimed,
hydrated compact side both end up carrying it). T1/T2 carry IDENTICAL
`ast_hints` tables - type the table ONCE per unit (z4).

## Graph & shapes (lint-checked)

- T1 dependsOn stage-0 + earlier T1s - NEVER a T2; T2 on its own T1 + the T2s of
  pinned producers; T3 on its own T2.
- stage 1 -> `agent-tester`, kind `test`, path = the TEST file (never the stage-2
  path); stage 2 -> `agent-coder`, kind `code`, production path; stage 3 ->
  `agent-evaluator`, kind `refactor`, stage-2's file.
- (p) DUTY: a project with inbound adapter units needs its request-path slice; the
  slice's stage-1 intent spells a marker the gate greps - `end-to-end`,
  `integration slice`, `request-path` - asserts only TABLED outcomes, citing them,
  and NAMES its isolation choice: UNIQUE identity per case, a RELATIVE delta
  against its own baseline, or a CLEANUP.
- Ids from the brief's next-free; pins resolve ONLY against queue/complete, the
  symbol table, or this file.

## Tables & references (ast_hints - the single interface truth)

Keys are BOARD SLOTS: the stack skill's Record-keys section gives each its language
reality. You type: `package`, `implements`, `dependencies` [{type, task_id}],
`methods` [{signature, returns, semantics?}] - EVERY boundary method, `returns` ""
when none, `semantics` REQUIRED when the intent rejects null or bounds an argument; a
signal's on_true/on_false behavior lives in the CONSUMER's intent (m).
You REFERENCE what other units own; the engine tables the canonical entry at claim -
`uses_meters`: [names] -> `ast_hints.meters` {name, duty: uses} (z);
`uses_routes`: ["METHOD /path"] -> `ast_hints.routes` {method, path, duty: uses};
`uses_config`: [paths] -> `ast_hints.config` {path, kind: value|list|map, fields?}
(z5); `claims_steps`: [strategy floor strings] -> `observability.step_logs` (j) - a
METER never claims a step; `root_gate`: true (typed by the ROOT pass ONLY) -> one per project, the engine tables
the root's whole address list into its routes (y4). The join (z) stays the batch
defense. A published `returns` type needs its consumer's pin or an out-of-process
boundary (k); the engine closes guarded-surface wiring (z6) and budget pair-tests (z7). A BOARD-object draft carries the same reference
keys directly on the stage-2 record - hydration is identical for both shapes.

## Persistence & config (emit-checked)

- (o) statements against a schema => the paired test demands the REAL migrated
  substrate run.
- (b) ONE config unit per domain (ROOT pass) seeds every `rules` default, every
  enabled reader's own keys (h), PACKAGED migration locations (r), the test-profile
  activation route, and the BOOT POSTURE of any seeded key whose mechanism row names
  one; `${VAR}` defaultable or seeded.
- (v) table the semantic path; the artifact's own kind spells the file layout.

## Security & egress (emit-checked)

- Entry unit per surface kind (y5): its intent names `surfaces[].name` verbatim and
  pins the enforcing unit; its T1 carries the row id + the per-kind cross-owner
  refusal case (y1-y3).
- (q) retryable inbound over append-only => named dedup identity; (s) corrections =>
  the identity-axis sentence spelled, both resend classes tested.
- (i) every published stream names its consumer unit - or the publisher's OWN intent
  spells the boundary (`out-of-process`/`external subscribers`/`downstream subscribers`).
- A refusal status is a TABLED fact - spec, `rules` or a stack line names it; else
  assert the behavior (refused + code-only body), never an invented oracle number.

## Intent economy

40-80 words (180 refused): claim, config literals, both signal branches. Never
re-spell a tabled fact; a collaborator's method is NAMED, not its parameters; values
come from `rules` - never invented, no open bound closed.
