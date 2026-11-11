---
name: domain-context-mapping
description: "Use after domain-boundary-discovery to build and validate the DDD context map, choose integration relationships and boundary protection, map cross-boundary flows, and write one context map per discovery slice for an architect agent. No code."
---
# Purpose
Boundary slices => validated context maps, one per slice in `blackboard/context-map/`. Analysis only; no code/APIs/schemas. Discovery slices must exist and parse (reader tool); missing/invalid => stop+report; never invent contexts.
# Workflow
1. Confirm inputs: each context has responsibility, language, owned invariants, source of truth. Invariant with 0 or 2 owners => return to discovery.
2. Interactions per pair: what crosses; initiator; up/downstream; what never leaks; eventual vs immediate. Nothing crosses => separate ways.
3. Relationships (choose by condition, not fashion; direction upstream->downstream):
   Partnership - co-evolve (coupling risk). Shared kernel - minimal explicit shared model (keep tiny, name it). Customer-supplier - negotiated downstream needs. Conformist - downstream adopts upstream model (loses freedom). Anti-corruption layer - downstream translates foreign model (protects, costs maintenance). Published language - stable versioned contract for many consumers.
4. Flows: event, payload concept, initiator, consumers, consistency (transactional|eventual), failure posture (retry/idempotency/compensation).
5. Protections: translate where models diverge; name what may cross (events, published language) and what may not (internals).
6. Validate: publishes/consumes matched; unmatched terms flagged ambiguous; no unnamed coupling cycles.
# Output
`context-map-<slug>.json` payload keys ONLY: schema_version "1.0", report_type "context-map", metadata{generated_at, agent, source_report "blackboard/domain"}, context_map[{upstream, downstream, relationship, direction, exchanged_information, boundary_protection}], cross_boundary_flows[{business_process, contexts_involved, consistency_expectation, notes?}]. Context names exact or "external"; required context_map when >1 context. No other top-level keys. Persist via the writer script; `--emit-template context-map` prints the exact skeleton.
