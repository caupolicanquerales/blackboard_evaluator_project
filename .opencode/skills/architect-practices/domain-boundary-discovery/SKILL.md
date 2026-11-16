---
name: domain-boundary-discovery
description: Use when turning a natural-language business description into subdomains, bounded contexts, ubiquitous language, owned invariants, and domain events. Produces one JSON slice per subdomain in blackboard/domain/; no context map or code.
---
# Purpose
Produce per-subdomain slices: subdomains, bounded contexts, ubiquitous language, owned invariants, source-of-truth concepts, domain events. Stop at `blackboard/domain/`; no context map, no tactical DDD, no packages/APIs/schemas/infrastructure, no invented requirements.
Subdomain = expertise area; bounded context = one boundary, one model; aggregates listed only as consistency candidates.
# Workflow
1. Extract: read twice (outcomes/actors/flows; nouns/verbs/rules/events/quantities). Per term: definition, actors, synonyms/overloads. Keep user words.
2. Capabilities: group verbs/outcomes; own rules+lifecycle+owner = boundary signal.
3. Split on signals, not entities: language, rule/lifecycle ownership, actor change, cadence, data ownership, consistency, regulatory.
4. Classify: core = differentiator (deepest modeling); supporting = necessary/specific; generic = buy/reuse. Name by capability, never tech.
5. Contexts: name, responsibility, in/out scope, language, invariants, source of truth, publishes/consumes, actors, external systems, confidence. One meaning per term per context; one owner per invariant; strong consistency inside; never a context per entity/table; never merge unrelated rules to shrink count.
6. Events: significant occurrences, producer + likely consumers, names only.
7. Validate: one owner per invariant; significant terms placed or flagged; nothing invented; uncertainty as Assumption|Ambiguity|Open question with boundary impact. **Transport posture is a modeled fact**: for every inbound flow, record whether delivery is at-most-once or at-least-once (retries, redelivery, network replay) and, when the flow writes an append-only/correcting history, which identity makes a retry distinguishable from a new event (client-supplied key, natural business identity, or an explicit accept-duplicates declaration). A capability described as "ingest, corrections append revisions" over an HTTP-like delivery, with no dedup identity named, is an UNRESOLVED AMBIGUITY worth a boundary question - not an assumption to silently invent (seed-002 2026-11-16: server-minted ids over an at-least-once POST made every network retry mint a domain revision the device never sent twice). **Seed fidelity**: every entity, metric, named range/threshold and status literal the description spells out must appear VERBATIM in some context's language or invariants, or the deviation must be recorded as a named Assumption with its reason - substituting vocabulary the description never used (another sensor family, renamed flags, different boundary numbers) creates a wrong world that stays internally consistent and is invisible to every downstream gate, because all later validators check coherence, not fidelity (2026-11-16: an athletic-telemetry seed produced weather-metric enums; 71 tasks and every green test inherited the drift).
# Output
One `domain-boundary-<slug>.json` per subdomain, exact slice keys per the specialist contract; valid JSON; unique context names; thin input => best-effort + assumptions; `question` only for boundary-changing unknowns.
