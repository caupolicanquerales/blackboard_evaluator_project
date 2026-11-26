"""plan_drafts - the draft lifecycle and THE TASK-CREATION CONTRACT.

FACT/LAW/VERDICT state machine, draft paths, sidecars, plan-input snapshots.
Split from task_queue.py (2026-11-26) so a future incident names its own module:
wrong freshness verdict -> this file; wrong queue records -> plan_board; wrong
rewrites -> plan_wiring; wrong refusal -> plan_laws; wrong flow -> task_queue."""

import json
import re
from pathlib import Path
import settings
import ddd
import tasks


DRAFT_DIR = Path("/tmp") / "tasks"


def draft_path(slug, context):
    return DRAFT_DIR / f"{slug}-{ddd.context_stem(context)}.json"


def clear_drafts(slug):
    """A stale draft of a previous (aborted) plan must not join this one's batch."""
    removed = []
    for path in sorted(DRAFT_DIR.glob(f"{slug}-*.json")):
        if path.name.startswith(f"T0-{slug}") or path.name.endswith(".draft-meta.json"):
            continue
        path.unlink(missing_ok=True)
        removed.append(path.name)
        path.with_name(path.name[:-len(".json")] + ".draft-meta.json").unlink(missing_ok=True)
    return removed
PLAN_SNAPSHOT_VERSION = 1
_INPUT_VALIDATORS = {
    "execution-strategy": "validate_strategy",
    "security-spec": "validate_security_spec",
    "performance-spec": "validate_performance_spec",
    "ai-spec": "validate_ai_spec",
}


def _snapshot_input_files(slug):
    return [f for f in settings.COMPLETE_DIR.glob(f"*{slug}.json")
            if any(f.name.startswith(k) for k in _INPUT_VALIDATORS)]


def snapshot_plan_inputs(slug):
    files = {}
    for f in _snapshot_input_files(slug):
        try:
            files[f.name] = f.read_text(encoding="utf-8")
        except OSError:
            pass
    snap = settings.BLACKBOARD / "snapshots" / f"{slug}-plan-inputs.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(json.dumps({"version": PLAN_SNAPSHOT_VERSION, "files": files},
                               indent=1), encoding="utf-8")
    return snap


