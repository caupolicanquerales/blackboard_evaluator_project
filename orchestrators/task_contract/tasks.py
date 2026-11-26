"""tasks - the task-record contract, top layer: validate() plus the stable
re-export surface. The heavy content lives in three cohesive modules
(2026-11-26 split): task_identity (what a record is), task_signals (what its
prose says), task_rules (what the plan must guarantee). Every historical
``tasks.X`` caller keeps working unchanged."""

from pathlib import Path
import json
import workspace
import re
import settings

# stable public API across the split (2026-11-26)
from task_identity import CAMEL_TYPE_RE, MIGRATION_SCRIPT_NAME_RE, PUBLISHER_FORMS, SIGNAL_FORMS, STATIC_CALL_RE, UNCONSTRUCTIBLE_RE, _instance_members, _is_static, _member_name, _returns_publisher, _returns_signal, _simple_return_type, _table_signatures, depends_transitively, exported_product, is_database_task, is_type_shape, produced_types, step_log_entries, task_file_name, task_sort_key, validate_ast_hints
from task_signals import CONFIG_ARTIFACT_TAILS, CONFIG_TRIGGER_RE, CONSTRUCTOR_CLAIM_RE, FAIL_OUTCOME_RE, FILE_ARTIFACT_RE, INTENT_WORD_CEILING, INTENT_WORD_TARGET, MECHANISM_PROMISE_RE, METER_CLAIM_RE, NULL_REJECT_RE, STEP_STOP_TOKENS, VIA_TOKEN_RE, _mechanism_claimed, _meter_pairs, _path_is_config_artifact, _signature_parameters, _step_tokens, _surface_norm, per_record_signal_problems
from task_rules import APPEND_CHAIN_RE, ARRAY_BODY_RE, ARRAY_REQUEST_TYPES, BOUNDARY_MARKER_RE, CORRECTION_RE, CWD_RELATIVE_LOCATION_RE, DEDUP_RE, DML_CLAIM_RE, GENERIC_SELF_REGISTRATION_RE, INBOUND_RE, INTEGRATION_MARK_RE, MIGRATION_SCHEME_RE, REAL_SUBSTRATE_RE, SELF_REGISTRATION_RES, STREAM_BODY_RE, STREAM_REQUEST_TYPES, VALUE_AXIS_RE, _strategy_text, plan_consistency, strategy_language




