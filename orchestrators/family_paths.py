"""family_paths - the sys.path bootstrap for the orchestrator families (2026-11-26).

The refactor split monoliths into cohesive family folders, each keeping its
root script:

    orchestration/   pipeline.py + cli_args, run_phases, plan_gates, plan_flow, drain_flow
    task_contract/   tasks.py    + task_identity, task_signals, task_rules
    task_creation/   task_queue.py + plan_drafts, plan_board, plan_wiring, plan_laws
    backends/        copilot_backend.py + opencode_backend.py  (the CLI adapters)

Modules keep importing each other by FLAT name (``import task_queue``), across
families as well as within - so the three folders must be importable BEFORE any
family module resolves. This module performs that insertion; it is idempotent and
imports nothing from the project, so it is safe at any point in an import chain.

Every project module already imports ``settings`` before any family module
(verified by the ordering scan at split time), and ``settings`` imports this
module first - which is why no other file needs a bootstrap line. The two
standalone entrypoints import it explicitly as the first project import, so even
a direct ``python3 orchestrators/orchestrator_github.py`` primes the path before
``import pipeline`` resolves into orchestration/.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
FAMILIES = ("orchestration", "task_contract", "task_creation", "backends")


def install():
    """Put the family folders on sys.path so every module keeps its flat import
    name (``import task_queue``, ``import tasks``, ``import pipeline``) no matter
    which folder physically holds it. Idempotent; the folders share no module
    names with each other or with the shared root modules, so order is only
    about resolution speed."""
    for name in reversed(FAMILIES):
        path = os.path.join(_HERE, name)
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


install()
