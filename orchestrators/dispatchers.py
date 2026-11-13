"""Skill dispatchers called by the pipeline between agent stages.

Every function here shells out to a ``.opencode/skills`` script and interprets its
JSON contract; none of them import agent logic or touch source files directly.
"""
import json
import subprocess
import sys

import agent_runners
import settings
import task_queue
import telemetry
import test_gate
import workspace


BUILD_MARKERS = ("pom.xml", "build.gradle", "build.gradle.kts", "package.json",
                 "pyproject.toml", "go.mod", "requirements.txt", "Cargo.toml")


def red_phase_problem(task):
    """Return a reason string if blackboard/red-phase/<id>.json is missing or invalid, else None.

    The red-phase artifact lives on the repository-root blackboard (same root the
    queue writers use). `compile_error` and `assertion_failure` are VALID reds
    (java-junit5 skill); only a pre-implementation pass is rejected.
    """
    path = settings.RED_PHASE_DIR / f"{task['id']}.json"
    if not path.is_file():
        return f"red-phase file missing: {path.name}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"red-phase file unreadable: {exc}"
    if not isinstance(data, dict) or not data:
        return f"red-phase file is empty or not an object: {path.name}"
    if data.get("executed") is not True:
        return f"red-phase not executed: {path.name}"
    status = data.get("status")
    if status == "passed":
        return f"red-phase passed before implementation, not a valid red: {path.name}"
    return None


def record_missing_packages(record):
    """Absent packages/modules the tool normalized for ANY language: its structured field only.

    Syntax parsing belongs to run-test-tool (it knows javac vs python vs tsc vs go phrasing);
    re-parsing raw excerpts here would re-introduce the javac-only assumption into the
    orchestrator. Legacy records without the field simply produce no candidates.
    """
    return {str(pkg) for pkg in (record.get("missing_packages") or []) if isinstance(pkg, str)}


def _package_segments(pkg):
    """Directory-run candidates for one module/package path, in ANY ecosystem notation.

    A path is tried twice: split on "/" only (TS filenames keep their dots: "user.service",
    python relative "./greeter"), and split on "/" and "." (java/python dotted packages,
    go repo-prefixed imports). Relative "." / ".." markers are dropped.
    """
    raw = str(pkg).replace("\\", "/")
    slash = [s for s in raw.split("/") if s and s not in (".", "..")]
    dotted = [part for chunk in slash for part in chunk.split(".") if part]
    variants = []
    for segs in (slash, dotted):
        if segs and segs not in variants:
            variants.append(segs)
    return variants


def _internal_package_runs(project, index):
    """Directory paths the project owns, as (dir-segments, file-stem) pairs.

    Language-neutral: built from production task `path`s and source files on disk, in any
    layout (java src/main/java/..., python src/app/..., go internal/store/...). No grammar,
    no extension assumptions - pure path segments.
    """
    runs = []
    for task in index.values():
        if task.get("project") != project or not isinstance(task.get("path"), str):
            continue
        path = task["path"].replace("\\", "/")
        if "/test/" in "/" + path or path.startswith("test/") or "/tests/" in path:
            continue
        segments = [s for s in path.split("/") if s]
        if len(segments) > 1:
            runs.append((segments[:-1], segments[-1].rsplit(".", 1)[0]))
    root = workspace.project_root_for(project) if project else None
    if root and root.is_dir():
        for source in test_gate.source_files(root):
            try:
                relative = source.relative_to(root)
            except ValueError:
                continue
            parts = list(relative.parts[:-1])
            if parts:
                runs.append((parts, relative.name.rsplit(".", 1)[0]))
    return runs


def _package_is_internal(pkg, runs):
    """True when the package/module names a path this project owns or will produce.

    Matches: the package as a contiguous run inside a task/source path (java package dirs,
    python dotted module paths), or as the tail of an import path that carries a module/repo
    prefix (go). Anything else is third-party: only the manifest can add it, and no agent
    in this pipeline may edit the manifest - which is exactly the hole to abort on.
    """
    variants = _package_segments(pkg)
    if not variants:
        return True
    for dirs, stem in runs:
        path = list(dirs) + ([stem] if stem else [])
        for segments in variants:
            size = len(segments)
            if path and any(path[i:i + size] == segments for i in range(len(path) - size + 1)):
                return True
            if dirs and size >= len(dirs) and segments[-len(dirs):] == list(dirs):
                return True
    return False


def _build_file_rewritten_since(project, record_path):
    """True when the project build file changed after this record: the classpath hole may be closed."""
    if not project:
        return False
    root = workspace.project_root_for(project)
    try:
        stamp = record_path.stat().st_mtime
    except OSError:
        return False
    return any((root / name).is_file() and (root / name).stat().st_mtime > stamp
               for name in BUILD_MARKERS)


