#!/usr/bin/env python3
"""Blackboard orchestrator (opencode backend) for the evaluator pipeline.

The pipeline runs in these phases over one business description from ``seed/``:

1. ``domain-boundary-discovery-specialist`` writes one small file per subdomain
   to ``blackboard/domain/domain-boundary-<slug>.json``. It is the only phase that reads the business
   description, so it is also the only place a security waiver can be recorded - as
   ``security_directive{required:false, quote, source:"description"}`` with the user's sentence copied
   VERBATIM; the engine greps that quote in the description file the slice names, and an absent
   directive means SECURITY REQUIRED.
2. ``domain-context-mapping-specialist`` reads those files and writes one
   context map per slice to ``blackboard/context-map/context-map-<slug>.json``.
3. ``agent-strategy-architect`` (phase 1 of the split architect) writes one execution strategy
   per domain to ``blackboard/complete/execution-strategy-<slug>.json``, including its
   ``surfaces`` table: every inbound surface the domain receives (name, kind, context,
   operations). The surface ``name`` is the join key the next phases are measured against.
4. ``agent-database-architect`` runs once per strategy and queues stage 0 database
   tasks (``T0-###``) through ``--emit``.
5. ``agent-security-architect`` runs once per strategy - unconditionally, there is no skip flag;
   the only exception is a description-verified ``security_directive`` waiver, printed as
   ``WAIVED`` and marked in the terminal verdict - and writes
   ``blackboard/complete/security-spec-<slug>.json`` - threat model, principals, the
   authorization matrix (ONE row per declared surface, its ``surface`` copying the strategy's
   ``name`` verbatim), data classification, trust boundaries, invariants and the duties
   handoff, all in abstract capability tokens. It queues nothing and names no mechanism. A
   spec that leaves an ``open_questions`` entry stops the run: only phase 1 can answer it.
5a. ``agent-performance-architect`` runs once per strategy like security - unconditional:
   every executable context has a load side (the observability-floor doctrine). It writes
   ``blackboard/complete/performance-spec-<slug>.json``: a workload entry per declared surface
   (or a reasoned exemption), budgets whose ``measurement.kind`` is from a CLOSED deterministic
   enum (no wall clock exists in that enum on purpose - R5), invariants, and duties in abstract
   tokens. No mechanism, no vendor, ever.
5b. ``agent-ai-architect`` runs ONLY when the domain's slice carries an
   ``ai_directive{required:true, quote, source:"description"}`` whose quote the engine verified
   VERBATIM against the description file - an AI capability is a product decision the user
   states, never an agent's inference (the security waiver's mirror: same witness law,
   opposite polarity). It writes ``blackboard/complete/ai-spec-<slug>.json``: model roles with
   statefulness and data classes, capabilities from a CLOSED token vocabulary keyed verbatim to
   surfaces/flows, each with a deterministic measurement, and the mandatory offline-port
   invariant - no test may ever reach a live model endpoint.
6. ``agent-planner-architect`` (phase 2 of the split architect) runs ONE session per bounded
   context: strategy + that context's digest slice (duties pre-joined to their rule rows
   and matched mapping-table rows) + the symbol table of the drafted contexts, then the
   ENGINE emits the whole domain as one batch. Lists the database ids in ``dependsOn``
   where a unit uses the store, and claims each spec duty by spelling its ``spec_ref`` and
   ``capability`` token in the enforcing unit's intent - mapping capability tokens to the
   stack's real mechanisms is this phase's job, not the security step's. The claim must sit
   on the stage-2 unit that ENFORCES it, that unit must be pinned by the entry adapter that
   IS the surface, and the adapter's own test must assert the cross-owner case.
7. The blackboard workers drain the queue in stage order:

   stage 0 -> agent-container  (generate the project root / scaffold, database setup)
   stage 1 -> agent-tester     (read the task and create the test)
   stage 2 -> agent-coder      (payload only; body spliced by code-weaver-dispatcher)
   stage 3 -> agent-evaluator  (inspect the implementation and refactor it)

Agents never talk to each other: every hand-off is a validated file on disk.
"""
import sys

import family_paths  # noqa: F401  - first project import: registers the family
                      # folders (orchestration/, task_contract/, task_creation/)
                      # on sys.path so the flat imports below resolve post-split.
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
