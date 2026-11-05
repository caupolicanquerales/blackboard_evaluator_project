"""The TDD loop and the dependency-graph queue drain.

``drain_queue`` is backend-agnostic: the entry scripts pass ``invoke_for_task``
(the backend's agent call) and it wires per-task invoke/verify closures around
the skill dispatchers and the verification gate.
"""
import heapq
import json

import dispatchers
import settings
import task_queue
import test_gate
import tasks
import telemetry
import verification
import workspace


_ERROR_FILE_RE = __import__("re").compile(r"\[ERROR\] (\S+\.java):\[\d+")


BATCH_MIN_PEERS = 4
BATCH_MAX = 12


def _pending_exports_of(project, exclude_id):
    """Simple export names of still-queued stage-2 tasks of one domain."""
    names = set()
    for f in settings.QUEUE_DIR.glob(f"T2-*-{project}.json"):
        try:
            peer = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if peer.get("id") != exclude_id and isinstance(peer.get("export"), str):
            names.add(peer["export"].split(".")[-1])
    return names


def _payloadless_peers(task):
    """This task plus same-domain stage-2 tasks still lacking a coder payload."""
    import os
    same = []
    for f in settings.QUEUE_DIR.glob("T2-*.json"):
        try:
            peer = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (peer.get("project") == task["project"]
                and not os.path.exists(settings.ROOT / "blackboard" / "coder-changes"
                                       / f"{peer.get('id')}.json")):
            same.append(peer)
    ordered = [task] + sorted((p for p in same if p.get("id") != task["id"]),
                              key=lambda p: str(p.get("path")))
    return ordered


class DeferredTask(Exception):
    """Stage-2 verification blocked by not-yet-implemented peer tasks; retry next pass."""


def execute_with_tdd(task, invoke, verify):
    """Run one task. Stage 2 retries the coder with the verification log, up to MAX_TDD_RETRIES.

    invoke(feedback) -> (ok, reason): runs the agent and checks its output exists.
    verify() -> (ok, reason): for stage 2 first weaves the coder payload into the
    source tree, then re-runs the recorded test (green gate), then the build gate.
    Agent failures are not retried; only verification failures are.
    """
    attempts = settings.MAX_TDD_RETRIES if task["stage"] == settings.TDD_STAGE else 1
    feedback = None
    reason = ""
    for attempt in range(1, attempts + 1):
        ok, reason = invoke(feedback)
        if not ok:
            return False, reason
        ok, reason = verify()
        if ok:
            return True, ""
        if attempt < attempts:
            print(f"[tdd ] {task['id']} verification failed (attempt {attempt}/{attempts}); retrying coder with log")
        feedback = reason
    if attempts > 1:
        reason = f"TDD failed after {attempts} attempts: {reason}"
    return False, reason


def _peers_outstanding(task):
    """True when stage-2 tasks of the same domain are still in the queue (unevaluated peers)."""
    project = task.get("project", "")
    return any(settings.QUEUE_DIR.glob(f"T2-*-{project}.json"))


def _blocked_by_peers(result, task):
    """True when a red stage-2 gate is NOT this unit's own fault.

    Surefire compiles the whole source set: a missing peer (or a test that will
    only compile once other tasks land) fails every task of the domain. The only
    compile failure worth retrying is one LOCATED IN this unit's own file
    (javac prints "location: .../File.java:[l,c]"); everything else is a peer
    problem the coder cannot fix, so defer instead of burning the three attempts.
    """
    if not isinstance(result, dict) or result.get("status") not in ("compile_error", "error"):
        return False
    if result.get("status") == "compile_error":
        missing_tokens = _identifier_tokens(" ".join(str(item) for item in (result.get("missing_symbols") or [])))
        if missing_tokens & _pending_exports_of(task["project"], task["id"]):
            return True          # a queued peer will resolve this symbol; do not burn attempts
    excerpt_lines = [str(line) for line in (result.get("excerpt") or [])]
    files = [m.group(1) for line in excerpt_lines if (m := _ERROR_FILE_RE.search(line))]
    own = str(task.get("path", "")).split("/")[-1]
    main_hits = [f for f in files if "/src/main/" in f]
    if own and any(own in f for f in main_hits):
        return False                      # javac blames THIS unit's source: real retry
    if files and not main_hits:
        return True                       # only test files fail: peers/contract issue, defer
    if result.get("status") != "compile_error":
        return False
    export = str(task.get("export", "")).split(".")[-1]
    items = result.get("missing_symbols") or []
    if export and export in _identifier_tokens(" ".join(str(item) for item in items)):
        return False
    return bool(items) or any("cannot find symbol" in line.lower() for line in excerpt_lines)


