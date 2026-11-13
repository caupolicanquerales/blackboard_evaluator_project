"""Cross-pass TDD attempt memory: ``blackboard/attempts/<task-id>.json``.

A session's cost is a flat per-turn floor (measured ~20K input tokens on the Copilot
backend; even a two-call session pays ~60K), so the token bill of a TDD wave is driven
by the NUMBER of coder sessions, not by their content. Before this ledger the
three-attempt budget of ``tdd_engine.execute_with_tdd`` was per pass: a unit that
exhausted it, got quarantined, and was restored by ``--retry`` re-armed from zero and
blindly re-derived the same failure - one unit burned 7 paid sessions in one afternoon
rediscovering an unchanged defect.

The ledger persists, per stage-2 unit, the attempts and weave-reject bounces already
consumed, the last failure reason (so a restored unit's first session starts INFORMED
instead of re-exploring from zero) and a digit-normalized failure signature (so a
repeated identical failure short-circuits without paying another session). The one
event that resets all of it is the unit's own CONTRACT moving - task record, red-phase
record or AST contract bytes: only then can a fresh derivation plausibly produce
something different. Stack-agnostic: it hashes bytes and stores strings.
"""
import hashlib
import json
import time

import settings


def path_for(task_id):
    return settings.ATTEMPTS_DIR / f"{task_id}.json"


def read(task_id):
    """The unit's ledger, or {} when it has no failure history."""
    try:
        data = json.loads(path_for(task_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write(task_id, **fields):
    """Merge fields into the ledger and stamp the update time."""
    settings.ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)
    data = read(task_id)
    data.update({k: v for k, v in fields.items() if v is not None})
    data["id"] = task_id
    data["updated"] = int(time.time())
    path_for(task_id).write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def clear(task_id):
    """Drop the ledger when a unit goes green: nothing left to remember."""
    try:
        path_for(task_id).unlink()
    except FileNotFoundError:
        pass


def contract_hash(task):
    """Identity of the unit's INPUTS: its task contract and the stage-1 records the
    coder must satisfy. When this moves, every past failure stopped being predictive."""
    digest = hashlib.sha1()
    digest.update(json.dumps({key: task.get(key) for key in sorted(settings.PROMPT_KEYS)
                              if task.get(key) is not None},
                             sort_keys=True, default=str).encode("utf-8", "ignore"))
    tester_id = next((dep for dep in (task.get("dependsOn") or [])
                      if str(dep).startswith("T1-")), None)
    if tester_id:
        for folder in (settings.RED_PHASE_DIR, settings.AST_CONTEXT_DIR):
            try:
                digest.update((folder / f"{tester_id}.json").read_bytes())
            except OSError:
                digest.update(b"absent")
    return digest.hexdigest()[:16]
