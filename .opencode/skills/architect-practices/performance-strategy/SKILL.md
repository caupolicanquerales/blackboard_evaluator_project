---
name: performance-strategy
description: Use when designing a bounded context's performance posture - workload per declared surface, budgets with deterministic measurements, load invariants - as abstract capability tokens. Stack-agnostic: never names a product, library or annotation. No tasks, no files.
---
# The load floor is unconditional
Every executable context receives load: requests, events, rows, bytes. This phase plans it
the way the security phase plans permission - a domain with no performance spec is a domain
sized by framework defaults in the dark. Inputs are the execution strategy (its `surfaces`
table is the row source, `persistence` the volume source, `observability` the only place a
count is already promised) and the DDD slice + context map. Nothing else: no re-deciding
architecture, no stack reading, no tasks.

# Workload: one entry per declared surface, keyed VERBATIM
One entry per strategy `surfaces[].name`, copied word for word (that string is the join key
the decomposition matches units on - a paraphrase claims no unit). Each entry states what
drives it: arrival expectation, payload shape, fan-out, and the persisted concepts it moves
(`persistence.data_model` names them; copy concept names verbatim too). A surface that truly
carries no load duty goes to `surfaces_exempt` WITH a reason - the exemption is the visible
decision (the `contexts_without_inbound` idiom). Numbers are bounds to hold, never invented
precision, and never a reason to halt: a MISSING NUMBER IS A BASELINE ASSUMPTION, NEVER AN
OPEN QUESTION - record one assumption (PA-01, e.g. "single-node baseline ceiling assumed
wherever the description omits rates and volumes"), derive the budgets conservatively from
it, and let the workload driver cite the assumption ("per PA-01"). The floor holds without
real numbers.

# Budgets: every one carries a DETERMINISTIC measurement
A budget bounds one thing: admission (rate-limit), concurrency (bounded-semaphore), queueing
(bounded-queue, backpressure, drop-policy), cache (read-through-cache, negative-cache), retry
(idempotent-retry, bounded-attempts), page/payload sizes, resource ceilings (pool-limit,
timeout-budget), batching (batch-load). Each names its token, its enforcement expectation and
a `measurement` from the CLOSED kind set:
`query-count | config-key | status-code | payload-size | queue-depth | deterministic-count`.
THE WALL-CLOCK LAW: no kind measures elapsed time - every limit becomes a count, a bounded
key, a rejection status or a size ("p99 under 200ms" becomes "at most N queries per request",
"the response body stays under N bytes"). Provable at the stage-1 gate WITHOUT a load
harness; a load run is a post-delivery ambition, never the proof.

# Invariants: what holds at worst case
No unbounded queue, buffer or retry anywhere; one bounded policy per path with its rejection
behavior declared (status-code or drop-with-counter, never silent); saturation is answered,
never absorbed. Each invariant names a capability token.

# Duties: closure, or the plan is prose
Budgets are the duty rows. Every budget and every invariant is discharged by at least one
duty, ONE duty per unique (`capability`, `unit_kind`, `owner_context`): obligation, capability
token (lowercase kebab), unit_kind from the closed set (admission-control, rate-limit-policy,
concurrency-guard, cache-policy, retry-policy, pagination-rule, resource-ceiling,
batch-policy, timeout-policy, budget-observer), `owner_context` an exact `bounded_contexts`
name - the same pair enforced in two contexts is TWO duties, one semaphore per context. A
`WB-*` workload entry and a `PA-*` assumption are CONTEXT, never standalone duty targets:
unless a surface needs a capability no `PB-*` budget covers, WB and PI ids that share a
duty's triple ride that duty's `covers` list - a repeated triple or a `PA-*` duty target is
refused. A rule with no
duty is refused by the gate - same law as security. Where the environment cannot bound
something the plan demands, that is a `risks[]` entry citing the control or an accepted
posture with its residual, never a silently dropped duty.

# Vocabulary discipline
Requirements only: pools, semaphores, caches, budgets, backpressure - capacity architecture
English. A product name, library, annotation, file path, property key, or class suffix in the
artifact means the phase decided the architect's job; the gate refuses it. Undecided INPUT -
a surface, flow or persisted concept no input declared, or conflicting requirements - goes to
`open_questions`, which STOPS the run. A missing NUMBER is the baseline assumption's job
(see Workload), never an open question.
