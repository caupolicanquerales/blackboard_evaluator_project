---
name: ai-strategy
description: Use when a description-verified ai_directive requires AI capability inside the generated backend - plan model roles, closed-vocabulary capability tokens, deterministic evaluation and guardrail duties, and the offline model-port invariant. Stack-agnostic: no framework, SDK, vendor or model product names. No tasks, no files.
---
# The trigger is the user's sentence, not your judgment
This phase runs ONLY when the domain's slice carries `ai_directive{required:true, quote}`
whose quote the engine found VERBATIM in the business description. That sentence is the
mandate and the BOUNDARY: plan what it names, nothing it never asked for - an inferred
feature is the sibling of an inferred waiver. Absent = absent phase = absent spec: the
correct silence.

# What an AI capability actually is, in a plan
Every model/embedding access is a PORT at a domain-owned boundary (context types, never
vendor objects), the adapter kept outside it. Each duty maps to ONE CLOSED token (an
unmappable token has no realization channel; the gate refuses it):

| token | what must hold |
|---|---|
| `prompt-contract` | every prompt is a versioned artifact of the plan carrying FIVE elements - version, role identity, input placeholders, output-schema reference, and the refusal text for out-of-scope asks - never a string assembled ad hoc in a caller. The artifact is a SOURCE TYPE, tabled and asserted member by member: a template FILE has no writer, no member, no claimable version - a duty without a channel |
| `structured-output-guard` | model output is schema-validated BEFORE anything trusts it; a violation is refused (or re-asked within a declared budget), never coerced, never raw-logged |
| `context-budget-cap` | every assembly of history/documents/prompt enforces a named truncation or selection bound; unbounded context is the leak and the blow-up at once |
| `fallback-model-route` | a degraded path per role (alternate route, cached answer, honest refusal) with its trigger; a model failure escaping as a 500 is an undeclared dependency made visible |
| `retrieval-scope-guard` | retrieval respects the same ownership rules the surrounding surface carries - a query cannot return rows the caller could not read directly |
| `tool-call-guard` | any action the model requests passes the SAME admission checks as the human path; no ambient authority, enumerated operations, refusal otherwise |
| `eval-golden-set` | behavior is pinned by a versioned example set (input, expected property) runnable offline against the stub port - the stage-1 contract for quality, not an aspiration |
| `memory-boundary` | where a model may remember is stated per role (none / session / durable) AND how it stays bounded (its technique) - see # Memory: the tier and the technique; undeclared session-outliving state is a disclosure |
| `offline-model-port` | THE MANDATORY INVARIANT: every port has an offline stand-in, and NO unit test, slice or boot may reach a live endpoint - the drain has no network truth, a live CI call is a defect that bills money, and a test that needs the real model is not deterministic. The stand-in must WIN WITNESSED: the spec names who holds precedence over the production bean, and the support contract proves the context resolves the PORT to the substitute - an override assumed is an override not delivered |
| `token-cost-cap` | budget per call and per flow with a named over-budget behavior (refuse, degrade, queue); cost discipline is decided at plan time |
| `agent-handoff` | delegation is a TOPOLOGY, not a vibe: every edge (from-role -> to-role)
enumerated with its typed envelope tabled; a handoff no edge declares cannot happen at
runtime; the receiver is addressed ONLY through its port |
| `loop-budget-cap` | THE TERMINATION LAW: every autonomous cycle - a handoff chain, a
plan-do-critique loop, a worker pool feeding itself - carries a max-turns bound and a named
cycle-break outcome; each call can be valid and small, the CYCLE kills (the AI class of the
unbounded queue). The gate refuses an `agent-handoff` topology without this invariant; proof
= `stub-call-count`, bounded by construction, never by a clock |
| `incremental-progress-stream` | DELIVERY SHAPE is a plan decision, not a coding habit: a long-running or multi-step execution emits incremental chunk/progress events over a non-blocking push channel, ending in a terminal completion, instead of holding one request-response connection to the end. Emit when the directed capability involves multimodal analysis, a handoff loop, or user-facing generation whose time-to-first-token would stall a call; where completion is polled from the durable store, record the assumption - silence about the shape is undecided delivery. The name is TRANSPORT-FREE (SSE/websocket/queue are phase 2's mapping onto the surface). Proof = `stub-call-count`/`deterministic-count`: N incremental events, THEN the terminal completion, never a test that blocks for full completion first |
| `human-approval-gate` | a high-impact or irreversible tool SPLITS into propose and execute:
the proposal persists as an `awaiting_approval` state, execution happens ONLY through the
declared resume channel (one use case, rule (n)'s one-mechanism law), denial is a first-class
outcome; the pause is asynchronous state, never a thread blocked on a human. The RESUME
CHANNEL IS A NEW INBOUND SURFACE: it must already sit in the strategy's `surfaces` table
(only phase 1 declares it; else an `open_questions` entry, never a silent permission hole) |

# Roles: state and data, on the record
Name each model/embedding role, its `statefulness` (none / session / durable) and the data
classes it may touch, copied from the strategy's concepts. A role that names no data classes
touches all of them; a role not saying where it remembers remembers everywhere. In
multi-agent plans the topology is built FROM these rows: every agent an edge, capability or
invariant mentions must be a `model_roles` entry bound through the row's optional `roles`
list (AR- ids only - a topology agent with no row is a ghost).

# Memory: the tier and the technique
Statefulness names the TIER - decided by triggers, not taste:
- `none` - single-turn extraction/classification/analysis; a handoff worker that receives
  its whole context in the task envelope;
- `session` - short-lived interactive use; losing history on restart acceptable; no audit
  or resume duty;
- `durable` - MANDATORY when any trigger holds: (1) cross-session continuity (across
  disconnects, devices, days); (2) a bound `human-approval-gate` pause - `awaiting_approval`
  resumes through an inbound surface, so it cannot live in a process that may restart or
  rebalance; (3) shared blackboard or auditable history - the concept MUST already sit in
  `persistence.data_model`, else `open_questions` for phase 1 / the database step; (4) long-
  term semantic recall.
Every non-`none` role also names its TECHNIQUE - how `memory-boundary` pairs with
`context-budget-cap` (what the bound keeps, what it compacts):
- `sliding-window` - the last N turns verbatim, older turns dropped;
- `rolling-summary` - older turns periodically condensed into a running summary, recent
  verbatim; compaction IS the budget mechanism, so it needs its own bound (interval/tokens);
- `semantic-episodic` - past turns/facts embedded, retrieved top-K per query; it reaches
  across sessions by design, so it REQUIRES `retrieval-scope-guard`: unscoped semantic memory
  is a tenant-to-tenant disclosure with good recall. Triggers provable from the artifact (2,
  the data_model half of 3, the semantic binding) are gate laws; the rest is the author's
  call, made visible by the fields they read.

# The spec_ref law: rules are discharged, context is cited
A duty's `spec_ref` names a CAPABILITY (AC-) or an INVARIANT (AM-) - the rows that carry a
token to match. A model role is a SUBJECT realized through the capabilities that bind it; an
assumption is a recorded decision. Cite AR-/AA- inside an obligation, never as its target:
a role duty has no token to match and the claim gate could not read it back.

# Measurements: deterministic or nonexistent
Every capability carries a `measurement` from the closed set
(`stub-call-count | schema-validation | config-key | status-code | payload-size |
deterministic-count`): the stub counts calls, the schema validates, the budget key is read,
the refusal answers its status, the prompt stays under size. Model output equality is never a measurement: assert the CONTRACT around the model,
never its wording.

# Duties and closure
Every capability and every invariant is discharged by a duty: obligation, same token,
unit_kind from the closed set (model-port-adapter, prompt-contract, output-validator,
context-budget, fallback-policy, retrieval-adapter, tool-guard, eval-harness, memory-adapter,
offline-stub, orchestration-router, loop-governor, approval-gate, stream-delivery). Undecided (a flow the inputs never declared) goes to `open_questions`, which
stops the run - never invented. Realizations (frameworks, SDKs, vendors, model names) belong
to the architect's mapping tables; here they are gate refusals.
