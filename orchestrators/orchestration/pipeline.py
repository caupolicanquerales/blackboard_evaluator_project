"""pipeline - the orchestrator entry module, thin by contract (2026-11-26 split).

Owns only what must live at entry time: the stamped-print patch (every phase
module's print goes through it), the shared CLI shape re-export, and the phase
glue. The body of the pipeline lives in cohesive modules, one failure home each:

    run_phases.py   the ORDER of phases (entry gates, DDD, strategy, specs)
    plan_gates.py   skip/reason/risk-surfacing helpers (what is already done)
    plan_flow.py    the planning loop (sessions, claims, routed repair, batch emit)
    drain_flow.py   execution (watch loop, breakers, terminal tree, verify)
    task_queue.py   task creation top layer (claim/lint/emit) over plan_drafts,
                    plan_board, plan_wiring, plan_laws

Backend-specific behavior arrives through the `backend` module parameter
(copilot_backend / opencode_backend); nothing in this tree names a CLI.
"""
import builtins
import time

import workspace

_REAL_PRINT = builtins.print


def _stamp_print(*args, **kwargs):
    """Tagged `[phase ] ...` lines get a wall clock so a resume's replay flood and
    live progress are distinguishable in the log; passthrough output untouched.
    ALWAYS flush (2026-11-20): a block-buffered log loses every line when a run is
    stopped - and a supervisor that cannot see the last line cannot diagnose a stop."""
    kwargs.setdefault("flush", True)
    first = args[0] if args else ""
    if isinstance(first, str) and first.lstrip().startswith("["):
        _REAL_PRINT(time.strftime("%H:%M:%S") + " " + first, *args[1:], **kwargs)
        return
    _REAL_PRINT(*args, **kwargs)


builtins.print = _stamp_print

from cli_args import build_parser                        # noqa: E402
from plan_flow import (PLANNER_REPAIR_ROUNDS, _next_free_for,  # noqa: E402
                       _repair_fingerprint, _plan_domain_tasks)
from plan_gates import (_application_tasks_queued, _database_reason,  # noqa: E402
                        _migration_files, _security_reason,
                        _strategy_phase_gaps, _surface_security_risks,
                        _surface_spec_risks)
from run_phases import docker_gate, ddd_and_strategy, entry, specs_and_tasks  # noqa: E402
from drain_flow import (drain, _terminal_tree_report, _stuck_report,  # noqa: E402
                        _closure_blockers, _pass_summary)


def run(args, backend):
    """Execute the full pipeline for one backend. Returns the process exit code."""
    code = entry(args, backend)
    if code is not None:
        return code
    # the seed path is deterministic pure resolution - identical bytes to what
    # entry resolved; the DDD phase needs it as a parameter across the split.
    description = workspace.resolve_seed(args.seed)
    code = ddd_and_strategy(args, backend, description)
    if code is not None:
        return code
    code = specs_and_tasks(args, backend)
    if code is not None:
        return code
    return drain(args, backend)
