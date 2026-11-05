#!/usr/bin/env python3
"""Blackboard orchestrator (GitHub Copilot backend) for the evaluator pipeline.

Same contract, phase order and queue format as ``orchestrator_opencode.py``;
the only difference is that agents are activated headlessly through the Copilot
CLI using the custom agent profiles in ``.github/agents/``.
"""
import sys

import copilot_backend
import pipeline


def main():
    parser = pipeline.build_parser(
        "Blackboard orchestrator (GitHub Copilot CLI): DDD discovery -> context mapping -> "
        "architect -> container/tester/coder/evaluator."
    )
    parser.add_argument("--copilot-bin", default=copilot_backend.DEFAULT_COPILOT_BIN,
                        help="copilot binary (or COPILOT_BIN)")
    parser.add_argument("--allow-tool", default=copilot_backend.DEFAULT_ALLOW_TOOL,
                        help="comma-separated tools granted to agents")
    args = parser.parse_args()
    return pipeline.run(args, copilot_backend)


if __name__ == "__main__":
    sys.exit(main())
