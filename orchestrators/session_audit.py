"""Session audit: what each agent session really cost.

Every assistant turn re-sends the whole transcript, so the price of a session is driven by its
number of tool calls, not by the length of its prompt. This tool reads the local Copilot CLI
session records and reports, per agent, the turns, the tool calls, the tokens and the calls that
left the agent's own inputs (skill folder listings, orchestrator or AST-tool source reads, other
tasks' records, `git`).

Usage:
  python3 orchestrators/session_audit.py                 # last 12 hours, worst first
  python3 orchestrators/session_audit.py --since-hours 3 --budget-report
  python3 orchestrators/session_audit.py --json
"""
import argparse
import collections
import glob
import json
import os
import re
import time
from pathlib import Path

SESSION_GLOB = "~/.copilot/session-state/*/events.jsonl"

BUDGETS = {
    "discovery": 10, "mapping": 10,
    # 2026-11-20 architect split: "architect" stays the label of HISTORIC monolith
    # sessions (13 was their per-phase shape); the two new carriers classify apart.
    "architect": 13, "strategy": 12, "planner": 12, "planner_repair": 12,
    "database": 10, "security": 8, "performance": 8, "ai": 8,
    "container": 10, "tester": 8, "coder": 6, "evaluator": 12, "assembly": 12,
}

PATTERNS = (
    # verbs must be whole words at a command position: ".opencode/skills/run-test-tool.py"
    # (required tool paths) must not read as a folder listing through the "ls" inside "skills".
    ("skills_folder_listing", re.compile(r"(?:^|[\s;&|])(ls|find|glob|tree|echo \*)\s[^\n]*skills/?")),
    ("tooling_source_read", re.compile(r"(?:^|[\s;&|])(grep|cat|sed|head|tail|awk)\s[^\n]*(orchestrators/|ast_tools/|ast_weaver_tools/|code-weaver-dispatcher|ast-dispatcher)")),
    ("other_task_record", re.compile(r"blackboard/(queue|complete|error)/T[0-3]-")),
    # board-wide listings: `ls blackboard/queue`, `ls blackboard/coder-changes` etc. were
    # measured in tester and batch coder sessions; the enumeration re-sends on every
    # later turn. Only the folder as a DIRECT verb argument counts (flags allowed) -
    # a single-file read of the unit's own record is legitimate input, not a listing.
    # (A `find . -path '*coder-changes*'` dodge stays under this radar: accepted - the
    # audit is a reporting aid, the engine's attempt ledger is the enforcement.)
    ("board_bulk_read", re.compile(
        r"(?:^|[\s;&|])(?:ls|find|tree|du)\s+(?:-\S+\s+)*(?:\S*/)?(?:queue|complete|error|coder-changes|ast-context|red-phase|attempts)(?![-\w])")),
    ("git", re.compile(r"\bgit (status|diff|log|show)\b")),
    ("agent_scratch", re.compile(r"\.copilot/session-state")),
    ("src_full_read", re.compile(r"\bcat [^\n]*src/(main|test)/")),
    ("writer_call", re.compile(r"write-(coder-changes|red-phase|evaluate-results|architect-file)\.py")),
)

UNIT_RE = re.compile(r"\bT([0-4])-(\d{3})\b")
BATCH_UNITS = re.compile(r"BATCH MODE.*?(\d+) tasks below", re.S)
VIOLATIONS = ("skills_folder_listing", "tooling_source_read", "other_task_record",
              "board_bulk_read", "git", "agent_scratch", "src_full_read")


ROLE_MARKERS = (
    ("discovery", "you are the domain boundary discovery specialist"),
    ("mapping", "you are the domain context mapping specialist"),
    ("database", "you are the blackboard database architect"),
    ("security", "you are the blackboard security architect"),
    ("performance", "you are the blackboard performance architect"),
    ("ai", "you are the blackboard ai architect"),
    # 2026-11-20 architect split. Order matters: the repair brief is the more specific
    # prefix of the planner phrase, so it must be tested first.
    ("planner_repair", "you are the blackboard planning architect for this repository. repair"),
    ("strategy", "you are the blackboard strategy architect"),
    ("planner", "you are the blackboard planning architect"),
    # the retired monolith's phrase: kept so HISTORIC sessions still classify as architect
    ("architect", "you are the blackboard architect"),
    ("coder", "emit the payload of this unit"),
    ("coder", "create the implementation at"),
    ("tester", "create the test at"),
    ("evaluator", "inspect the implementation at"),
    ("assembly", "boot the generated application"),
    ("container", "generate the project root and scaffold"),
)


