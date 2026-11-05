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
CODER_WRITER = SKILLS_DIR / "read-write-file-ddd" / "writer-coder-changes" / "write-coder-changes.py"
RED_PHASE_DIR = BLACKBOARD / "red-phase"
GATE_CACHE_DIR = BLACKBOARD / "gate-cache"

DISCOVERY_AGENT = "domain-boundary-discovery-specialist"
MAPPING_AGENT = "domain-context-mapping-specialist"
ARCHITECT_AGENT = "agent-architect"
DATABASE_AGENT = "agent-database-architect"

STAGE_AGENTS = {
    0: "agent-container",
    1: "agent-tester",
    2: "agent-coder",
    3: "agent-evaluator",
}
STAGE_KINDS = {
    0: ("bootstrap",),
    1: ("test",),
    2: ("code",),
    3: ("refactor",),
}
ALLOWED_AGENTS = tuple(STAGE_AGENTS.values())

# Tool calls per agent session. Every turn re-sends the whole transcript, so a session's cost is
# its number of calls: these caps are stated in the prompt and checked again when the session ends.
AGENT_CALL_BUDGETS = {
    STAGE_AGENTS[0]: 10,
    STAGE_AGENTS[1]: 8,
    STAGE_AGENTS[2]: 6,
    STAGE_AGENTS[3]: 12,
    ARCHITECT_AGENT: 12,
    DATABASE_AGENT: 10,
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
PROMPT_KEYS = ("id", "path", "kind", "layer", "feature", "export", "intent", "dependsOn", "project")
PROJECTS_SUBDIR = "services"
LAYERS = ("root", "domain", "application", "infrastructure", "interface", "shared", "features")
ID_PATTERN = re.compile(r"^T([0-3])-(\d{3})$")

VERIFY_MODES = ("none", "typecheck", "build")
MAX_TDD_RETRIES = 3
TDD_STAGE = 2
TESTER_STAGE = 1
EVALUATOR_STAGE = 3
AST_DISPATCH_TIMEOUT = 1800
WEAVER_DISPATCH_TIMEOUT = 1800
TEST_GATE_TIMEOUT = 600
# A batch session writes one payload per task, so it needs a budget that scales with the batch.
BATCH_TIMEOUT_PER_TASK = 240


def batch_timeout(single_timeout, count):
    """Seconds allowed for one agent session that carries ``count`` tasks."""
    return max(int(single_timeout), BATCH_TIMEOUT_PER_TASK * max(1, int(count)))