def foreign_missing_packages(record, project, record_path, index=None):
    """Missing packages the project itself will NEVER declare: third-party deps the manifest lacks.

    A manifest gap no agent may fix (stage 2 cannot edit build files), so the orchestrator
    aborts loudly. Anything matching an internal directory run is the domain's own business
    (a producer task or closure --emit resolves it).
    """
    if _build_file_rewritten_since(project, record_path):
        return []
    runs = _internal_package_runs(project, index if index is not None else task_queue.load_index(include_error=True))
    return [pkg for pkg in sorted(record_missing_packages(record))
            if not _package_is_internal(pkg, runs)]


def red_phase_dependency_gap(task):
    """Foreign missing packages of one tester task, or [] when the red is agent-fixable."""
    path = settings.RED_PHASE_DIR / f"{task['id']}.json"
    if not path.is_file():
        return []
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(record, dict):
        return []
    return foreign_missing_packages(record, task.get("project", ""), path)


def rerecord_red_phase(task):
    """Re-run the red command through run-test-tool and REWRITE the red-phase record.

    Used after the deterministic import repair rewrites a test file: the verdict must
    derive from the file as it now stands. Same two skill tools the tester piped
    together (run-test-tool | write-red-phase), so the record format is untouched.
    Returns True when the record was rewritten.
    """
    record_path = settings.RED_PHASE_DIR / f"{task['id']}.json"
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    command = record.get("command") if isinstance(record, dict) else None
    if not isinstance(command, str) or not command.strip():
        return False
    tool = [sys.executable, str(settings.RUN_TEST_TOOL),
            "--cwd", str(workspace.project_root_for(task.get("project", ""))),
            "--cmd", command, "--timeout", str(settings.TEST_GATE_TIMEOUT)]
    writer = [sys.executable, str(settings.RED_PHASE_WRITER), "--root", str(settings.ROOT),
              "--task-id", str(task["id"]), "--cmd", command]
    try:
        produced = subprocess.run(tool, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True,
                                  timeout=settings.TEST_GATE_TIMEOUT + 30, cwd=str(settings.ROOT))
        written = subprocess.run(writer, input=produced.stdout, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, text=True, timeout=60,
                                 cwd=str(settings.ROOT))
    except (OSError, subprocess.TimeoutExpired):
        return False
    return written.returncode == 0


def derive_red_phase(task):
    """Deterministic red recovery, zero sessions: the tester's test file is on disk but
    its red-phase record never was written (a session killed between the write and the
    record, or a batch interrupted mid-unit). The verdict is fully derivable - the
    scoped command comes from the test path, run-test-tool produces the verdict, the
    official writer persists it. Paying a whole agent session to re-derive a build
    result the engine can produce itself is pure waste; a genuinely wrong red still
    falls through to a real session, because the re-derived record is validated by the
    same red_phase_problem gate afterwards.
    """
    project_root = workspace.project_root_for(task.get("project", ""))
    test_path = str(task.get("path", ""))
    if not test_path or not (project_root / test_path).is_file():
        return False
    command = test_gate.command_from_test_path(test_path, project_root)
    if not command:
        return False
    tool = [sys.executable, str(settings.RUN_TEST_TOOL),
            "--cwd", str(project_root), "--cmd", command,
            "--timeout", str(settings.TEST_GATE_TIMEOUT)]
    writer = [sys.executable, str(settings.RED_PHASE_WRITER), "--root", str(settings.ROOT),
              "--task-id", str(task["id"]), "--cmd", command]
    try:
        produced = subprocess.run(tool, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True,
                                  timeout=settings.TEST_GATE_TIMEOUT + 30, cwd=str(settings.ROOT))
        written = subprocess.run(writer, input=produced.stdout, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, text=True, timeout=60,
                                 cwd=str(settings.ROOT))
    except (OSError, subprocess.TimeoutExpired):
        return False
    return written.returncode == 0