def classify(prompt_text):
    """Agent role from the session prompt: batch coder, stage agent, or a planning phase."""
    lowered = prompt_text.lower()
    unit_match = UNIT_RE.search(prompt_text)
    unit = unit_match.group(0) if unit_match else "-"
    if "BATCH MODE" in prompt_text:
        units = {match.group(0) for match in UNIT_RE.finditer(prompt_text)}
        declared = BATCH_UNITS.search(prompt_text)
        count = int(declared.group(1)) if declared else len(units)
        return "coder", f"batch x{max(count, len(units))}"
    for role, marker in ROLE_MARKERS:
        if marker in lowered:
            return role, unit
    return "other", unit


def calls_of_session(events_path):
    """Exact number of tool calls recorded in one session file."""
    calls = 0
    for line in open(events_path, encoding="utf-8", errors="ignore"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "tool.execution_start":
            calls += 1
    return calls


def latest_calls_since(start_ts, marker=None):
    """Tool calls of the session started at/after `start_ts`, read from the CLI's own records.

    The Copilot JSON stream does not have to expose tool events, so the orchestrator measures
    the budget from these records: the newest session file touched after the launch, optionally
    restricted to a prompt containing `marker`. Returns None when nothing matches yet.
    """
    candidates = []
    for events_path in glob.glob(os.path.expanduser(SESSION_GLOB)):
        try:
            modified = Path(events_path).stat().st_mtime
        except OSError:
            continue
        if modified < start_ts - 2:
            continue
        if marker:
            yaml_path = Path(events_path).with_name("workspace.yaml")
            try:
                if marker not in yaml_path.read_text(encoding="utf-8", errors="ignore"):
                    continue
            except OSError:
                continue
        candidates.append((modified, events_path))
    if not candidates:
        return None
    return calls_of_session(max(candidates)[1])


def read_session(events_path):
    """Aggregate one session record into counts, tokens and scope violations."""
    tools = collections.Counter()
    violations = collections.Counter()
    turns = calls = in_tok = out_tok = 0
    for line in open(events_path, encoding="utf-8", errors="ignore"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        data = event.get("data") or {}
        if kind == "tool.execution_start":
            calls += 1
            name = str(data.get("toolName"))
            tools[name] += 1
            blob = json.dumps(data.get("arguments") or {})
            for label, pattern in PATTERNS:
                if pattern.search(blob):
                    violations[label] += 1
        elif kind == "assistant.turn_start":
            turns += 1
        elif kind == "session.usage_record":
            usage = data.get("usage") or {}
            in_tok += usage.get("inputTokens", 0) or 0
            out_tok += usage.get("outputTokens", 0) or 0
    return {"turns": turns, "calls": calls, "tools": dict(tools),
            "violations": dict(violations), "in": in_tok, "out": out_tok}


def first_user_message(events_path):
    """The session's real prompt from its event record.

    workspace.yaml truncates the prompt, so a BATCH MODE session loses its marker there and
    gets audited against the single-task budget: an artifact that cries wolf. The events file
    holds the full first user message; classify from that when available.
    """
    for line in open(events_path, encoding="utf-8", errors="ignore"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "user.message":
            content = (event.get("data") or {}).get("content")
            if isinstance(content, str) and content.strip():
                return content
    return ""


def collect(since_hours):
    cutoff = time.time() - since_hours * 3600
    rows = []
    for events_path in glob.glob(os.path.expanduser(SESSION_GLOB)):
        if not Path(events_path).is_file() or Path(events_path).stat().st_mtime < cutoff:
            continue
        prompt = first_user_message(events_path)
        if not prompt:
            yaml_path = Path(events_path).with_name("workspace.yaml")
            prompt = yaml_path.read_text(encoding="utf-8", errors="ignore") if yaml_path.is_file() else ""
        role, unit = classify(prompt)
        stats = read_session(events_path)
        if stats["calls"] or stats["turns"]:
            rows.append({"role": role, "unit": unit, "session": Path(events_path).parent.name[:8],
                         "modified": time.strftime("%H:%M", time.localtime(Path(events_path).stat().st_mtime)),
                         **stats})
    rows.sort(key=lambda row: -row["in"])
    return rows


def budget_of(role, unit="-"):
    """Allowed tool calls for one session; a coder batch shares 4 + 3 per unit."""
    if role == "coder" and unit.startswith("batch x"):
        try:
            units = int(unit.split("x")[1])
        except (TypeError, ValueError):
            return BUDGETS["coder"]
        if units > 1:
            return 4 + 3 * units
        return BUDGETS["coder"]
    return BUDGETS.get(role)


def violations_of(row):
    return {key: value for key, value in row["violations"].items() if key in VIOLATIONS}


def report(rows, show_budget):
    header = f"{'role':<10} {'unit':<8} {'time':<6} {'turn':>4} {'call':>4} {'input':>9} {'output':>7} {'budget':>7}  violations"
    print(header)
    print("-" * len(header))
    over = 0
    for row in rows:
        limit = budget_of(row["role"], row["unit"])
        tag = "-" if limit is None else ("OVER" if row["calls"] > limit else "ok")
        if tag == "OVER":
            over += 1
        print(f"{row['role']:<10} {row['unit']:<8} {row['modified']:<6} {row['turns']:>4} "
              f"{row['calls']:>4} {row['in']:>9} {row['out']:>7} {str(limit or '-') + tag:>7}  "
              f"{violations_of(row) or ''}")
    total_in = sum(row["in"] for row in rows)
    print("-" * len(header))
    print(f"sessions={len(rows)} over_budget={over} turns={sum(r['turns'] for r in rows)} "
          f"calls={sum(r['calls'] for r in rows)} input={total_in} "
          f"output={sum(r['out'] for r in rows)} "
          f"input_per_turn={int(total_in / max(1, sum(r['turns'] for r in rows)))}")
    merged = collections.Counter()
    for row in rows:
        merged.update(violations_of(row))
    if merged:
        print("scope violations:", dict(merged))
    if show_budget:
        print("\nbudgets (tool calls per session):", BUDGETS)


CHARS_PER_TOKEN = 3.7   # calibrated against the records' own token counts on tool payloads


def burn_report(since_hours, role="architect", top=20):
    """What inside a session cost what - item tokens weighted by the turns that re-sent them.

    `report` says what a run cost; it cannot say WHY. Every tool result enters the transcript and is
    then re-sent on all later turns, so an item's true price is its size x its residence: a 5k-token
    skill loaded on turn 1 of a 12-turn session costs ~60k, the same skill loaded on turn 10 costs
    10k. Output is listed separately because it is the expensive class and the one a plan-phase
    change can actually move. Run this after any prompt/skill/emission-shape change: re-auditing the
    same sessions is the only evidence that a token fix worked.
    """
    start_ts = time.time() - since_hours * 3600
    items = collections.defaultdict(lambda: [0.0, 0.0, 0])
    totals = collections.Counter()
    for path in sorted(glob.glob(os.path.expanduser(SESSION_GLOB))):
        try:
            if os.path.getmtime(path) < start_ts:
                continue
            prompt = first_user_message(path) or ""
        except OSError:
            continue
        got, _unit = classify(prompt)
        if got != role:
            continue
        events = []
        for line in open(path, encoding="utf-8", errors="ignore"):
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
        events.sort(key=lambda e: e.get("timestamp", ""))
        usage = [((e.get("data") or {}).get("usage") or {}) for e in events
                 if e.get("type") == "session.usage_record"]
        if not usage:
            continue
        turns = len(usage)
        totals["sessions"] += 1
        totals["turns"] += turns
        totals["in"] += sum(u.get("inputTokens", 0) or 0 for u in usage)
        totals["out"] += sum(u.get("outputTokens", 0) or 0 for u in usage)
        totals["cache_read"] += sum(u.get("cacheReadTokens", 0) or 0 for u in usage)
        totals["peak_turn"] = max(totals["peak_turn"],
                                  max(u.get("outputTokens", 0) or 0 for u in usage))
        open_calls, pending, turn = {}, [], 0
        for event in events:
            kind = event.get("type")
            data = event.get("data") or {}
            if kind == "assistant.turn_start":
                turn += 1
            elif kind == "tool.execution_start":
                args = data.get("arguments") or {}
                name = str(data.get("toolName"))
                if name in ("view", "read", "create", "edit", "write", "str_replace"):
                    tail = Path(str(args.get("path", "?")))
                    label = f"{name} {tail.parent.name}/{tail.name}" if tail.name else name
                elif name == "bash":
                    label = "bash " + re.sub(r"\s+", " ", str(args.get("command", "")))[:58]
                elif name == "glob":
                    label = f"glob {args.get('pattern', '')}"
                else:
                    label = name
                item = {"label": label[:76], "turn": turn,
                        "chars": len(json.dumps(args, default=str))}
                open_calls[data.get("toolCallId")] = item
                pending.append(item)
            elif kind == "tool.execution_complete":
                item = open_calls.get(data.get("toolCallId"))
                if item:
                    result = data.get("result")
                    item["chars"] += len(json.dumps(result, default=str)) if result is not None else 0
        for item in pending:
            tok = item["chars"] / CHARS_PER_TOKEN
            residence = max(1, turns - item["turn"] + 1)
            agg = items[item["label"]]
            agg[0] += tok * residence
            agg[1] += tok
            agg[2] += 1
    uncached = totals["in"] - totals["cache_read"]
    print(f"BURN REPORT  role={role}  window={since_hours:g}h  sessions={totals['sessions']}  "
          f"turns={totals['turns']}")
    print(f"  input {totals['in']:,} tok ({totals['cache_read']:,} cache-read = "
          f"{totals['cache_read'] / max(totals['in'], 1):.0%}, {uncached:,} re-priced)  "
          f"output {totals['out']:,} tok  worst single-turn output {totals['peak_turn']:,}")
    print(f"  {'carried':>12} {'raw':>9} {'n':>4}  item  (size x turns that re-sent it)")
    for label, (cost, raw, n) in sorted(items.items(), key=lambda kv: -kv[1][0])[:top]:
        print(f"  {cost:>12,.0f} {raw:>9,.0f} {n:>4}  {label}")
    if not items:
        print("   (no sessions of this role in the window)")
    print("  read: skills and file reads are paid AGAIN on every later turn - load only the phase's"
          " own,\n  at the paths the profile gives; output is the expensive class, so a smaller"
          " emission unit and an\n  edit-not-rewrite remedy move the number that matters.")


def main():
    parser = argparse.ArgumentParser(description="Audit agent session cost from the Copilot CLI records.")
    parser.add_argument("--since-hours", type=float, default=12, help="look back this far (default 12)")
    parser.add_argument("--limit", type=int, default=0, help="show at most N sessions (0 = all)")
    parser.add_argument("--budget-report", action="store_true", help="print the configured budgets")
    parser.add_argument("--json", action="store_true", help="emit machine-readable rows")
    parser.add_argument("--burn-report", action="store_true",
                        help="per-item token cost weighted by the turns that re-sent it (why a "
                             "session cost what it cost)")
    parser.add_argument("--role", default="architect",
                        help="which agent to attribute (default: architect; used with "
                             "--burn-report). After the 2026-11-20 split the plan roles are "
                             "'strategy' (phase 1) and 'planner'/'planner_repair' (phase 2); "
                             "'architect' still matches HISTORIC monolith sessions.)")
    args = parser.parse_args()

    if args.burn_report:
        burn_report(args.since_hours, args.role)
        return
    rows = collect(args.since_hours)
    if args.limit:
        rows = rows[:args.limit]
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print(f"no agent sessions found in the last {args.since_hours:g}h under "
              f"{os.path.expanduser(os.path.dirname(SESSION_GLOB))}")
        return 1
    report(rows, args.budget_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
