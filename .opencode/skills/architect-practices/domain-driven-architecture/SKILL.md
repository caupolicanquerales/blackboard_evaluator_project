---
name: domain-driven-architecture
description: "Use when the architect agent translates blackboard/domain-boundary-analysis.json into stack-agnostic layers, components, ports/adapters, and strict cross-boundary contracts. Execution rules only."
---

# Domain-Driven Architecture

Stack-agnostic core skill for the architect agent. Decide boundaries and contracts; stack skills decide syntax. No application code.

## Input

Work one domain at a time. For each `blackboard/domain/domain-boundary-<slug>.json`, read that slice and its `blackboard/context-map/context-map-<slug>.json` with the project reader; do not hand-parse.

```bash
python3 .opencode/skills/read-write-file-ddd/reader-file/scripts/reader_file.py \
  --report blackboard/domain/domain-boundary-<slug>.json --expect any --validate-only
python3 .opencode/skills/read-write-file-ddd/reader-file/scripts/reader_file.py \
  --report blackboard/context-map/context-map-<slug>.json --expect any --validate-only
```

- Drop `--validate-only` to print the full validated report. Non-zero exit: stop and report. Do not re-run discovery or mapping.
- Slice fields: `subdomain`, `bounded_contexts.invariants/source_of_truth/publishes/consumes/actors/external_systems`, `ubiquitous_language`, `assumptions`.
- Context-map fields: `context_map.relationship/direction/boundary_protection`; `cross_boundary_flows.consistency_expectation`.
- One bounded context → one logical module; deployment units separate; never merge/split contexts or move invariants/source of truth without an explicit boundary.
- `core` gets the deepest model; `generic` gets adapters/reuse. Carry `assumptions` into explicit risks.

## 1. Strategic-to-tactical mapping rules

- **Context/module**: one module per context; public contract; private internals; `core` rich, `supporting` simple, `generic` buy/reuse + adapter.
- **Language → domain types**: each term maps to exactly one domain type in one context.
- **Invariants → aggregate boundaries**: one aggregate per transaction; reference by ID; enforce invariants inside; cross-aggregate rules become explicit policies/processes.
- **Ownership/events**: only the source-of-truth context writes; others read via contracts/events/projections; events are past-tense facts with stable names.
- **Actors/flows → use cases and adapters**: actors drive inbound use cases; external systems are outbound ports + ACL; cross-boundary flows map to use cases/sagas with state changes, compensation, temporary inconsistency.

## 2. Layering and inversion rules (hexagonal / ports and adapters)

```text
interface ──▶ application ──▶ domain
                   ▲
infrastructure ────┘
```

- **Dependencies/boundaries**: inward only; ports owned inside, implemented outside; root wires adapters; no framework/ORM in domain; expose only public contracts; no cross-context internals; shared kernel only if named; no cycles.
- **Contracts/persistence**: inbound DTOs/validation at adapter; outbound port interfaces; published versioned events/schemas; repository ports inside, adapters outside; no entity/ORM/transport type crosses a module boundary; one use case = one local transaction; outbox/saga across contexts.
- **MVC fallback**: only for simple CRUD/read-heavy `generic`/`supporting` contexts; keep controllers thin; do not let MVC/ORM shape the core.

## 3. Cross-boundary integration patterns

Use the weakest relationship from `context_map`; do not upgrade for convenience.

| Relationship | Rule |
|---|---|
| Partnership | Shared roadmap + contract tests; no internals. |
| Shared kernel | Minimal, versioned, owned; prefer duplication. |
| Customer-supplier | Upstream stable versioned contract; downstream needs. |
| ACL | Translate downstream; never import. |

Other patterns: Conformist = customer-supplier without influence; Open host service/published language = customer-supplier with public contract; Separate ways = no integration.

- **Consistency**: strong inside; eventual across via events/outbox/saga, idempotent consumers, retries, dead-letter, compensation; no 2PC; sync only when delay is unacceptable.
- **Contracts/data**: versioned/owned by publisher; consumers use published language, not internals/DB; events immutable, minimal, versioned; at-least-once, ordered per aggregate; contract tests; each context owns its data; projections for cross-context queries; never share tables.

## 4. Architectural anti-patterns

Reject; if forced, record the trade-off.

- **Boundaries**: no shared DB/tables, cross-context entity/ORM reuse, hidden coupling, leaky contracts, or cycles.
- **Layering**: no framework/ORM/transport in domain, business logic in controllers, adapters enforcing invariants, or missing ports/adapters.
- **Integration**: no distributed monolith, 2PC, events-as-commands, unversioned events, or assumed immediate consistency.
- **Modeling/delivery**: no anemic core, over-modeled generic, dual ownership, context-per-entity/table/screen, default microservices, premature abstraction, or context-as-deployment-unit; never invent/merge contexts or move invariants for convenience.

## Output

For each domain, produce one execution strategy (`blackboard/complete/execution-strategy-<slug>.json`) with modules, layers, build order, and risks, plus that domain's context→unit-of-work task seeds (one test/code/evaluator triple per unit; no code). Component, contract, and integration catalogs, ownership matrix, and flow map stay inside that domain's strategy and task files. Cross-domain links come from the context map only.

Gate: one owner per invariant/source of truth; every boundary has a contract and integration pattern; every flow has consistency/failure/compensation; no unjustified anti-pattern.

Stop at architecture: no framework code, schemas, or deployment topology.
