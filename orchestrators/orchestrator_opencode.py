#!/usr/bin/env python3
"""Blackboard orchestrator (opencode backend) for the evaluator pipeline.

The pipeline runs in these phases over one business description from ``seed/``:

1. ``domain-boundary-discovery-specialist`` writes one small file per subdomain
   to ``blackboard/domain/domain-boundary-<slug>.json``.
2. ``domain-context-mapping-specialist`` reads those files and writes one
   context map per slice to ``blackboard/context-map/context-map-<slug>.json``.
3. ``agent-architect`` (strategy phase) writes one execution strategy per domain to
   ``blackboard/complete/execution-strategy-<slug>.json``.
4. ``agent-database-architect`` runs once per strategy and queues stage 0 database
   tasks (``T0-###``) through ``--emit``.
5. ``agent-architect`` (tasks phase) queues the application tasks (stage 1..3) and
   lists the database ids in ``dependsOn`` where a unit uses the store.
6. The blackboard workers drain the queue in stage order:

   stage 0 -> agent-container  (generate the project root / scaffold, database setup)
   stage 1 -> agent-tester     (read the task and create the test)
   stage 2 -> agent-coder      (payload only; body spliced by code-weaver-dispatcher)
   stage 3 -> agent-evaluator  (inspect the implementation and refactor it)

Agents never talk to each other: every hand-off is a validated file on disk.
"""
import sys

import opencode_backend
import pipeline


def main():
    parser = pipeline.build_parser(
        "Blackboard orchestrator (opencode): DDD discovery -> context mapping -> "
        "architect -> container/tester/coder/evaluator."
    )
    parser.add_argument("--no-auto", action="store_true", help="do not pass --auto to opencode")
    args = parser.parse_args()
    return pipeline.run(args, opencode_backend)


if __name__ == "__main__":
    sys.exit(main())
