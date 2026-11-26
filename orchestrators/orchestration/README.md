# orchestration — the pipeline family (root: `pipeline.py`)

The ORDER of phases and their operator surface. Extracted from the 1,043-line
`pipeline.py` monolith (2026-11-26); `pipeline.py` remains the root and the thin
entry glue (stamped logging + phase sequence).

| Module | One-line failure home |
|---|---|
| `pipeline.py` | entry glue: print-stamp patch, CLI re-export, phase sequence |
| `cli_args.py` | the argparse shape shared by both orchestrator entrypoints |
| `run_phases.py` | phase ORDER: entry gates → DDD → strategy ladder → specs → planner → drain call |
| `plan_gates.py` | skip/reason/risk-surfacing: "is this phase already done?" |
| `plan_flow.py` | the planning loop: sessions (serial root + parallel sibling wave), claims, routed repair, ONE batch emit |
| `drain_flow.py` | execution: watch/single-pass loops, stuck/exhausted breakers, terminal tree, verify |

Imports are FLAT (`import plan_flow`) — the folders are registered on `sys.path`
by `../family_paths.py`, hooked into `settings` and the two entry scripts.
