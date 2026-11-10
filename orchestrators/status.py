"""Read-only board status: the cumulative view that survives process restarts.

    python3 orchestrators/status.py

Shows queue/complete/quarantine counters, the most recent completions, and for each
quarantined unit its attempt-ledger state (budget left, grants used, whether its last
failure has been shown to a coder yet) - the exact questions the drain answers when
relaunched, so the operator sees WHY the board is where it is without reading a log.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import attempt_ledger
import settings


def _records(folder):
    out = []
    try:
        for file in sorted(folder.glob("*.json"), key=lambda f: f.stat().st_mtime):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and data.get("id"):
                out.append((file, data))
    except OSError:
        pass
    return out


def _age(path):
    try:
        return int(time.time() - path.stat().st_mtime)
    except OSError:
        return -1


def _ledger_note(task_id):
    ledger = attempt_ledger.read(task_id)
    if not isinstance(ledger, dict) or not ledger:
        return "no ledger (never charged)"
    consumed = int(ledger.get("consumed") or 0)
    grants = int(ledger.get("grants") or 0)
    shown = ledger.get("fed") == ledger.get("signature") and ledger.get("signature")
    budget = max(settings.MAX_TDD_RETRIES - consumed, 0)
    if budget or (grants < settings.MAX_INFORMED_GRANTS and not shown):
        state = "advance-ready (restore will attempt)"
    elif grants >= settings.MAX_INFORMED_GRANTS:
        state = "LOCKED (grants exhausted; needs fresh contract or operator reset)"
    else:
        state = "repeat-shown (replay closes it at zero sessions)"
    return f"consumed {consumed}/3 grants {grants}/{settings.MAX_INFORMED_GRANTS} " \
           f"last-failure-shown={'yes' if shown else 'no'} -> {state}"


def show():
    queue, complete, error = (_records(settings.QUEUE_DIR),
                              _records(settings.COMPLETE_DIR),
                              _records(settings.ERROR_DIR))
    print(f"board at {time.strftime('%Y-%m-%d %H:%M:%S')}  root={settings.ROOT}")
    print(f"  queue {len(queue)}   complete {len(complete)}   quarantined {len(error)}")
    by_stage = {}
    for _, task in queue:
        by_stage[str(task.get("stage"))] = by_stage.get(str(task.get("stage")), 0) + 1
    if by_stage:
        print("  queue by stage: " + "  ".join(f"T{k}:{v}" for k, v in sorted(by_stage.items())))
    if complete:
        print("  most recent completions:")
        for file, task in complete[-5:]:
            print(f"    {task['id']:<10} {_age(file):>7}s ago  {str(task.get('path', ''))[-60:]}")
    if error:
        print("  quarantined units (ledger state = what a restore/resume will do):")
        for file, task in error[-12:]:
            print(f"    {task['id']:<10} {_age(file):>7}s ago  {_ledger_note(task['id'])}")
            reason = str(task.get("error") or "")[:110]
            if reason:
                print(f"             reason: {reason}")
    try:
        pids = subprocess.run(["pgrep", "-f", "orchestrator_git"], capture_output=True,
                              text=True, timeout=5).stdout.split()
        print("  orchestrator processes: " + (", ".join(pids) if pids else "none running"))
    except Exception:
        pass
    _token_rollup()


def _token_rollup():
    """Session token totals since the current process (or the last hour): the burn
    question answered continuously instead of by post-mortem. Reads the backend's own
    session-state event files; every field is optional - absence is reported, never guessed."""
    import datetime
    import glob
    import time as _time
    def gint(u, *keys):
        for k in keys:
            try:
                v = int(u.get(k) or 0)
            except (TypeError, ValueError):
                v = 0
            if v:
                return v
        return 0
    cutoff = None
    try:
        out = subprocess.run(["ps", "-eo", "pid,lstart,cmd"], capture_output=True,
                             text=True, timeout=5).stdout
        for line in out.splitlines():
            if "orchestrator_github" in line and "grep" not in line:
                stamp = " ".join(line.split()[1:6])
                cutoff = datetime.datetime.strptime(stamp, "%a %b %d %H:%M:%S %Y").timestamp()
                break
    except Exception:
        pass
    if cutoff is None:
        cutoff = _time.time() - 3600
    tin = tout = n = 0
    worst = (0, 0.0)
    for f in glob.glob(os.path.expanduser("~/.copilot/session-state/*/events.jsonl")):
        try:
            m = os.path.getmtime(f)
        except OSError:
            continue
        if m < cutoff:
            continue
        s_in = s_out = 0
        try:
            for line in open(f, errors="ignore"):
                if "usage" not in line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                srcs = [s for s in ((e.get("data") if isinstance(e.get("data"), dict) else {}), e)
                        if isinstance(s, dict)]
                for src in srcs:
                    u = src.get("usage") or src.get("tokens")
                    if isinstance(u, dict):
                        s_in += gint(u, "input_tokens", "inputTokens", "prompt_tokens")
                        s_out += gint(u, "output_tokens", "outputTokens", "completion_tokens")
        except OSError:
            continue
        if s_in or s_out:
            n += 1
            tin += s_in
            tout += s_out
            if s_in > worst[0]:
                worst = (s_in, m)
    done = (sum(1 for _ in settings.COMPLETE_DIR.glob("T?-*.json"))
            if settings.COMPLETE_DIR.is_dir() else 0)
    print(f"  tokens since launch: sessions={n} input={tin:,} output={tout:,}"
          + (f" | per completed unit={tin // done:,}" if done else ""))
    if worst[0]:
        print("  largest session input: " + f"{worst[0]:,}"
              " at " + datetime.datetime.fromtimestamp(worst[1]).strftime("%H:%M"))


def main():
    show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