def _shape(doc):
    if isinstance(doc, dict):
        return {k: _shape(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_shape(v) for v in doc]
    return "leaf"


def verify_plan_inputs(slug):
    """Returns (restored_names, amended_names). restored = unlawful mutation rolled
    back to the phase-1 snapshot; amended = shape-identical text change that still
    passes the input's own gate (rule (t)/(k) amendments: accepted, phase 1 stays
    the truth in the snapshot). Called at launch start (heals previous-run damage
    instead of dying on it) and after every session/repair boundary."""
    snap = settings.BLACKBOARD / "snapshots" / f"{slug}-plan-inputs.json"
    try:
        saved = json.loads(snap.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], []
    restored, amended = [], []
    for name, old_text in (saved.get("files") or {}).items():
        f = settings.COMPLETE_DIR / name
        try:
            current = f.read_text(encoding="utf-8")
        except OSError:
            current = ""
        if current == old_text:
            continue
        prefix = next((k for k in _INPUT_VALIDATORS if name.startswith(k)), None)
        lawful = False
        if prefix:
            try:
                old_doc, new_doc = json.loads(old_text), json.loads(current)
                validator = getattr(ddd, _INPUT_VALIDATORS[prefix])
                lawful = _shape(old_doc) == _shape(new_doc) and validator(slug) is None
            except (ValueError, TypeError, AttributeError):
                lawful = False
        if lawful:
            amended.append(name)
            continue
        f.write_text(old_text, encoding="utf-8")
        restored.append(name)
    return restored, amended
LAW_VERSION = "2026-11-26.1"   # facts/law/verdict split + SKILL.md de-hash + attempt cap
MAX_REDRAFTS = 2               # sessions a single context may be RE-billed after rejection


def _plan_input_paths(slug):
    """The binding FACT inputs of a planning draft: strategy + the three specs.
    DECISIONS.md, QUICKREF.md and the contract SKILL.md are deliberately NOT here:
    the first two are history/derivative, the third is LAW prose - law rides
    LAW_VERSION and re-validates, it never re-bills a session by touching a file."""
    return [ddd.strategy_path(slug),
            *(settings.COMPLETE_DIR / f"{prefix}{slug}.json"
              for prefix in ("security-spec-", "performance-spec-", "ai-spec-"))]


def _input_hashes(slug):
    import hashlib
    out = {}
    for f in _plan_input_paths(slug):
        try:
            out[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
        except OSError:
            out[f.name] = "<absent>"
    return out


def draft_meta_path(slug, context):
    return DRAFT_DIR / f"{slug}-{ddd.context_stem(context)}.draft-meta.json"


def stamp_draft_meta(slug, context, clean=True, state="rejected"):
    """claim writes the sidecar: the FACT hashes the draft was drafted under, the LAW
    version that judged it, and the claim VERDICT (R2 2026-11-25 content-freshness;
    2026-11-26 fact/law/verdict split): 'clean' lets the next launch skip the session,
    'rejected'/'broken' escalate it to a real re-draft - bounded by MAX_REDRAFTS.
    Re-draft attempts survive a re-stamp (they count launches, not claims)."""
    path = draft_meta_path(slug, context)
    attempts = 0
    try:
        attempts = int(json.loads(path.read_text(encoding="utf-8")).get("attempts") or 0)
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    try:
        path.write_text(json.dumps({"input_hashes": _input_hashes(slug),
                                    "claim": "clean" if clean else state,
                                    "law": LAW_VERSION,
                                    "attempts": attempts}, indent=1), encoding="utf-8")
    except OSError:
        pass


def draft_state(slug, context):
    """The task-creation state machine (see THE TASK-CREATION CONTRACT above).

    'absent'    - no draft: the session drafts it.
    'broken'    - unparseable draft or unreadable sidecar: cleared and re-drafted.
    'stale'     - FACTS moved (strategy/spec changed under the draft): cleared, the
                  session re-drafts - units for an old plan cannot be repaired into a
                  new one.
    'unjudged'  - no sidecar (killed session) OR the LAW moved OR the sidecar predates
                  the verdict era: send the bytes to the claim gate - re-VALIDATION is
                  free (Python), a session is billed only when the law refuses.
    'fresh'     - facts match, law matches, verdict clean: skip the session; claim
                  still re-runs its bookkeeping and the batch stays the authority.
    'rejected'  - the gate refused these bytes under this law: escalate to one real
                  re-draft, up to MAX_REDRAFTS attempts; beyond that 'exhausted'.
    'exhausted' - re-drafted MAX_REDRAFTS times and still refused: stop loudly; the
                  repair ladder is spent and more sessions would be a loop, not a fix."""
    path = draft_path(slug, context)
    if not path.is_file():
        return "absent"
    try:
        batch = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "broken"
    if not (isinstance(batch, list) and batch and all(isinstance(t, dict) for t in batch)):
        return "broken"
    meta_path = draft_meta_path(slug, context)
    if not meta_path.is_file():
        return "unjudged"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "broken"  # sidecar unreadable: damaged, not unjudged
    current = _input_hashes(slug)
    stored = meta.get("input_hashes") or {}
    if any(stored.get(key) != value for key, value in current.items()):
        return "stale"
    if str(meta.get("law") or "") != LAW_VERSION:
        return "unjudged"   # law moved (or predates the split): re-VALIDATE, never re-bill
    verdict = str(meta.get("claim", "clean"))  # pre-verdict sidecars: claimed under
    if verdict == "clean":                     # these exact facts - the gate's own
        return "fresh"                         # record, honest by construction
    if int(meta.get("attempts") or 0) >= MAX_REDRAFTS:
        return "exhausted"
    return "rejected" if verdict == "rejected" else "broken"


def record_redraft_attempt(slug, context):
    """One billed re-draft against a rejected draft - the cap counts launches, so a
    context that refuses every session stops the run instead of burning the board."""
    path = draft_meta_path(slug, context)
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        meta = {"input_hashes": _input_hashes(slug), "claim": "rejected",
                "law": LAW_VERSION}
    meta["attempts"] = int(meta.get("attempts") or 0) + 1
    try:
        path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    except OSError:
        pass
    return meta["attempts"]


def draft_is_fresh(slug, context):
    """Fresh = parses as a non-empty array of task objects AND the stamped input
    hashes equal the inputs on disk now. A draft with NO sidecar is unjudged, not
    stale - draft_state spells the distinction the claim gate routes on."""
    return draft_state(slug, context) == "fresh"


# THE GAP CHANNEL IS GONE (2026-11-25 root restructure): `missing_coordinates` and
# `config_paths` existed only because the build manifest and the config unit belonged to
# "whichever context drafted first" - a later context could not edit A's file and needed
# a side channel. PHASE 1.5 owns the singletons deterministically (engine-queued
# manifest; ROOT-pass config unit and gate), so the channels had no reason to exist and
# no engine code mutates another draft for them. `apply_coordinate_gaps` is kept as a
# frozen no-op ONLY so an OLD board's lingering .gaps.json files stay readable: the
# engine clears those drafts as stale anyway (their plan inputs moved).


def apply_coordinate_gaps(slug, contexts):
    """Deprecated no-op (PHASE 1.5): reports nothing, mutates nothing, bills nothing."""
    return [], []
