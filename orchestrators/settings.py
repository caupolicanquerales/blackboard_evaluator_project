"""Static layout and pipeline vocabulary shared by every orchestrator module.

Roots and script locations derive from this file's position: the repository root
is one level above the ``orchestrators/`` folder. Backend and entry scripts import
this module as a namespace (``settings.ROOT``) so tests can patch values at runtime.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLACKBOARD = ROOT / "blackboard"
QUEUE_DIR = BLACKBOARD / "queue"
COMPLETE_DIR = BLACKBOARD / "complete"
ERROR_DIR = BLACKBOARD / "error"
PROJECTS_DIR = ROOT / "projects"
SEED_DIR = ROOT / "seed"
DOMAIN_DIR = BLACKBOARD / "domain"
CONTEXT_MAP_DIR = BLACKBOARD / "context-map"

SKILLS_DIR = ROOT / ".opencode" / "skills"
READER_SCRIPT = SKILLS_DIR / "read-write-file-ddd" / "reader-file" / "scripts" / "reader_file.py"
AST_DISPATCHER = SKILLS_DIR / "ast-dispatcher" / "ast-dispatcher.py"
CODE_WEAVER_DISPATCHER = SKILLS_DIR / "code-weaver-dispatcher" / "code-weaver-dispatcher.py"
RUN_TEST_TOOL = SKILLS_DIR / "tester-framework" / "run-test-tool.py"
RED_PHASE_WRITER = SKILLS_DIR / "read-write-file-ddd" / "writer-red-phase" / "write-red-phase.py"
CODER_WRITER = SKILLS_DIR / "read-write-file-ddd" / "writer-coder-changes" / "write-coder-changes.py"
RED_PHASE_DIR = BLACKBOARD / "red-phase"
GATE_CACHE_DIR = BLACKBOARD / "gate-cache"
AST_CONTEXT_DIR = BLACKBOARD / "ast-context"
# Cross-pass TDD attempt memory (blackboard/attempts/<task-id>.json): the number of
# coder sessions a unit may still be billed for. See orchestrators/attempt_ledger.py.
ATTEMPTS_DIR = BLACKBOARD / "attempts"

DISCOVERY_AGENT = "domain-boundary-discovery-specialist"
MAPPING_AGENT = "domain-context-mapping-specialist"
# 2026-11-20 architect split: the monolithic planning agent became two carriers so each
# phase starts with a clean, small context window. Phase 1 (strategy) and phase 2 (planner)
# share no prompt bytes; the planner runs ONE session per bounded context.
ARCHITECT_STRATEGY_AGENT = "agent-strategy-architect"
ARCHITECT_PLANNER_AGENT = "agent-planner-architect"
DATABASE_AGENT = "agent-database-architect"
SECURITY_AGENT = "agent-security-architect"
PERFORMANCE_AGENT = "agent-performance-architect"
AI_AGENT = "agent-ai-architect"

STAGE_AGENTS = {
    0: "agent-container",
    1: "agent-tester",
    2: "agent-coder",
    3: "agent-evaluator",
    4: "agent-assembly",
}
STAGE_KINDS = {
    0: ("bootstrap",),
    1: ("test",),
    2: ("code",),
    3: ("refactor",),
    4: ("assembly",),
}

# Stage-0 family export markers (S16's lesson: families are keyed by EXPORT marker, never
# by path shape). task_queue re-exports these names; both trees read one source.
SCAFFOLD_EXPORT = "project_scaffold"
BUILD_MANIFEST_EXPORT = "build-manifest"
ALLOWED_AGENTS = tuple(STAGE_AGENTS.values())

# Tool calls per agent session. Every turn re-sends the whole transcript, so a session's cost is
# its number of calls: these caps are stated in the prompt and checked again when the session ends.
AGENT_CALL_BUDGETS = {
    STAGE_AGENTS[0]: 10,
    STAGE_AGENTS[1]: 8,
    STAGE_AGENTS[2]: 6,
    STAGE_AGENTS[3]: 12,
    STAGE_AGENTS[4]: 12,
    ARCHITECT_STRATEGY_AGENT: 12,  # phase 1: read 2 reports, write 1 strategy, emit 1 scaffold
                                   # task; the three strategy skills load once. The old 15 was
                                   # sized for BOTH phases (2026-11-19); the split moves phase 2
                                   # bytes out of this context entirely.
    ARCHITECT_PLANNER_AGENT: 16,   # per BOUNDED CONTEXT session: strategy + digest + symbol
                                   # table reads, one draft write, one lint/emit. The mapping
                                   # tables load ONLY when the digest lists unmapped_duties -
                                   # the matched rows ride the digest itself (2026-11-20).
                                   # 12 -> 16 (2026-11-24 seed-002, measured twice): a LAW-ABIDING
                                   # session costs 7 reads + bulk create + rewrite + ~3 lints +
                                   # a per-object fix pass for a 68-object draft = 25 calls; the
                                   # compliant draft hit the 24-cap (twice: run 1's second context,
                                   # run 2's single context) and the kill landed AFTER the work
                                   # was done. The budget was calibrated for ~10 units; this
                                   # seed's context carries every duty in one file. 16 keeps the
                                   # watchdog's teeth (cap 32) with room for two lint rounds.
    DATABASE_AGENT: 12,    # 14 was needed ONLY because the profile had no exact skill
                           # paths and the agent globbed tech-stack/** (A4, 2026-11-18);
                           # with paths given, 12 is the honest ceiling and it is pinned
    SECURITY_AGENT: 8,
    PERFORMANCE_AGENT: 8,
    AI_AGENT: 8,
    DISCOVERY_AGENT: 10,
    MAPPING_AGENT: 10,
}
CODER_BATCH_FIRST_CALLS = 4
CODER_BATCH_CALLS_PER_UNIT = 3
# A tester batch shares the cold start (skill, manifest) and pays per unit: write test,
# run-test-tool red (+ one wrong-reason fix), write the red-phase record. Each unit's red
# is still validated independently at close-out, so a thin batch red degrades to a
# per-task rerun rather than a wrong freeze.
TESTER_BATCH_FIRST_CALLS = 3
TESTER_BATCH_CALLS_PER_UNIT = 4


PROFILE_REQUIRED_KEYS = {".github": ("name", "description", "tools"),
                         ".opencode": ("description", "permission")}


def agent_profiles_problems(root=None):
    """Launch preflight (2026-11-20 live-line stop): the Copilot CLI SILENTLY skips any
    agent profile whose YAML header does not parse - the failure then surfaces as
    'No such agent' mid-run, only at the first spawn of that carrier, after every prior
    planning session was already billed. The engine therefore parses both profile trees
    itself before phase 0 starts: a header must be a mapping with its backend's required
    keys. When PyYAML is absent the colon heuristic below catches the known poison shape
    (an unquoted 'x: y' sequence inside a value line)."""
    base = Path(root) if root else ROOT
    try:
        import yaml
    except ImportError:
        yaml = None
    problems = []
    for tree in (".github", ".opencode"):
        folder = base / tree / "agents"
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---\n"):
                problems.append(f"{path}: no frontmatter header")
                continue
            parts = text.split("---\n", 2)
            if len(parts) < 3:
                problems.append(f"{path}: unterminated frontmatter")
                continue
            header = parts[1]
            fields = {}
            if yaml is not None:
                try:
                    parsed = yaml.safe_load(header)
                except Exception as exc:
                    problems.append(f"{path}: header is not parseable YAML: {str(exc)[:120]}")
                    continue
                if not isinstance(parsed, dict):
                    problems.append(f"{path}: header is not a mapping")
                    continue
                fields = parsed
            else:
                for line in header.splitlines():
                    if not line.strip() or (line[:1] in (" ", "\t")):
                        continue
                    key, sep, value = line.partition(":")
                    if not sep:
                        problems.append(f"{path}: header line without a key: {line[:60]!r}")
                        continue
                    value = value.strip()
                    if ": " in value and not value.startswith(('"', "'", "[")):
                        problems.append(
                            f"{path}: unquoted ': ' inside {key.strip()!r} - the CLI's YAML "
                            "loader will reject the header")
                    fields[key.strip()] = value
            for key in PROFILE_REQUIRED_KEYS[tree]:
                if key not in fields:
                    problems.append(f"{path}: header lacks the required key {key!r}")
    return problems


def call_budget(target_agent, units=1):
    """Tool calls allowed to one session of `target_agent`; a coder batch shares more."""
    budget = AGENT_CALL_BUDGETS.get(target_agent)
    if budget is None:
        return None
    if target_agent == STAGE_AGENTS[TESTER_STAGE] and units > 1:
        return TESTER_BATCH_FIRST_CALLS + TESTER_BATCH_CALLS_PER_UNIT * units
    if target_agent == STAGE_AGENTS[TDD_STAGE] and units > 1:
        return CODER_BATCH_FIRST_CALLS + CODER_BATCH_CALLS_PER_UNIT * units
    return budget


# A session streaming past this multiple of its budget is KILLED mid-run: every extra turn
# re-sends the whole transcript, so an overshooting agent is not a warning, it is the burn.
# Degrades to the after-the-fact warning when the CLI stream exposes no tool events.
BUDGET_HARD_KILL_FACTOR = 2.0
BUDGET_HARD_KILL_SLACK = 4

REQUIRED_KEYS = (
    "id",
    "targetAgent",
    "stage",
    "dependsOn",
    "path",
    "kind",
    "layer",
    "feature",
    "export",
    "intent",
    "project",
)
# Optional structural key: the API contract table the architect must emit for planning
# stages (see validate): package, implements, dependencies pinned to producer task ids,
# and the boundary methods with their exact parameter/return spellings. Testers write
# assertions ONLY against this table; boards recorded before it existed remain readable.
OPTIONAL_KEYS = ("ast_hints", "observability")
AST_HINT_KEYS = ("package", "implements", "dependencies", "methods")
# THE SHARED-LITERAL VOCABULARY (rule (z), 2026-11-19 - R1/R2 roots): meter names and
# request-path routes are literals used by >= 2 units (owner, consumers, the frozen test
# pair). While they lived ONLY in intent prose, two frozen contracts could spell one
# meter or one route differently and every per-unit gate stayed green - a coder then died
# 3/3 on a pair no payload can satisfy. The machine fields below are their only lawful
# home; the emit gate joins them across units (owner per literal, consumers verbatim,
# prose spelled into the table). Optional keys: boards recorded before they existed stay
# readable (subset validation, planning-time-only demands).
AST_HINT_OPTIONAL_KEYS = ("meters", "routes", "config")
METER_DUTIES = ("owns", "uses")     # owns = this unit registers the name (exactly one per name)
ROUTE_DUTIES = ("serves", "uses")   # serves = this unit answers the (method, path) (exactly one per pair)
# z5 (2026-11-19, R4): a property path is a shared literal too. The seed-002 board carried
# one prefix in two incompatible shapes - the binding record declared `devices` as a LIST of
# (id, secret-hash, scope) entries while the config unit's contract seeded
# `devices.secret-hash` as a SCALAR - and no document or gate could see the pair until two
# frozen tests paid for it. kind is the shape; fields lists the element/entry keys of a
# structured path (kebab or camel - relaxed binding canonicalizes both). The join: units
# table the SAME path with the SAME kind and fields, a value/map child of a list path is an
# impossible shape, and once any unit tables a path, the config-artifact unit tables every
# path its document seeds.
CONFIG_KINDS = ("value", "list", "map")
# The step-log CLAIM surface (2026-11-13): a task record that owns planned observability
# step logs declares them verbatim here; emit refuses strategies whose entries have no
# owner. Optional on the schema: legacy boards carry neither key nor claim, and the
# attempt-ledger digest ignores absent fields (continuity preserved).
PROMPT_KEYS = ("id", "path", "kind", "layer", "feature", "export", "intent", "dependsOn",
               "project", "ast_hints", "observability")
PROJECTS_SUBDIR = "services"
LAYERS = ("root", "domain", "application", "infrastructure", "interface", "shared", "features")
# The build manifest of each supported stack. A stage-0 bootstrap task whose path names one of
# these files is a BUILD-MANIFEST duty: it rewrites the classpath the red-phase gap check reads.
# The resume gate defers such a project's fatal to the per-task close-out, which re-checks AFTER
# stage 0 ran (heap order) - fataling on a gap the duty itself would fill is a deadlock
# (2026-11-18 live: the manifest duty the security mapping owed could be emitted, but the gate
# read the pre-duty pom on every relaunch and died before the drain could run it).
BUILD_FILE_NAMES = ("pom.xml", "build.gradle", "build.gradle.kts", "package.json")
ID_PATTERN = re.compile(r"^T([0-4])-(\d{3})$")

VERIFY_MODES = ("none", "typecheck", "build")
MAX_TDD_RETRIES = 3
# A watch pass that bills nothing and completes nothing while tasks stay blocked is
# provably waiting on events only the OPERATOR can create (a --retry restore, a new
# emitted producer, a source fix): the drain's own outcomes cannot change it. After
# this many consecutive zero-progress blocked passes the watch loop stops loudly with
# the remedy instead of re-running skip-agent + cached verdicts forever (measured:
# 2,900+ passes after one root quarantine + cascade reverted the domain's classes).
STUCK_PASSES_FATAL = 4
# A quarantined unit whose LAST recorded failure was never shown to a coder session
# (signature != fed) can still advance: the watch loop auto-restores such units for
# one informed attempt per restore, capped in total per contract by this grant count
# (the ledger clears them on green; contract moves are budgeted separately). Units
# that only repeat an already-shown failure stay quarantined: the replay closes them
# at zero sessions, and nothing here re-arms a retry storm (§13.1 cap holds).
MAX_INFORMED_GRANTS = 3
# Weaver TOOL rejections bounce back to the coder free of charge, capped so a
# tool-vs-agent disagreement cannot spin unbounded sessions.
MAX_WEAVE_REJECT_BOUNCES = 2
TDD_STAGE = 2
TESTER_STAGE = 1
EVALUATOR_STAGE = 3
ASSEMBLY_STAGE = 4
AST_DISPATCH_TIMEOUT = 1800
WEAVER_DISPATCH_TIMEOUT = 1800
TEST_GATE_TIMEOUT = 600
# Whole-module wave build: one shared suite run adjudicates every unit's green gate.
WAVE_GATE_TIMEOUT = 1200
# A batch session writes one payload per task, so it needs a budget that scales with the batch.
BATCH_TIMEOUT_PER_TASK = 240


def batch_timeout(single_timeout, count):
    """Seconds allowed for one agent session that carries ``count`` tasks."""
    return max(int(single_timeout), BATCH_TIMEOUT_PER_TASK * max(1, int(count)))