def validate(task, index, planning=False):
    """Validate one blackboard task against the evaluator pipeline schema.

    planning=True (task emission) additionally demands the API contract table for
    stages 1-2: those freeze the unit's public surface, and a tester left without the
    table improvises signatures from prose - which froze two contradictory contracts
    against each other in seed 002 and deadlocked the whole domain behind them.
    Resume validation (planning=False) only shape-checks: older boards stay readable.

    Returns a reason string, or None when the task is valid.
    """
    allowed = set(settings.REQUIRED_KEYS) | set(settings.OPTIONAL_KEYS)
    if not set(task) <= allowed or set(settings.REQUIRED_KEYS) - set(task):
        missing = sorted(set(settings.REQUIRED_KEYS) - set(task))
        extra = sorted(set(task) - allowed)
        return f"schema mismatch, missing={missing} extra={extra}"
    stage = task["stage"]
    if not isinstance(stage, int) or stage not in settings.STAGE_AGENTS:
        return f"stage must be one of {sorted(settings.STAGE_AGENTS)}"
    match = settings.ID_PATTERN.match(str(task["id"]))
    if not match:
        return f"id must match {settings.ID_PATTERN.pattern}"
    if int(match.group(1)) != stage:
        return "id stage suffix differs from stage"
    if task["targetAgent"] != settings.STAGE_AGENTS[stage]:
        return f"targetAgent must be {settings.STAGE_AGENTS[stage]!r} for stage {stage}"
    if task["kind"] not in settings.STAGE_KINDS[stage]:
        return f"kind must be one of {list(settings.STAGE_KINDS[stage])} for stage {stage}"
    if not isinstance(task["path"], str) or not task["path"].strip():
        return "path must be a non-empty string"
    if not isinstance(task["export"], str) or not task["export"].strip():
        return "export must be a non-empty string"
    if not isinstance(task["intent"], str) or not task["intent"].strip():
        return "intent must be a non-empty string"
    if (not isinstance(task["project"], str) or not task["project"].strip()
            or task["project"] != workspace.slugify(task["project"])):
        return "project must be a domain slug"

    if stage == 0:
        if task["layer"] != "root":
            return "stage 0 layer must be root"
        if task["feature"] is not None:
            return "stage 0 feature must be null"
        if task["dependsOn"] and not is_database_task(task, index):
            return ("stage 0 dependsOn must be empty except for database-family tasks "
                    "(the migration directory, a V<n>__ script, or a scaffold/manifest-hung "
                    "bootstrap: the database phase's concerns hang off the scaffold because "
                    "they write INSIDE the tree it creates)")
        return None

    if task["layer"] not in settings.LAYERS:
        return f"layer must be one of {list(settings.LAYERS)}"
    has_feature = isinstance(task["feature"], str) and bool(task["feature"])
    if task["layer"] == "features" and not has_feature:
        return "feature required when layer is features"
    if task["layer"] != "features" and has_feature:
        return "feature must be null unless layer is features"
    if not isinstance(task["dependsOn"], list):
        return "dependsOn must be a list"

    for dep in task["dependsOn"]:
        if not isinstance(dep, str) or not settings.ID_PATTERN.match(dep):
            return f"dependsOn id invalid: {dep!r}"
        dep_task = index.get(dep)
        if (dep_task is None or not isinstance(dep_task.get("stage"), int)
                or not isinstance(dep_task.get("path"), str)):
            return f"dependsOn {dep} not resolvable in queue or complete"
        if dep_task["stage"] > stage:
            return (f"dependsOn {dep} is in a later stage than this task - the stage graph "
                    "is law: a stage-1 test NEVER depends on a stage-2 task (red must run "
                    "before green, the drain orders units only by dependsOn); drop this "
                    "entry, or point it at the producer unit's stage-1 pair")
        if depends_transitively(dep, task["id"], index):
            return f"dependsOn {dep} creates a dependency cycle"
    if "ast_hints" in task:
        reason = validate_ast_hints(task["ast_hints"])
        if reason:
            return reason
        hints = task["ast_hints"]
        if hints["implements"] and not hints["methods"]:
            return ("ast_hints.methods must spell the surface of every implemented "
                    "supertype (implements is non-empty but methods is empty)")
    if "observability" in task:
        obs = task["observability"]
        if (not isinstance(obs, dict) or set(obs) != {"step_logs"}
                or not isinstance(obs["step_logs"], list) or not obs["step_logs"]
                or not all(isinstance(s, str) and s.strip() for s in obs["step_logs"])):
            return ('observability must be exactly {"step_logs": [non-empty strings]}: the '
                    "verbatim execution-strategy entries this unit owns and its stage-1 "
                    "test must assert (the claim is the machine surface, never prose)")
    if planning and stage in (1, 2):
        words = len(str(task["intent"]).split())
        if words > INTENT_WORD_CEILING:
            return (f"intent runs to {words} words (target {INTENT_WORD_TARGET}, ceiling "
                    f"{INTENT_WORD_CEILING}): the plan of one domain is emitted in a single turn and "
                    "re-sent on every later one, so prose volume is paid twice. Move what "
                    "`ast_hints` already pins (signatures, types, collaborators) out of the sentence, "
                    "and split any unit whose contract genuinely needs more: one unit that must "
                    "explain itself at length is usually two units. Keep every token the gates demand "
                    "in prose - the security spec_ref + capability + mechanism, the config literals, "
                    "the both-branch semantics - but meter names and request paths are NOT prose: they "
                    "belong in ast_hints.meters / ast_hints.routes (rule (z))")
        if "ast_hints" not in task:
            return ("stage 1-2 tasks carry ast_hints: the API contract table "
                    "(package, implements, dependencies, methods) the tester and coder "
                    "must not improvise")
        if NULL_REJECT_RE.search(str(task["intent"])):
            methods = (task["ast_hints"] or {}).get("methods") or []
            unmarked = [m for m in methods if not str(m.get("semantics") or "").strip()]
            if unmarked:
                return ("intent pins a null-rejecting surface but "
                        f"{len(unmarked)}/{len(methods)} ast_hints.methods entries carry no "
                        "`semantics` note: state the initial-state encoding (a named constant "
                        "the producing unit ships, or the nullable alternative) - a mandatory "
                        "field that rejects null with no legal way to represent its pre-use "
                        "state froze two contradictory contracts (seed-002 D1)")
        # RANGE-CLAIM -> CONSTRUCTOR SEMANTICS (2026-11-16): an intent that states a
        # numeric/argument invariant ("revision (>=1, else ...)") must carry it in the
        # constructor's table entry. The consumer units' testers see the injected
        # collaborator TABLE, never this unit's prose; a prose-only invariant let four
        # units' frozen fixtures construct revision=0 against a domain that rejects it,
        # and those units died 3/3 on tests they cannot edit.
        claims = CONSTRUCTOR_CLAIM_RE.findall(str(task["intent"]))
        if claims and task.get("stage") in (1, 2):
            product = (exported_product(task) or "").strip()
            ctor = next((m for m in ((task.get("ast_hints") or {}).get("methods") or [])
                         if isinstance(m, dict)
                         and str(m.get("signature", "")).startswith(product + "(")), None)
            if ctor is not None and not str(ctor.get("semantics") or "").strip():
                return (f"intent states constructor invariants on {sorted(set(claims))} but "
                        f"the '{product}' constructor table entry carries no `semantics`: "
                        "consumer units' testers receive ONLY the collaborator table - spell "
                        "the valid-argument ranges and the sanctioned construction (factory, "
                        "initial value) into that entry's `semantics`, or the next unit's "
                        "fixture guesses an illegal literal and dies on this record "
                        "(seed-002 2026-11-16: revision (>=1) lived only in prose; four "
                        "consumer tests fabricated 0)")
        if (task["ast_hints"] or {}).get("methods") and \
                UNCONSTRUCTIBLE_RE.search(str(task["intent"])) and \
                _instance_members(task["ast_hints"], exported_product(task) or ""):
            return ("intent asserts an UNCONSTRUCTIBLE shape (private constructor / utility "
                    "class / non-instantiable) while ast_hints.methods binds INSTANCE members: "
                    "no caller can ever reach them and no payload satisfies both - bind the "
                    "members `static` in the table, or drop the constructor claim and let the "
                    "unit be instantiated/injected (seed-002 rerun F2 froze the whole domain "
                    "behind exactly this pair)")
    return None
