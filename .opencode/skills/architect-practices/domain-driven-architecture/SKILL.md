---
name: domain-driven-architecture
description: "Use when the architect agent translates blackboard/domain-boundary-analysis.json into stack-agnostic layers, components, ports/adapters, and strict cross-boundary contracts. Execution rules only."
---
# Input
Per domain read `blackboard/domain/domain-boundary-<slug>.json` + `blackboard/context-map/context-map-<slug>.json` via the reader (validate first; non-zero => stop+report; never re-run discovery/mapping):
the `read-write-file-ddd` reader, run with `--report <file> --expect any --validate-only`
Slice: subdomain, bounded_contexts[{invariants,source_of_truth,publishes,consumes,reads?,actors,external_systems}], ubiquitous_language, assumptions. publishes/consumes are asynchronous domain events; `reads` names synchronous query dependencies a context needs to do its own work - wire reads as direct ports/queries, never as event machinery. Map: relationships, cross_boundary_flows.consistency_expectation, and any read-after-event staleness posture the flow names - a posture the plan COMMITS to is a `rules` row {context, statement} naming its enforcing context, so it rides the digest to a unit that implements it; a `risks` row records an EXPOSURE the plan accepts, and an ordering guarantee parked there is enforced nowhere (a risk has no claiming unit - only rules and surfaces reach the planner).
# Rules
- One context => one logical module; never merge/split contexts or move invariants/source of truth; core = deepest model, generic = adapter+reuse; assumptions become explicit risks.
- RULE VALUES TRAVEL WITH THE STRATEGY: every numeric bound, window length, limit and named
  status literal the slice spells (`invariants`, `ubiquitous_language` definitions) is tabled
  in a `rules` array - one entry {context, statement} per bounded rule, the description's
  numbers, units and tokens copied VERBATIM. The security, performance, database and planning
  phases read the strategy and its digests, NEVER the description: a value paraphrased away
  here (30-240 becoming "physiological limits") is a value no unit asserts and no test pins
  (2026-11-24 seed-002: the ranges and the 60-second window died in phase 1 and the plan
  shipped "configured boundaries" with no configured physics). A one-sided rule keeps its
  open side - never invent a bound the description did not state; a rule the slice leaves
  value-less stays value-less and is recorded as an assumption or open question.
- Term => exactly one domain type in one context.
- Invariant => its aggregate; one aggregate per transaction; cross-aggregate refs by ID; cross-aggregate rules become explicit processes/events.
- Use cases => application services behind inbound ports; entry adapters - whatever brings work in from outside (request handlers, message consumers, schedulers, command runners) - call those ports.
- Persistence/messaging/external => outbound ports owned by application, adapters in infrastructure; schemas/drivers never leak inward.
- Events/published language at boundaries; anti-corruption translation where a foreign model enters; shared kernel minimal and named.
- Layers: domain (pure, owns invariants) <- application (use cases, ports, no framework) <- infrastructure (adapters); interface <- application; composition root wires.
# Deliverable (into the strategy)
modules + layers + build_order per the above + the `rules` table (the slice's rule values,
verbatim); integration per relationship type; risks carry the assumptions; open questions recorded, never silently decided - DECISION-MAKING IS NOT DECOMPOSITION: a question that some unit operationalizes has been decided by omission, not avoided. An Ambiguity or Open question touching identity, delivery posture or STATE-MUTATION semantics (corrections, retries, revisions, supersession - what makes delivery N a new fact rather than a repeat of fact N-1) must be promoted to an explicit, decided Assumption BEFORE decomposition: named discriminator, outcome per resend class, and the invariant owner; the strategy then carries the RESOLVED assumption (with what it excludes and why), never the question next to a unit that answers it in silence (2026-11-16 PART III G2: "behavior for correcting packets unspecified; assumed handled as a revision" reached decomposition as an open question, the idempotency rule was satisfied with a natural identity that excluded the value, and value-corrections were silently reclassified as duplicates - no file on the board ever said so).