def scan_red_phase_gaps():
    """Foreign missing packages across every recorded red: {project: [packages]}.

    Checked again at every drain: a stale record from before a build-file rewrite is ignored,
    so fixing the scaffold is enough for the run to continue.
    """
    gaps = {}
    index = task_queue.load_index(include_error=True)
    for path in sorted(settings.RED_PHASE_DIR.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        task = index.get(str(record.get("task_id") or path.stem)) or {}
        project = str(task.get("project", ""))
        for pkg in foreign_missing_packages(record, project, path, index):
            gaps.setdefault(project or "unknown", [])
            if pkg not in gaps[project or "unknown"]:
                gaps[project or "unknown"].append(pkg)
    return gaps


def _dispatch(command, timeout, span_name, task_id, failure_reason):
    """Shared subprocess call for the skill dispatchers.

    Returns (returncode, stdout, telemetry_reason_or_None). ``failure_reason``
    turns a non-zero exit into the reason recorded on the span.
    """
    with telemetry.span(span_name, {"task": task_id}) as current:
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                cwd=str(settings.ROOT),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            telemetry.mark_error(current, str(exc))
            return None, str(exc), str(exc)
        if result.returncode != 0:
            reason = failure_reason(result.returncode, result.stdout)
            telemetry.mark_error(current, reason)
            return result.returncode, result.stdout, reason
        return result.returncode, result.stdout, None


def ast_context_problem(task):
    """Return a reason string if the unit's AST contract is missing or empty, else None.

    The coder writes the payload from the red-phase verdict plus this contract (constructors,
    calls, stubbed returns). Without it the coder guesses signatures the weaver splices and
    the green gate punishes with coder-retry sessions: the orchestrator enforces it exactly
    like the red-phase record, so the hallucination guard can never be silently skipped.
    """
    tester_id = next((str(dep) for dep in task.get("dependsOn", [])
                      if str(dep).startswith("T1-")), None)
    if not tester_id:
        return "stage-2 task has no stage-1 dependency: nothing defines its test contract"
    path = settings.BLACKBOARD / "ast-context" / f"{tester_id}.json"
    if not path.is_file():
        return f"ast-context missing: blackboard/ast-context/{tester_id}.json " \
               "(the tester's dispatch must produce it: production contract or test contract)"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"ast-context unreadable: {exc}"
    if not isinstance(data, dict) or not data.get("context"):
        return f"ast-context holds no extracted contract: {tester_id}.json"
    return None


def evaluate_result_problem(task):
    """Return a reason string if blackboard/evaluate-results/<id>.json is missing or not green, else None."""
    path = settings.ROOT / "blackboard" / "evaluate-results" / f"{task['id']}.json"
    if not path.is_file():
        return f"evaluate-results file missing: {path.name}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"evaluate-results file unreadable: {exc}"
    if not isinstance(data, dict) or not data:
        return f"evaluate-results file is empty or not an object: {path.name}"
    if data.get("executed") is not True:
        return f"evaluate-results not executed: {path.name}"
    final_test = data.get("final_test")
    status = final_test.get("status") if isinstance(final_test, dict) else None
    if status != "passed":
        return f"evaluator did not finish green (final_test.status={status!r})"
    return None


def run_ast_dispatcher(task):
    """Run the AST dispatcher once agent-tester finishes, then mark agent-coder as ready.

    The dispatcher reads <root>/blackboard and writes blackboard/ast-context/<id>.json.
    `unsupported` is an outcome, not a failure: a brand-new unit has no production source
    to extract yet, and agent-coder proceeds from the red-phase record. A dispatcher
    failure is reported but does not block agent-coder.
    """
    command = [sys.executable, str(settings.AST_DISPATCHER),
               "--root", str(settings.ROOT),
               "--project-root", str(workspace.project_root_for(task["project"])),
               "--task-id", task["id"]]
    print(f"[ast ] {task['id']} running ast-dispatcher")
    code, stdout, reason = _dispatch(
        command, settings.AST_DISPATCH_TIMEOUT, "blackboard.ast_dispatcher", task["id"],
        lambda exit_code, text: f"dispatcher exit {exit_code}",
    )
    if code is None:
        print(f"[ast ] {task['id']} dispatcher could not run: {stdout}")
        return False
    status = ""
    detail = ""
    try:
        payload = json.loads(stdout)
        status = str(payload.get("status") or "")
        detail = str(payload.get("reason") or "")
    except (TypeError, json.JSONDecodeError):
        pass
    if status == "unsupported":
        print(f"[ast ] {task['id']} no context yet (coder proceeds from red-phase): {detail[:200]}")
        return True
    if status == "test_contract":
        print(f"[ast ] {task['id']} greenfield contract extracted from the test "
              f"-> blackboard/ast-context/{task['id']}.json")
        return True
    if code != 0 or status not in ("ok", ""):
        print(f"[ast ] {task['id']} dispatcher exit {code}: {agent_runners.verify_tail(stdout)}")
        return False
    print(f"[ast ] {task['id']} context saved to blackboard/ast-context/{task['id']}.json")
    print(f"[next] {task['id']} tester done; agent-coder notified to start")
    return True


WEAVE_BASELINE_DIR = settings.BLACKBOARD / "weave-baseline"

# Reasons the WEAVER TOOL produced from the payload itself. The unit's code never ran;
# burning a TDD attempt on a tool rejection wastes a session and a full module build, so
# the reason is prefixed and execute_with_tdd bounces it back without counting the attempt.
# "not parseable" (yaml builder) and "cannot derive" (java type-name extraction from a
# malformed export) are the same class: the TOOL refused the payload shape, the unit's
# code never compiled at all - live 2026-11-12: "export: final CorrelationContext" was
# charged as three unit failures while it was a re-emit-field fix.
_PAYLOAD_REJECT_MARKERS = ("does not parse", "no builder matched", "payload", "unsupported",
                           "not parseable", "cannot derive")


def _reset_stale_weave(task, project_root):
    """Restore the unit's file to its pre-first-weave state before a NEW payload re-weaves it.

    The weaver ADDS members: retry payloads merge onto the previous weave, accumulating
    duplicate constructors, dropped class headers and vestigial methods (observed as the
    WindowBufferService frankenstein file). The first weave snapshots the target as it was;
    every later weave undoes the old splice first, so each attempt sees a clean file.
    Cache hits (unchanged payload) never reach a re-weave, so they are untouched.
    """
    import shutil
    payload_file = settings.ROOT / "blackboard" / "coder-changes" / f"{task['id']}.json"
    result_file = settings.BLACKBOARD / "weave-results" / f"{task['id']}.json"
    if not payload_file.is_file():
        return
    try:
        changes = json.loads(payload_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    target_rel = changes.get("targetFile") if isinstance(changes, dict) else None
    if not isinstance(target_rel, str) or not target_rel:
        return
    target = project_root / target_rel
    baseline = WEAVE_BASELINE_DIR / task["id"] / target_rel.replace("/", "__")
    if not baseline.exists():
        baseline.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            shutil.copy2(target, baseline)
        else:
            (baseline.parent / "absent").write_text(target_rel, encoding="utf-8")
        return
    try:
        reweave_pending = not result_file.is_file() or \
            payload_file.stat().st_mtime_ns > result_file.stat().st_mtime_ns
    except OSError:
        reweave_pending = True
    if not reweave_pending:
        return
    if (baseline.parent / "absent").exists():
        if target.is_file():
            target.unlink()
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline, target)


_PAYLOADLESS_GEN = 0
_PAYLOADLESS_CACHE = {}   # project -> (generation, set of T2 ids without payload)


def invalidate_payload_cache():
    """Any event that can change payload existence (attempt, apply, revert) bumps this."""
    global _PAYLOADLESS_GEN
    _PAYLOADLESS_GEN += 1


def payloadless_t2_ids(project):
    """T2 ids queued for one domain that have no coder payload yet - computed once
    per generation, not once per task. Pure file presence, any stack."""
    if _PAYLOADLESS_CACHE.get(project, (None, None))[0] != _PAYLOADLESS_GEN:
        ids = set()
        for f in settings.QUEUE_DIR.glob(f"T2-*-{project}.json"):
            try:
                peer = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            peer_id = peer.get("id") if isinstance(peer, dict) else None
            if isinstance(peer_id, str) and not (settings.ROOT / "blackboard" / "coder-changes"
                                                 / f"{peer_id}.json").is_file():
                ids.add(peer_id)
        _PAYLOADLESS_CACHE[project] = (_PAYLOADLESS_GEN, ids)
    return _PAYLOADLESS_CACHE[project][1]


def _weave_up_to_date(task, project_root, payload_file, result_file):
    """Orchestrator-side mirror of the dispatcher's own `_cached_success`.

    Checking it HERE avoids paying a python-startup subprocess (~140 ms) on every
    attempt of every pass just to be told 'nothing to apply' - the same answer for
    any payload language. When unsure (unreadable JSON, moved files), return False
    and let the real dispatcher decide."""
    try:
        if not payload_file.is_file() or not result_file.is_file():
            return False
        changes = json.loads(payload_file.read_text(encoding="utf-8"))
        previous = json.loads(result_file.read_text(encoding="utf-8"))
        if not isinstance(changes, dict) or not isinstance(previous, dict):
            return False
        if previous.get("status") != "ok" or not previous.get("executed"):
            return False
        if payload_file.stat().st_mtime_ns > result_file.stat().st_mtime_ns:
            return False
        target_rel = changes.get("targetFile")
        if not isinstance(target_rel, str):
            return False
        target = project_root / target_rel
        if not target.is_file():
            return False
        return target.stat().st_mtime_ns <= result_file.stat().st_mtime_ns
    except (OSError, json.JSONDecodeError):
        return False


def revert_weave(task, discard_payload=True):
    """Undo a unit's woven payload when the unit is quarantined (restores the baseline
    snapshotted by _reset_stale_weave, or deletes a file the unit created).

    A quarantined stage-2 unit with its broken payload still spliced into src/main is the
    worst tree state there is: it never passes a gate again (the task is in error/), yet
    every other unit's module-wide compile keeps failing on it - the whole T2 wave hangs
    on the few poisoned files. Reverting makes the tree contain only units that passed;
    dependents dangle honestly (cascade quarantine) and --retry can re-run the unit later.
    Returns True when the tree was restored.
    """
    import shutil
    payload_file = settings.ROOT / "blackboard" / "coder-changes" / f"{task['id']}.json"
    if not payload_file.is_file():
        return False
    try:
        changes = json.loads(payload_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    target_rel = changes.get("targetFile") if isinstance(changes, dict) else None
    if not isinstance(target_rel, str) or not target_rel:
        return False
    baseline = WEAVE_BASELINE_DIR / task["id"] / target_rel.replace("/", "__")
    if not baseline.exists() and not (WEAVE_BASELINE_DIR / task["id"] / "absent").exists():
        return False
    target = workspace.project_root_for(task.get("project", "")) / target_rel
    try:
        if (WEAVE_BASELINE_DIR / task["id"] / "absent").exists():
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(baseline, target)
    except OSError:
        return False
    (settings.BLACKBOARD / "weave-results" / f"{task['id']}.json").unlink(missing_ok=True)
    (settings.GATE_CACHE_DIR / f"{task['id']}.json").unlink(missing_ok=True)
    print(f"[revert] {task['id']}: woven payload undone ({target_rel}) - quarantined code must not poison the shared tree")
    if discard_payload:
        # A unit that failed its OWN attempts 3x has a proven-bad payload: keeping it
        # lets the next resume skip-agent re-splice identical poison. Untested cascade
        # victims keep theirs - it was never disproven, and the next weave can pass.
        payload_file.unlink(missing_ok=True)
    invalidate_payload_cache()
    return True


def run_code_weaver_dispatcher(task):
    """Splice the agent-coder payload into the source tree via the code-weaver dispatcher.

    The dispatcher reads blackboard/coder-changes/<id>.json, selects the weaver
    executable by payload language and records blackboard/weave-results/<id>.json.
    Returns None on success, or a reason string; the reason is fed back to the
    coder as TDD retry feedback, so it must explain what to re-emit with --retry.
    """
    payload_file = settings.ROOT / "blackboard" / "coder-changes" / f"{task['id']}.json"
    result_file = settings.BLACKBOARD / "weave-results" / f"{task['id']}.json"
    project_root = workspace.project_root_for(task["project"])
    if _weave_up_to_date(task, project_root, payload_file, result_file):
        print(f"[weave] {task['id']} payload already applied (tree unchanged since); dispatcher skipped")
        return None
    _reset_stale_weave(task, project_root)
    command = [
        sys.executable,
        str(settings.CODE_WEAVER_DISPATCHER),
        "--root", str(settings.ROOT),
        "--project-root", str(project_root),
        "--task-id", task["id"],
    ]
    print(f"[weave] {task['id']} running code-weaver-dispatcher")
    code, stdout, reason = _dispatch(
        command, settings.WEAVER_DISPATCH_TIMEOUT, "blackboard.code_weaver_dispatcher", task["id"],
        lambda exit_code, text: _weaver_failure_reason(text),
    )
    if code is None:
        return f"code-weaver dispatcher could not run: {reason}"
    if code != 0:
        print(f"[weave] {task['id']} failed (exit {code})")
        if any(marker in (reason or "").lower() for marker in _PAYLOAD_REJECT_MARKERS):
            return "weave-reject: " + reason
        return reason
    invalidate_payload_cache()
    print(f"[weave] {task['id']} changes applied; result saved to blackboard/weave-results/{task['id']}.json")
    return None


def _weaver_failure_reason(output_text):
    """Compact the dispatcher JSON into a single actionable line for coder retry feedback."""
    try:
        summary = json.loads(output_text)
    except (TypeError, json.JSONDecodeError):
        summary = None
    detail = ""
    if isinstance(summary, dict):
        detail = str(summary.get("reason") or summary.get("stdout") or summary.get("stderr") or "").strip()
    if not detail:
        detail = agent_runners.verify_tail(output_text)
    return f"code-weaver failed: {detail[:400] if detail else 'no dispatcher output'}"
