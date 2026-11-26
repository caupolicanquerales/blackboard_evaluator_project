# task_contract — the tasks family (root: `tasks.py`)

What a task record IS and what its text means. Extracted from the 1,149-line
`tasks.py` (2026-11-26); `tasks.py` remains the root: `validate()` + the stable
`tasks.X` re-export surface every caller already uses.

| Module | One-line failure home |
|---|---|
| `tasks.py` | the record contract front door: `validate`, re-exports |
| `task_identity.py` | schema & shape: ids, file names, exports, produced types, ast_hints rules, stage-0 family membership, publisher/signal return grammar |
| `task_signals.py` | prose-vs-table signals: what a unit's intent TEXT advertises (artifacts, config triggers, nulls, meters, mechanisms) |
| `task_rules.py` | the mechanized plan rules (o)/(p)/(q)/(s)/(t)/(u) + the batch `plan_consistency` join |

DAG (no cycles): identity → signals → rules → tasks.
