---
name: domain-boundary-discovery
description: Use when turning a natural-language business description into subdomains, bounded contexts, ubiquitous language, owned invariants, and domain events. Produces one JSON slice per subdomain in blackboard/domain/; no context map or code.
---

# Domain Boundary Discovery

Parent: [[java-architect-practices]]

## Purpose & scope

- Produce: subdomains (problem space), bounded contexts (solution space), ubiquitous language, owned invariants, source-of-truth concepts, and domain events.
- Stop at the per-subdomain slice files; no context map or application code.
- Do: interpret input; extract vocabulary/actors/rules/flows; detect boundaries; classify subdomains; propose contexts; record uncertainty.
- Do not: context mapping (`domain-context-mapping`), packages/APIs/schemas/infrastructure, tactical DDD, or invented requirements.
- Concepts: subdomain = business expertise area; bounded context = solution boundary with one model/language; aggregate = later consistency candidate (list only).

## Workflow

1. **Extract** — Read twice: outcomes/actors/flows, then nouns/verbs/rules/events/quantities. Keep user terms. Per term: definition, actors/systems, activity, synonyms/overloads.
2. **Capabilities** — Group verbs/outcomes. A capability is a boundary signal when it has its own rules, lifecycle, and owner.
3. **Boundary signals** — Split when rules/language/ownership differ, not entities: language, rule ownership, lifecycle ownership, actor/role change, change cadence, data ownership, transactional consistency, regulatory/contractual.
4. **Subdomains** — `core` = differentiator, deepest modeling; `supporting` = necessary/specific, simpler; `generic` = buy/reuse. Name by business capability, not technology.
5. **Bounded contexts** — Define name/single responsibility, in/out scope, ubiquitous language, invariants, source-of-truth, publishes/consumes, actors/external systems, confidence. Constraints: one meaning per term per context; one owner per invariant; strong consistency inside a context; no context per entity/table/screen; no "everything" context unless one model/owner.
6. **Validate/gaps** — Every significant term placed or ambiguous; no invariant dual-owned; each context has a business reason; core distinguishable; never invent actors/rules/integrations. Mark unknowns `Assumption|Ambiguity|Open question`. Prefer best-effort draft; if too thin, one provisional context + split questions.
- Ask only boundary-changing questions: decision owner, rule universality, atomicity, source of truth, term meaning per actor.

## Output: one slice per subdomain (JSON)

- Path: `blackboard/domain/domain-boundary-<subdomain-slug>.json` (slug: lowercase, non-alphanumerics replaced by `-`).
- One file per subdomain. No aggregate draft is written.
- Deliverable: exact JSON below; not Markdown.
- Each slice holds only its own subdomain, its contexts, and its terms. Context names are unique across all slices.

```text
schema_version="1.0"
report_type="domain-slice"
metadata={generated_at, agent}
subdomain={name, type: core|supporting|generic, capability, why_distinct}
ubiquitous_language=[{term, context, definition}]
bounded_contexts=[{name, responsibility, in_scope, out_of_scope, ubiquitous_language, invariants, source_of_truth, publishes, consumes, actors, external_systems?, confidence}]
assumptions=[{item, type, impact_on_boundaries, confidence}]
```

## Contract

- Top-level keys (exact, no extras): `schema_version`, `report_type`, `metadata`, `subdomain`, `ubiquitous_language`, `bounded_contexts`, `assumptions`.
- Fixed: `schema_version="1.0"`; `report_type="domain-slice"`; `metadata.agent="domain-boundary-discovery-specialist"`; `metadata.generated_at` ISO-8601.
- Optional: `metadata.run_id`; `bounded_contexts[].external_systems`.
- Non-empty lists: `ubiquitous_language`, `bounded_contexts`; `assumptions` may be `[]`.
- Enums: `subdomain.type = core|supporting|generic`; `confidence = high|medium|low`; `assumptions[].type = Assumption|Ambiguity|Open question`.
- Uniqueness: context names unique across all slices; each invariant and source-of-truth concept has exactly one owner.
- Do not persist Markdown tables/headings/prose.

## Persisting

- One command per subdomain:

```bash
python3 .opencode/skills/read-write-file-ddd/writer-file/scripts/writer_file.py \
  --source - --report-type domain-slice \
  --target blackboard/domain/domain-boundary-<subdomain-slug>.json <<'JSON'
{ ...complete slice payload... }
JSON
```

- `--emit-template domain-slice` prints a skeleton. `--force` only for requested regeneration.
- Exit: `0` written | `1` schema rejected (fix, never bypass) | `2` source error | `3` write error or target exists without `--force`.
- Do not use raw file-write while the writer is available.

## Handoff & constraints

- Handoff: the orchestrator starts `domain-context-mapping` only after every `blackboard/domain/domain-boundary-*.json` exists and parses. Mapping reads those slices.
- Analysis only; no code or tactical design.
- Use domain language, not generic technical names.
- Never assign an invariant to two contexts.
- Never equate a bounded context with a microservice, module, or package.
- Always state confidence and unresolved questions.
