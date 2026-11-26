"""task_signals - prose-vs-table signals: what a unit's INTENT TEXT
advertises (artifacts, config triggers, nulls, meters, mechanisms, streams)
versus what its TABLES claim. Feeds plan_laws' z3-style joins; a signal
refuses nothing by itself, it only names the mismatch."""

import json
import re
import settings
from task_identity import _returns_signal


FILE_ARTIFACT_RE = re.compile(
    r"\b[\w./-]*\w\.(?:ya?ml|properties|sql|json|xml|conf|ini|toml|env)\b", re.I)
CONFIG_ARTIFACT_TAILS = ("application.yml", "application.yaml", "application.properties",
                         "settings.py", "config.py", "config.ts", "config.js",
                         "config.json", "config.yaml", ".env")
CONFIG_TRIGGER_RE = re.compile(
    r"@ConfigurationProperties|application\.(?:ya?ml|properties)|externalized[- ]config", re.I)
NULL_REJECT_RE = re.compile(
    r"rejects?[^.;]*\bnull\b|null[- ]?(?:reject|intoler)|\bnon-null\b", re.I)
# argument + comparison inside parentheses (or adjacent): "revision (>=1, ...)",
# "window (> 0)", "capacity (<= 1000)" - the invariant-claim surface of an intent.
# INTENT ECONOMY (2026-11-18 token audit of the plan phase): the emitted plan of one domain measured
# 23,585 tokens, of which `intent` prose was 52%; the biggest single assistant output turn on record
# was 40,442 tokens, and half the emit attempts bounced a refusal that used to demand a full rewrite.
# Volume is therefore a plan defect, not a style preference - but the machine rule is a WALL, not a
# target: only a document-sized intent is refused, and only while planning (a resumed board must stay
# readable). What must go instead is the narration `ast_hints` already pins; every token the gates
# demand (spec_ref + capability + mechanism, config literals, both signal branches) still stays.
INTENT_WORD_TARGET = 80
INTENT_WORD_CEILING = 180

CONSTRUCTOR_CLAIM_RE = re.compile(r"\b(\w+)\s*\(\s*(?:>=|<=|>|<)\s*\d")
MECHANISM_PROMISE_RE = re.compile(r"\bvia\b[^.;\n]{0,80}\bpropagat\w*"
                                  r"|\bpropagat\w*[^.;\n]{0,80}\bvia\b", re.I)
VIA_TOKEN_RE = re.compile(r"\bvia\s+(?:the\s+)?([A-Za-z][\w]*(?:[-\s][A-Za-z][\w]*){0,2})",
                         re.I)
FAIL_OUTCOME_RE = re.compile(r"\b(?:drop\w*|fail\w*|reject\w*|swallow\w*|overflow\w*)\b", re.I)
METER_CLAIM_RE = re.compile(r"(?:counter|meter|gauge|timer)[^.;\n]{0,80}"
                            r"(?:drop|fail|reject|error)|(?:drop|fail|reject|error)"
                            r"[^.;\n]{0,80}(?:counter|meter|gauge|timer)", re.I)
STEP_STOP_TOKENS = {"the", "and", "for", "with", "into", "from", "that", "this", "are",
                    "per", "each", "once", "after", "before", "when", "than", "then",
                    "over", "under", "not", "new", "raw", "all", "same", "every",
                    "their", "there", "which", "being", "was", "were", "been"}


def _step_tokens(text):
    return {w for w in re.findall(r"[a-z]{4,}", str(text or "").lower())
            if w not in STEP_STOP_TOKENS}


def _surface_norm(text):
    return " ".join(str(text or "").strip().lower().rstrip(".").split())


def _meter_pairs(step, metrics):
    st = _step_tokens(step)
    if not st:
        return True
    for entry in metrics:
        if isinstance(entry, str):
            entry = {"name": entry}
        if not isinstance(entry, dict):
            continue
        blob = " ".join([str(entry.get("name", "")), " ".join(map(str, entry.get("tags") or [])),
                         str(entry.get("counts", ""))])
        mt = _step_tokens(blob)
        if any(a == b or a.startswith(b[:5]) or b.startswith(a[:5]) for a in st for b in mt):
            return True
    return False


def _mechanism_claimed(token, texts):
    """The strategy's mechanism phrase must appear as an INSTALL duty, adjacent and
    unnegated: 'no context-propagation library is used' is a divergence, not a duty -
    the refusal class G3 was born from (the plan quietly un-promised the strategy)."""
    norm = _surface_norm(token).replace("_", "-")
    if not norm:
        return True
    words = [w for w in re.split(r"[-\s]+", norm) if w]
    joined = r"[-\s]+".join(map(re.escape, words))
    alt = r"[-\s]+".join(map(re.escape, reversed(words))) if len(words) > 1 else joined
    finder = re.compile(f"(?:{joined}|{alt})", re.I)
    negated = re.compile(r"\b(?:no|not|without|never|avoid\w*|skip\w*|exclude\w*|"
                         r"drop\w*|remov\w*|abandon\w*)\b[^,.;]{0,24}$", re.I)
    for text in texts:
        for match in finder.finditer(text):
            if negated.search(text[:match.start()][-28:]):
                continue
            return True
    return False

# Prose-vs-table shape (seed-002 rerun F2: the T2-014 pair that froze T2-020 and the
# whole deferred cluster behind it). Two deterministic contradiction classes are emit-
# refused because NO payload can ever satisfy both sides of the pair:
#   (1) an intent asserting an UNCONSTRUCTIBLE shape (private constructor / utility
#       class / non-instantiable) while its own table binds INSTANCE members;
#   (2) an intent calling a pinned producer's member in STATIC form (`Type.member(`)
#       while that producer's table binds it as an instance member.
# Both are pure text comparisons of the task records - stack-neutral by construction;
# yesterday's rules made the table win at WRITE time, this refuses the contradiction at
# PLAN time so the two frozen tests of one type can never be written in two shapes again.


def _path_is_config_artifact(path):
    p = str(path or "").replace("\\", "/").lower()
    return any(p.endswith(tail) for tail in CONFIG_ARTIFACT_TAILS)


def _signature_parameters(hints):
    """The parameter text of every pinned signature - request bindings live there."""
    for method in (hints or {}).get("methods", []) or []:
        signature = str(method.get("signature", "")) if isinstance(method, dict) else str(method)
        if "(" in signature:
            yield signature[signature.index("("):]


def per_record_signal_problems(records):
    """(m)/(d) signal semantics - a PER-RECORD join: a tabled boolean/status return that
    spells no encoding is a defect the record itself already admits. Extracted 2026-11-25
    so LINT can say it inside the session's own budget; plan_consistency keeps calling it,
    so the batch still refuses what a session talked past (one body, two tiers)."""
    errors = []
    for task in records:
        if not isinstance(task, dict) or task.get("stage") not in (1, 2):
            continue
        for member in (task.get("ast_hints") or {}).get("methods") or []:
            if (isinstance(member, dict) and _returns_signal(member.get("returns"))
                    and not str(member.get("semantics") or "").strip()):
                errors.append(
                    f"{task['id']}: tabled method '{member.get('signature')}' returns a "
                    "SIGNAL but carries no `semantics` - spell what TRUE and what FALSE "
                    "mean to the caller (accepted/rejected, inserted/duplicate, "
                    "written/dropped): a false the plan never describes is a false the "
                    "coder discards, and the caller answers success anyway (2026-11-16: "
                    "publish()->false silently dropped samples under burst, API lied 202)")
    return errors
