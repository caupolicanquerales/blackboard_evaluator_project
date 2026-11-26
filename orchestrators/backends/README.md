# backends — the CLI adapter family

`pipeline.run(args, backend)` is backend-agnostic by contract: the `backend`
module supplies `run_discovery/run_mapping/run_strategy/run_database/run_security/
run_performance/run_ai/run_planner/run_planner_repair/run_pass` (+ optional
`preflight`, `RUNNER_SCRIPT`). Nothing else in the engine names a CLI.

| Module | Adapter |
|---|---|
| `copilot_backend.py` | GitHub Copilot CLI headless sessions: profile resolution from `.github/agents/`, JSON event stream, hard tool-budget kill, per-call budget watchdog |
| `opencode_backend.py` | OpenCode CLI sessions (`opencode run`) over the `.opencode/agents/` profiles |

Both are thin: phase post-checks call the gates (`ddd.validate_*`, `task_queue`,
`tdd_engine.drain_queue`); agent subprocess plumbing lives in `../agent_runners.py`
(shared, with the death-shim that orphans nothing). Entry points stay at the
`orchestrators/` root: `orchestrator_github.py`, `orchestrator_opencode.py`.
