"""DDD artifact gates: validate discovery files, context maps, and strategies.

The reports themselves are produced by the specialist agents; these gates decide
whether a phase may be skipped and whether one finished cleanly.
"""
import json
from pathlib import Path
import subprocess
import sys

import settings


def database_slugs():
    """Slugs of every execution strategy the architect wrote, in stable order."""
    return sorted(
        file.stem.removeprefix("execution-strategy-")
        for file in settings.COMPLETE_DIR.glob("execution-strategy-*.json")
    )


def validate_report(path, expect):
    """Validate a DDD report with the shared reader script."""
    path = Path(path)
    if not path.is_file():
        return f"report not found: {path}"
    command = [
        sys.executable,
        str(settings.READER_SCRIPT),
        "--report",
        str(path),
        "--expect",
        expect,
        "--validate-only",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(settings.ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        return f"cannot run report validator: {exc}"
    if result.returncode != 0:
        return (result.stdout or "").strip() or f"report validator exited {result.returncode}"
    return None


def validate_domain_files():
    """Gate for the per-domain discovery files in blackboard/domain/.

    Returns None when at least one file exists and every file parses as a JSON object.
    Otherwise returns the reason string.
    """
    if not settings.DOMAIN_DIR.is_dir():
        return f"discovery did not create {settings.DOMAIN_DIR.relative_to(settings.ROOT)}/"
    files = sorted(settings.DOMAIN_DIR.glob("domain-boundary-*.json"))
    if not files:
        return f"no domain-boundary-*.json files in {settings.DOMAIN_DIR.relative_to(settings.ROOT)}/"
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return f"{path.name} is not valid JSON: {exc}"
        if not isinstance(payload, dict):
            return f"{path.name} must be a JSON object"
    return None


def validate_context_maps():
    """Gate for the per-domain context maps in blackboard/context-map/.

    Every slice in blackboard/domain/ needs a valid context-map-<slug>.json.
    Returns None when all are valid, otherwise the reason string.
    """
    reason = validate_domain_files()
    if reason:
        return reason
    for domain_file in sorted(settings.DOMAIN_DIR.glob("domain-boundary-*.json")):
        slug = domain_file.stem.removeprefix("domain-boundary-")
        map_file = settings.CONTEXT_MAP_DIR / f"context-map-{slug}.json"
        reason = validate_report(map_file, "any")
        if reason:
            return f"{map_file.relative_to(settings.ROOT)}: {reason}"
    return None
