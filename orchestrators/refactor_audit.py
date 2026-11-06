"""Refactor audit: the engine's own proof of what a stage-3 session changed.

The evaluator self-reports ``changes[]`` in its artifact; self-reports are
claims. This module snapshots the domain's production sources before the
session and computes the real unified diff after the green artifact passes,
appending it to the same ``evaluate-results`` file under ``engine_diff``.
Deterministic, stdlib-only, and silent on any I/O trouble: the audit is
evidence, never a gate - the gate is the green test attached by the writer.
"""
import difflib
import json

import settings
import test_gate
import workspace

MAX_DIFF_LINES = 240  # per file: the artifact stays readable, the cap is announced


def snapshot_sources(task):
    """{relative path: text} for every production source of the task's domain."""
    main_root = workspace.project_root_for(task["project"]) / "src" / "main"
    project_root = workspace.project_root_for(task["project"])
    return {str(f.relative_to(project_root)): f.read_text(encoding="utf-8", errors="ignore")
            for f in test_gate.source_files(main_root)} if main_root.is_dir() else {}


def attach_engine_diff(task, before):
    """Append the ground-truth diff of the evaluator session to its artifact.

    ``before`` is a snapshot_sources() taken pre-session; files added, edited or
    removed by the agent are diffed against it. Missing artifact or unreadable
    file: skip silently - verification owns those failures.
    """
    artifact = settings.ROOT / "blackboard" / "evaluate-results" / f"{task['id']}.json"
    if before is None or not artifact.is_file():
        return
    after = snapshot_sources(task)
    changed = []
    for path in sorted(set(before) | set(after)):
        old, new = before.get(path), after.get(path)
        if old == new:
            continue
        patch = list(difflib.unified_diff(
            (old or "").splitlines(), (new or "").splitlines(),
            fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""))
        capped = len(patch) > MAX_DIFF_LINES
        changed.append({
            "file": path,
            "added": sum(1 for line in patch[:MAX_DIFF_LINES]
                         if line.startswith("+") and not line.startswith("+++")),
            "removed": sum(1 for line in patch[:MAX_DIFF_LINES]
                           if line.startswith("-") and not line.startswith("---")),
            "capped": capped,
            "patch": "\n".join(patch[:MAX_DIFF_LINES]) if capped else "\n".join(patch),
        })
    try:
        data = json.loads(artifact.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        data["engine_diff"] = changed
        data["engine_diff_files"] = len(changed)
        artifact.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        return
