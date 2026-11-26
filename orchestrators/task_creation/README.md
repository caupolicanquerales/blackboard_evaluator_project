# task_creation — the task_queue family (root: `task_queue.py`)

How tasks GET INTO THE QUEUE: claim, lint, batch emit, refusal routing.
Extracted from the 3,239-line `task_queue.py` (2026-11-26); `task_queue.py`
remains the root: the top flow + the stable `task_queue.X` re-export surface.

| Module | One-line failure home |
|---|---|
| `task_queue.py` | top flow: `claim_draft`, `lint_draft`, `emit_tasks`, `route_refusals`, re-exports |
| `plan_drafts.py` | THE TASK-CREATION CONTRACT: FACT/LAW/VERDICT state machine, sidecars, plan-input snapshots |
| `plan_board.py` | queue records: index, ids, quarantine/retry, stage-0 discovery & recovery, replan, symbol table, the drafting "world" |
| `plan_wiring.py` | deterministic rewrites: expansion, triple synthesis, mirroring, hydration, pin/gate/config wiring, SIBLING-ANCHOR resolution |
| `plan_laws.py` | every law check as pure verdict functions (z-joins, security reach, steplog, manifest/stage-0/channel/reserved, slice coverage, budget closure) |

DAG (no cycles): drafts → board → wiring → laws → task_queue.
