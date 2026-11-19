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
decision, silence is not one (the `contexts_without_inbound` idiom). Numbers are budgets to
hold or targets to plan against - never invented precision, and never a reason to halt:
most business descriptions state behavior, not traffic - that is the NORM, not a gap. A
MISSING NUMBER IS A BASELINE ASSUMPTION, NEVER AN OPEN QUESTION: record one explicit
assumption (PA-01, e.g. "single-node baseline ceiling assumed wherever the description
omits rates and volumes"), derive the budgets conservatively from it, and let the workload
driver cite the assumption ("per PA-01"). The floor holds without real numbers.

# Budgets: every one carries a DETERMINISTIC measurement
A budget bounds one thing: admission (rate-limit), concurrency (bounded-semaphore), queueing
(bounded-queue, backpressure, drop-policy), cache (read-through-cache, negative-cache), retry
(idempotent-retry, bounded-attempts), page/payload sizes, resource ceilings (pool-limit,
timeout-budget), batching (batch-load). Each names its token, its enforcement expectation and
a `measurement` from the CLOSED kind set:
`query-count | config-key | status-code | payload-size | queue-depth | deterministic-count`.
THE WALL-CLOCK LAW: no kind measures elapsed time, because a stopwatch assertion flakes in
CI and an unenforceable limit is a wish - "p99 under 200ms" becomes "at most N queries per
request", "pool never exceeds N", "saturation answers the declared rejection status", "the
config key carries a finite bound", "the response body stays under N bytes". Every duty must
be provable at the stage-1 gate WITHOUT a load harness; the load harness is a post-delivery
activity this plan can require as a risk-noted ambition, never as the proof.

# Invariants: what holds at worst case
No unbounded queue, buffer or retry anywhere; one bounded policy per path with its rejection
behavior declared (status-code or drop-with-counter, never silent); saturation is answered,
never absorbed. Each invariant names a capability token.

# Duties: closure, or the plan is prose
Every budget and every invariant is discharged by at least one duty: obligation, capability
token (lowercase kebab), unit_kind from the closed set (admission-control, rate-limit-policy,
concurrency-guard, cache-policy, retry-policy, pagination-rule, resource-ceiling,
batch-policy, timeout-policy, budget-observer). A rule with no duty is refused by the gate -
same law as security. Where the environment cannot bound something the plan demands, that is
a `risks[]` entry citing the control or an accepted posture with its residual, never a
silently dropped duty.

# Vocabulary discipline
Requirements only: pools, semaphores, caches, budgets, backpressure - capacity architecture
English. A product name, library, annotation, file path, property key, or class suffix in the
artifact means the phase decided the architect's job; the gate refuses it. Undecided INPUT - a surface,
a flow, or a persisted concept no input declared, or two requirements that conflict - goes
to `open_questions`, which STOPS the run: an unsized surface at the gate is an unbounded
surface in production. A missing NUMBER is not undecided input (see the baseline law
above); halting a run for traffic a functional seed never described is mistaking the floor
for a spec sheet.