def _identifier_tokens(text):
    import re
    return set(re.findall(r"[A-Za-z_$][\w$]*", text))


def quarantine_dependents(failed_id, tasks, files, dependents, remaining):
    """Send every transitive dependent of a failed task to the error queue."""
    pending = [failed_id]
    while pending:
        source = pending.pop()
        for dependent_id in dependents.get(source, []):
            if dependent_id not in remaining:
                continue
            dependent_task = tasks[dependent_id]
            if dependent_task["stage"] == 0:
                continue
            file = files[dependent_id]
            reason = f"dependsOn {source} not resolvable in queue or complete"
            task_queue.send_to_error(file, reason, dependent_task)
            print(f"[error] {file.name}: {reason}")
            remaining.discard(dependent_id)
            pending.append(dependent_id)


def drain_queue(args, invoke_for_task):
    """Drain the queue once using an in-memory dependency graph and ready heap.

    The queue and completion folders are scanned once per pass. Tasks that become
    ready after a completion are pushed onto a heap ordered by (stage, project, path),
    keeping work grouped by domain within each stage.

    ``invoke_for_task(task, feedback)`` runs the backend-specific agent call.
    With ``args.parallel > 1`` independent domains run concurrently; at most one
    task per project is in flight so concurrent builds never share a target/ dir.
    """
    kept, complete_ids = task_queue.load_valid_tasks()
    if not kept:
        return 0, []

    by_id = {task["id"]: task for _, task in kept}
    files = {task["id"]: file for file, task in kept}
    by_stage = {}
    for _, task in kept:
        by_stage.setdefault(task["stage"], []).append(task["id"])

    pending_deps = {}
    dependents = {}
    for task_id, task in by_id.items():
        unmet = [dep for dep in task["dependsOn"] if dep not in complete_ids]
        pending_deps[task_id] = len(unmet)
        for dep in unmet:
            dependents.setdefault(dep, []).append(task_id)

    processed = {"count": 0}
    remaining = set(by_id)

    def closures_for(task):
        def invoke(feedback):
            payload = settings.ROOT / "blackboard" / "coder-changes" / f"{task['id']}.json"
            if (task["stage"] == settings.TDD_STAGE and feedback is None and payload.is_file()):
                print(f"[skip-agent] {task['id']} coder payload already recorded; going straight to verify")
                return True, ""
            if task["stage"] == settings.TDD_STAGE and feedback is None and not payload.is_file():
                batch = getattr(invoke_for_task, "batch", None)
                siblings = _payloadless_peers(task) if batch else []
                if len(siblings) >= BATCH_MIN_PEERS:
                    picked = siblings[:BATCH_MAX]
                    print(f"[batch ] {task['id']} batching coder payloads for {len(picked)} tasks of {task['project']}")
                    try:
                        batch(picked)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[batch ] batch session failed ({exc}); falling back to per-task")
            ok, reason = invoke_for_task(task, feedback)
            expected = workspace.project_root_for(task["project"]) / task["path"]
            if ok and task["stage"] != settings.TDD_STAGE and not expected.exists():
                return False, f"agent finished but {task['path']} was not created"
            if ok and task["stage"] == settings.TESTER_STAGE:
                problem = dispatchers.red_phase_problem(task)
                if problem:
                    return False, problem
                dispatchers.run_ast_dispatcher(task)
            if ok and task["stage"] == settings.EVALUATOR_STAGE:
                problem = dispatchers.evaluate_result_problem(task)
                if problem:
                    if _peers_outstanding(task):
                        raise DeferredTask(f"evaluate artifact pending ({problem}) while peers remain queued")
                    return False, problem
            return ok, reason

        def verify():
            project_root = workspace.project_root_for(task["project"])
            if task["stage"] == settings.TDD_STAGE:
                problem = dispatchers.run_code_weaver_dispatcher(task)
                if problem:
                    return False, problem
                problem, result = test_gate.green_test_result(task)
                if problem:
                    if _blocked_by_peers(result, task):
                        raise DeferredTask(problem)
                    return False, problem
                return True, ""      # the green gate supersedes the build gate
            if task["stage"] == settings.EVALUATOR_STAGE:
                return verification.verify_project(
                    project_root, args.verify, args.verify_timeout)
            return verification.run_verification(
                project_root, args.verify, args.verify_scope, task, args.verify_timeout)

        return invoke, verify

    def attempt(task):
        invoke, verify = closures_for(task)
        try:
            ok, reason = execute_with_tdd(task, invoke, verify)
        except DeferredTask as defer:
            return "defer", str(defer)
        return ("done", "") if ok else ("fail", reason)

    def finalize(task_id, outcome, detail, stage, ready, limit_hit):
        file = files[task_id]
        task = by_id[task_id]
        if outcome == "done":
            with telemetry.span("blackboard.complete", {"file": file.name,
                                                        **telemetry.task_attributes(task)}):
                file.replace(settings.COMPLETE_DIR / file.name)
            print(f"[done] {task['id']}")
            complete_ids.add(task_id)
            remaining.discard(task_id)
            for dependent_id in dependents.get(task_id, []):
                if dependent_id not in remaining:
                    continue
                pending_deps[dependent_id] -= 1
                if pending_deps[dependent_id] == 0 and by_id[dependent_id]["stage"] == stage:
                    heapq.heappush(ready, (tasks.task_sort_key(by_id[dependent_id]), dependent_id))
        elif outcome == "defer":
            print(f"[wait  ] {task['id']} waiting for peers: {detail[:120]}")
        else:
            task_queue.send_to_error(file, detail, task)
            print(f"[fail] {task['id']}: {detail}")
            remaining.discard(task_id)
            quarantine_dependents(task_id, by_id, files, dependents, remaining)
        processed["count"] += 1

    workers = max(1, int(getattr(args, "parallel", 1) or 1))

    def next_ready(stage, ready, busy):
        parked = []
        picked = None
        while ready:
            item = heapq.heappop(ready)
            _, task_id = item
            if task_id not in remaining or pending_deps[task_id] != 0:
                continue
            if workers > 1 and by_id[task_id]["project"] in busy:
                parked.append(item)
                continue
            picked = item
            break
        for item in parked:
            heapq.heappush(ready, item)
        return picked

    for stage in sorted(by_stage):
        ready = []
        for task_id in by_stage[stage]:
            if task_id in remaining and pending_deps[task_id] == 0:
                heapq.heappush(ready, (tasks.task_sort_key(by_id[task_id]), task_id))

        if workers == 1:
            while ready:
                item = next_ready(stage, ready, set())
                if item is None:
                    break
                _, task_id = item
                task = by_id[task_id]
                print(f"[run ] {task['id']} -> {task['targetAgent']} ({task['path']})")
                outcome, detail = attempt(task)
                finalize(task_id, outcome, detail, stage, ready, False)
                if args.limit and processed["count"] >= args.limit:
                    return processed["count"], []
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=workers) as pool:
                inflight = {}
                busy = set()
                while ready or inflight:
                    while ready and len(inflight) < workers:
                        item = next_ready(stage, ready, busy)
                        if item is None:
                            break
                        _, task_id = item
                        task = by_id[task_id]
                        busy.add(task["project"])
                        print(f"[run ] {task['id']} -> {task['targetAgent']} ({task['path']})")
                        inflight[pool.submit(attempt, task)] = task_id
                    if not inflight:
                        break
                    future = next(as_completed(inflight))
                    task_id = inflight.pop(future)
                    busy.discard(by_id[task_id]["project"])
                    outcome, detail = future.result()
                    finalize(task_id, outcome, detail, stage, ready, False)
                    if args.limit and processed["count"] >= args.limit:
                        return processed["count"], []

        if any(task_id in remaining for task_id in by_stage[stage]):
            blocked = sorted(remaining, key=lambda item: tasks.task_sort_key(by_id[item]))
            return processed["count"], blocked
    if remaining:
        blocked = sorted(remaining, key=lambda item: tasks.task_sort_key(by_id[item]))
        return processed["count"], blocked
    return processed["count"], []
