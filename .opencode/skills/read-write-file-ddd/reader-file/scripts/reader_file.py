#!/usr/bin/env python3
"""Read and validate a strategic DDD report from the blackboard.

Default input is the boundary draft written by the domain-boundary-discovery
specialist. The validated JSON is printed on stdout so the context-mapping
specialist can consume it without hand-reading the file.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_READ = 2
EXIT_INVALID = 3

sys.dont_write_bytecode = True

DEFAULT_REPORT = "blackboard/domain-boundary-draft.json"
EXPECTED_TYPES = {
    "discovery": "domain-boundary-draft",
    "final": "domain-boundary-analysis",
}


def load_validator():
    script = (
        Path(__file__).resolve().parents[2]
        / "writer-file"
        / "scripts"
        / "writer_file.py"
    )
    if not script.is_file():
        return None, f"writer validation module not found: {script}"
    spec = importlib.util.spec_from_file_location("ddd_writer_file", script)
    if spec is None or spec.loader is None:
        return None, f"cannot load writer validation module: {script}"
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - report any import failure verbatim
        return None, f"cannot load writer validation module {script}: {exc}"
    return module, None


def read_report(path):
    if not path.is_file():
        return None, f"report not found: {path}"
    try:
        return path.read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, f"cannot read report {path}: {exc}"


def build_summary(report, path):
    return {
        "report_type": report["report_type"],
        "path": str(path),
        "bounded_contexts": [context["name"] for context in report["bounded_contexts"]],
        "subdomain_count": len(report["subdomains"]),
        "ubiquitous_language_count": len(report["ubiquitous_language"]),
        "assumption_count": len(report["assumptions"]),
        "context_relationships": len(report.get("context_map", [])),
        "cross_boundary_flows": len(report.get("cross_boundary_flows", [])),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Read a validated strategic DDD report from the blackboard.",
        epilog="Exit codes: 0 ok, 1 report not found, 2 read error, 3 invalid report.",
    )
    parser.add_argument(
        "--report",
        default=DEFAULT_REPORT,
        metavar="FILE",
        help=f"report to read (default: {DEFAULT_REPORT})",
    )
    parser.add_argument(
        "--expect",
        choices=("discovery", "final", "any"),
        default="discovery",
        help="expected report kind (default: discovery)",
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print the JSON payload")
    parser.add_argument("--summary", action="store_true", help="print a summary instead of the full report")
    parser.add_argument("--validate-only", action="store_true", help="validate without printing the report")
    args = parser.parse_args()

    path = Path(args.report).expanduser()
    raw, reason = read_report(path)
    if reason:
        print(f"[reader-file] {reason}", file=sys.stderr)
        return EXIT_NOT_FOUND if "not found" in reason else EXIT_READ

    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[reader-file] report is not valid JSON: {exc}", file=sys.stderr)
        return EXIT_INVALID

    validator, reason = load_validator()
    if reason:
        print(f"[reader-file] {reason}", file=sys.stderr)
        return EXIT_INVALID

    reason = validator.validate_report(report)
    if reason:
        print(f"[reader-file] invalid report: {reason}", file=sys.stderr)
        return EXIT_INVALID

    if args.expect != "any" and report["report_type"] != EXPECTED_TYPES[args.expect]:
        print(
            f"[reader-file] expected a {EXPECTED_TYPES[args.expect]} report "
            f"but found {report['report_type']!r}",
            file=sys.stderr,
        )
        return EXIT_INVALID

    if args.validate_only:
        return EXIT_OK

    if args.summary:
        print(json.dumps(build_summary(report, path), indent=2, ensure_ascii=False))
        return EXIT_OK

    print(
        json.dumps(
            report,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
            ensure_ascii=False,
        )
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
