"""drain_flow - the execution side: watch/single-pass drain loops, the
stuck/exhausted breakers with their operator reports, the terminal
delivered-tree verdict, and the closure pre-drain gate.

(Extracted from pipeline.py, 2026-11-26.)"""
import json
import re
import time

import assembly
import closure
import ddd
import settings
import task_queue
import tdd_engine
import workspace

from run_phases import docker_gate



def _pass_summary(pass_started, processed, blocked):
    """One heartbeat line per drain pass: wall cost plus the cumulative board
    counters, so progress is readable across restarts without parsing the log."""
    def count(folder):
        try:
            # task records only: the architect's strategy files also live under the board
            return sum(1 for f in folder.glob("*.json")
                       if '"id"' in f.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            return 0
    print("[pass  ] wall {:.1f}s | queue {} complete {} quarantined {} | processed {} blocked {}"
          .format(time.monotonic() - pass_started, count(settings.QUEUE_DIR),
                  count(settings.COMPLETE_DIR), count(settings.ERROR_DIR),
                  processed, len(blocked or [])))




def _closure_blockers():
    """Summary of test imports without producer tasks, per domain (empty string when closed)."""
    root = workspace.get_project_root()
    index = task_queue.load_index(include_error=True)
    offenders = []
    services = sorted((root / settings.PROJECTS_SUBDIR).glob("*")) if (root / settings.PROJECTS_SUBDIR).is_dir() else []
    for service in services:
        found = closure.gaps(service, service.name, index)
        if found:
            names = ", ".join(g["class"] for g in found[:3])
            offenders.append(f"{service.name}: {len(found)} unclosed import(s) [{names}...]")
    return "; ".join(offenders)




def _stuck_report(blocked):
    """The stuck-drain escalation text: who blocks, who owns the blockers, what to run.

    A watch drain whose passes bill nothing and complete nothing while tasks stay
    blocked is provably waiting on events the engine itself cannot create. The report
    names the quarantined owners and the last deferral reasons so the operator lands
    on the remedy (--retry / closure --emit / source fix) instead of reading a spin.
    """
    import re
    waits = tdd_engine.wait_snapshot()
    quarantined = sorted({match.group(1) for f in settings.ERROR_DIR.glob("*.json")
                          if (match := re.match(r"(T[0-4]-\d{3})", f.name))})
    parts = [f"no progress for {settings.STUCK_PASSES_FATAL} consecutive passes: "
             f"{len(blocked)} task(s) still blocked"]
    if quarantined:
        head = ", ".join(quarantined[:12]) + (", ..." if len(quarantined) > 12 else "")
        parts.append(f"quarantined in blackboard/error/: {head}")
    for task_id in list(blocked)[:3]:
        if task_id in waits:
            parts.append(f"e.g. {task_id} waits on: {waits[task_id][:150]}")
    parts.append("nothing the engine can do changes this: restore quarantined units with "
                 "--retry [ids], queue missing producers with python3 orchestrators/closure.py --emit, "
                 "or fix the blamed source; then relaunch to continue")
    return " | ".join(parts)




def _terminal_tree_report(gate=None):
    """A DETERMINISTIC verdict on the delivered bytes at every terminal exit (seed-002
    supervision gap: the run exited reporting board counts plus a CACHED 16:17 boot
    verdict while the final quarantine rollback had left dangling imports in production
    code). Board-driven by design (2026-11-13 rerun finding): a domain whose stage-4
    assembly NEVER ran is reported as `NEVER BOOTED`, not silently skipped - the old
    report scanned completed T4 records only and inherited the scheduling hole it was
    meant to expose. Zero agent sessions: the gate command is the deterministic boot;
    no stale build output can mask it because the command recompiles. Reporting only -
    this never raises and never requeues."""
    gate = gate or assembly.gate
    index = task_queue.load_index(include_error=True)
    slugs = sorted({str(t.get("project", "")) for t in index.values()
                    if isinstance(t, dict) and t.get("stage") == settings.TDD_STAGE
                    and t.get("project")})
    lines = []
    for slug in slugs:
        record = None
        for file in sorted(settings.COMPLETE_DIR.glob("T4-*.json")):
            try:
                rec = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(rec, dict) and rec.get("project") == slug:
                record = rec
                break
        if (ddd.ai_directive(slug) or {}).get("required") is True:
            lines.append(f"[tree   ] {slug}: AI BY DIRECTIVE - {ddd.ai_required(slug)[1]}"
                          + ("" if ddd.ai_spec_path(slug).is_file()
                             else " BUT NO SPEC ON DISK (the phase never landed)"))
        if ddd.security_waived(slug):
            lines.append(f"[tree   ] {slug}: SECURITY WAIVED by directive in the business description "
                         f"- {ddd._waiver_note(slug)[1]}"
                         + (" BUT A SPEC IS ON DISK (stale: it predates the waiver)"
                            if ddd.security_spec_path(slug).is_file() else ""))
        if record is None:
            lines.append(f"[tree   ] {slug}: RED - NEVER BOOTED: no completed stage-4 assembly "
                         "task exists for this domain - the boot gate never ran, so NOTHING "
                         "proves the application starts (relaunch the drain; assembly is "
                         "queued automatically once the scaffold exists)")
            continue
        try:
            ok, reason = gate(record)
        except Exception as exc:                       # reporting must not crash the exit
            ok, reason = False, f"terminal gate could not run: {exc}"
        lines.append(f"[tree   ] {slug}: "
                     + ("GREEN - the delivered tree compiles and boots" if ok
                        else f"RED - the DELIVERED TREE IS BROKEN: {str(reason)[:500]}"))
    return lines


def drain(args, backend):
    blocked_by_docker = docker_gate(args)
    if blocked_by_docker:
        print(f"[hint ] nothing ran: fix the environment and relaunch with --retry to restore "
              f"{len(list(settings.ERROR_DIR.glob('*.json')))} quarantined task(s)")
        return blocked_by_docker

    blocked = _closure_blockers()
    if blocked:
        print(f"[fatal] task closure: {blocked}")
        print("[hint ] generate the missing producers with: python3 orchestrators/closure.py --emit")
        if any(settings.ERROR_DIR.glob("*.json")):
            print("[hint ] a quarantined task may own the missing product: relaunch with "
                  "--retry [ids] to restore it (its payload often still needs only a gate)")
        return 2

    # Stage 4: the drain walks stages in ascending order, so a queued assembly task
    # structurally runs after every unit of the domain is implemented and evaluated.
    assembly.ensure_tasks()

    try:
        if args.watch:
            idle_passes = 0
            stuck_passes = 0
            exhausted_passes = 0
            while True:
                pass_started = time.monotonic()
                # Re-scheduled EVERY pass, not once at launch: on a fresh run the services/
                # folder does not exist until the stage-0 scaffold completes DURING the drain,
                # and an ensure_tasks() that only sees the pre-drain emptiness never queues
                # the boot gate - the run then drains to "done" having never booted anything
                # (observed live 2026-11-13 13:33: queue 0, 35 complete, zero T4 records).
                # ensure_tasks() is idempotent and reads directories only: zero sessions.
                assembly.ensure_tasks()
                processed, blocked = backend.run_pass(args)
                _pass_summary(pass_started, processed, blocked)
                if processed == 0:
                    idle_passes += 1
                    # Quiet board: the suite gate re-reads the DELIVERED tree, not the
                    # board statistics (2026-11-16: an evaluator and the assembler each
                    # broke a peer's frozen test AFTER the last wave; every later gate
                    # passed and the drain idled on a red tree). Memoized per tree
                    # fingerprint: a converged board costs file hashes, never builds.
                    if not any(settings.QUEUE_DIR.glob("*.json")):
                        if tdd_engine.terminal_suite_gate():
                            idle_passes = 0
                            continue
                    # Nothing was produced this pass: every unit is idle (empty queue)
                    # or deferred on work only the OPERATOR can unlock (--retry restore,
                    # a newly emitted producer, a source fix). A fixed 5s re-poll burns
                    # CPU and log volume (W3) and, with a blocked queue, used to run
                    # forever: measured 2,900+ zero-progress passes after one root
                    # quarantine reverted the domain's classes. Back off geometrically
                    # for BOTH shapes and stop loudly when a blocked drain repeats.
                    time.sleep(min(max(args.interval, 1) * 2 ** min(idle_passes, 4), 60))
                    if blocked:
                        stuck_passes += 1
                    elif (not any(settings.QUEUE_DIR.glob("*.json"))
                            and any(settings.ERROR_DIR.glob("*.json"))):
                        # BOARD EXHAUSTED (seed-002 rerun shape): the queue is empty ONLY
                        # because quarantines drained it - blocked is empty by definition,
                        # so the stuck breaker above could never see this. Silence here cost
                        # an operator afternoon: zero progress, zero bills, zero guidance.
                        exhausted_passes += 1
                        if exhausted_passes >= settings.STUCK_PASSES_FATAL:
                            restored = tdd_engine.autogrant_progressing()
                            if restored:
                                print(f"[grant ] auto-restored {len(restored)} advancing "
                                      f"quarantined unit(s): {', '.join(restored[:8])}")
                                exhausted_passes = 0
                                idle_passes = 0
                                continue
                            n_err = len(list(settings.ERROR_DIR.glob("*.json")))
                            for line in _terminal_tree_report():
                                print(line)
                            print(f"[exhausted] queue empty with {n_err} quarantined task(s): "
                                  "the drain cannot advance without the operator. Inspect with "
                                  "`python3 orchestrators/status.py`, fix the root failure, then "
                                  "relaunch with --retry.")
                            return 1
                    else:
                        stuck_passes = 0
                        exhausted_passes = 0
                    if stuck_passes >= settings.STUCK_PASSES_FATAL:
                        # Before declaring the block operator-only, auto-grant the
                        # quarantined units that are PROVABLY advancing (their last
                        # failure was never shown to a coder): the drain resumes with
                        # its bounded informed attempts instead of idling on launches.
                        restored = tdd_engine.autogrant_progressing()
                        if restored:
                            print(f"[grant ] auto-restored {len(restored)} advancing "
                                  f"quarantined unit(s): {', '.join(restored[:8])}")
                            stuck_passes = 0
                            idle_passes = 0
                            continue
                        raise tdd_engine.FatalPipeline(_stuck_report(blocked))
                else:
                    idle_passes = 0
                    stuck_passes = 0
                    time.sleep(args.interval)
        processed, blocked = backend.run_pass(args)
        # Same root cause as the watch-loop reschedule: on a single-pass run the services/
        # folder appears DURING the pass, so the one pre-drain ensure_tasks() could not have
        # seen it. Schedule now (idempotent, zero sessions) and, if the boot gate is fresh
        # work, drain it - a run that "finished" without ever booting the app is a lie.
        before = set(settings.QUEUE_DIR.glob("T4-*.json"))
        assembly.ensure_tasks()
        if set(settings.QUEUE_DIR.glob("T4-*.json")) - before:
            extra, blocked = backend.run_pass(args)
            processed += extra
    except KeyboardInterrupt:
        return 130
    except tdd_engine.FatalPipeline as fatal:
        print(f"[fatal] {fatal}")
        return 2
    if blocked:
        print(f"[blocked] {', '.join(blocked)}")
        return 1

    if args.verify != "none":
        for slug in ddd.database_slugs():
            ok, reason = verification.verify_project(workspace.project_root_for(slug),
                                                     args.verify, args.verify_timeout)
            if not ok:
                print(f"[fatal] {slug}: {reason}")
                return 1
            print(f"[verify] {slug} passes {args.verify}")
    print(f"[ok] processed {processed} task(s)")
    return 0
    return 0
