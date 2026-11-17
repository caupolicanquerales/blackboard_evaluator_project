---
name: domain-driven-architecture
description: "Use when the architect agent translates blackboard/domain-boundary-analysis.json into stack-agnostic layers, components, ports/adapters, and strict cross-boundary contracts. Execution rules only."
---
# Input
Per domain read `blackboard/domain/domain-boundary-<slug>.json` + `blackboard/context-map/context-map-<slug>.json` via the reader (validate first; non-zero => stop+report; never re-run discovery/mapping):
`python3 .opencode/skills/read-write-file-ddd/reader-file/scripts/reader_file.py --report <file> --expect any --validate-only`
Slice: subdomain, bounded_contexts[{invariants,source_of_truth,publishes,consumes,actors,external_systems}], ubiquitous_language, assumptions. Map: relationships, cross_boundary_flows.consistency_expectation.
# Rules
- One context => one logical module; never merge/split contexts or move invariants/source of truth; core = deepest model, generic = adapter+reuse; assumptions become explicit risks.
- Term => exactly one domain type in one context.
- Invariant => its aggregate; one aggregate per transaction; cross-aggregate refs by ID; cross-aggregate rules become explicit processes/events.
- Use cases => application services behind inbound ports; controllers/consumers/CLI are adapters calling ports.
- Persistence/messaging/external => outbound ports owned by application, adapters in infrastructure; schemas/drivers never leak inward.
- Events/published language at boundaries; anti-corruption translation where a foreign model enters; shared kernel minimal and named.
- Layers: domain (pure, owns invariants) <- application (use cases, ports, no framework) <- infrastructure (adapters); interface <- application; composition root wires.
# Deliverable (into the strategy)
modules + layers + build_order per the above; integration per relationship type; risks carry the assumptions; open questions recorded, never silently decided - DECISION-MAKING IS NOT DECOMPOSITION: a question that some unit operationalizes has been decided by omission, not avoided. An Ambiguity or Open question touching identity, delivery posture or STATE-MUTATION semantics (corrections, retries, revisions, supersession - what makes delivery N a new fact rather than a repeat of fact N-1) must be promoted to an explicit, decided Assumption BEFORE decomposition: named discriminator, outcome per resend class, and the invariant owner; the strategy then carries the RESOLVED assumption (with what it excludes and why), never the question next to a unit that answers it in silence (2026-11-16 PART III G2: "behavior for correcting packets unspecified; assumed handled as a revision" reached decomposition as an open question, the idempotency rule was satisfied with a natural identity that excluded the value, and value-corrections were silently reclassified as duplicates - no file on the board ever said so).
