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
ARCHITECT_AGENT = "agent-architect"
DATABASE_AGENT = "agent-database-architect"

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
ALLOWED_AGENTS = tuple(STAGE_AGENTS.values())

# Tool calls per agent session. Every turn re-sends the whole transcript, so a session's cost is
# its number of calls: these caps are stated in the prompt and checked again when the session ends.
AGENT_CALL_BUDGETS = {
    STAGE_AGENTS[0]: 10,
    STAGE_AGENTS[1]: 8,
    STAGE_AGENTS[2]: 6,
    STAGE_AGENTS[3]: 12,
    STAGE_AGENTS[4]: 12,
    ARCHITECT_AGENT: 12,
    DATABASE_AGENT: 14,
    DISCOVERY_AGENT: 10,
    MAPPING_AGENT: 10,
}
CODER_BATCH_FIRST_CALLS = 4
CODER_BATCH_CALLS_PER_UNIT = 3


def call_budget(target_agent, units=1):
    """Tool calls allowed to one session of `target_agent`; a coder batch shares more."""
    budget = AGENT_CALL_BUDGETS.get(target_agent)
    if budget is None:
        return None
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
OPTIONAL_KEYS = ("ast_hints",)
AST_HINT_KEYS = ("package", "implements", "dependencies", "methods")
PROMPT_KEYS = ("id", "path", "kind", "layer", "feature", "export", "intent", "dependsOn",
               "project", "ast_hints")
PROJECTS_SUBDIR = "services"
LAYERS = ("root", "domain", "application", "infrastructure", "interface", "shared", "features")
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
