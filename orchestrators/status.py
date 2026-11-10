"""Read-only board status: the cumulative view that survives process restarts.

    python3 orchestrators/status.py

Shows queue/complete/quarantine counters, the most recent completions, and for each
quarantined unit its attempt-ledger state (budget left, grants used, whether its last
failure has been shown to a coder yet) - the exact questions the drain answers when
relaunched, so the operator sees WHY the board is where it is without reading a log.
"""
import json
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


def main():
    show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
