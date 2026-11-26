"""cli_args - the shared CLI surface: the argparse shape both orchestrator
entrypoints use. (Extracted from pipeline.py, 2026-11-26.)"""
import argparse

import settings



def build_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--seed", metavar="FILE", help="business description to analyze (default: first seed/*_description.md)")
    parser.add_argument("--output", metavar="DIR", help="directory where the project is generated (default: projects/<seed title>)")
    parser.add_argument("--force", action="store_true", help="regenerate existing DDD reports")
    parser.add_argument("--watch", action="store_true", help="poll the queue continuously")
    parser.add_argument("--interval", type=int, default=5, help="seconds between polls in watch mode")
    parser.add_argument("--timeout", type=int, default=900, help="seconds before an agent run is aborted")
    parser.add_argument("--verify", choices=settings.VERIFY_MODES, default="typecheck", help="post-task compile/check gate run in the project root")
    parser.add_argument("--verify-scope", choices=("task", "global"), default="task", help="verification scope")
    parser.add_argument("--verify-timeout", type=int, default=300, help="seconds before verification times out")
    parser.add_argument("--limit", type=int, default=0, help="stop after N tasks (0 = no limit)")
    parser.add_argument("--parallel", type=int, default=1,
                        help="concurrent domains during drain (one task per project in flight)")
    parser.add_argument("--emit", nargs="+", metavar="FILE", help="validate and emit task JSON files to queue, then exit")
    parser.add_argument("--lint", metavar="FILE",
                        help="validate ONE planning draft file against the single-file law "
                             "(schema, dangling pins, writable channel); batch laws - duty "
                             "claims, step-log ownership, the shared-literal join, provider "
                             "closure - are DEFERRED to the engine's batch --emit, then exit")
    parser.add_argument("--retry", nargs="*", metavar="ID", default=None,
                        help="move quarantined tasks back to the queue (all, or only ids matching these patterns), then continue")
    parser.add_argument("--replan", nargs="+", metavar="SLUG",
                        help="archive one or more domains' plan (execution strategy, security, "
                             "performance and AI specs, and stage 1-3 records, all to "
                             "blackboard/archive/) so the phases re-run for them on this "
                             "launch: the fix when a strategy names no inbound surface or a "
                             "spec arrived after its decomposition")
    parser.add_argument("--plan-only", action="store_true",
                        help="run every PLAN phase (discovery, mapping, strategy, database, "
                             "security, performance, AI, planner sessions, gaps, batch "
                             "emit) and STOP before the docker gate and the drain - the "
                             "supervised way to measure plan cost: zero execution sessions "
                             "are billed, the queue holds the finished plan")
    parser.add_argument("--skip-docker-check", action="store_true",
                        help="do not gate the queue drain on a reachable Docker daemon")
    return parser
