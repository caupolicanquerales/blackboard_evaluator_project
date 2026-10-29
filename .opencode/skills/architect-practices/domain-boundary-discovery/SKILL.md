---
name: domain-boundary-discovery
description: Use when turning a natural-language business description into subdomains, bounded contexts, ubiquitous language, owned invariants, and domain events. Produces a JSON boundary draft only; no context map or code.
---

# Domain Boundary Discovery

Parent: [[java-architect-practices]]

## Purpose & scope

- Produce: subdomains (problem space), bounded contexts (solution space), ubiquitous language, owned invariants, source-of-truth concepts, and domain events.
- Stop at the boundary draft; no context map or application code.
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

## Output: boundary draft (JSON)

- Path: `blackboard/domain-boundary-draft.json`.
- Deliverable: exact JSON below; not Markdown.

```json
{
  "schema_version": "1.0",
  "report_type": "domain-boundary-draft",
  "metadata": {
    "generated_at": "2026-01-01T00:00:00Z",
    "agent": "domain-boundary-discovery-specialist",
    "run_id": "<optional>",
    "source_description": "<optional>",
    "confidence": "high"
  },
  "business_summary": {
    "goal": "<business goal>",
    "actors": ["<actor>"],
    "end_to_end_processes": ["<process>"],
    "key_outcomes": ["<outcome>"]
  },
  "ubiquitous_language": [
    {"term": "<term>", "context": "<bounded context>", "definition": "<meaning>", "synonyms_conflicts": ["<optional>"]}
  ],
  "subdomains": [
    {"name": "<subdomain>", "type": "core", "capability": "<capability>", "why_distinct": "<why>"}
  ],
  "bounded_contexts": [
    {
      "name": "<bounded context>",
      "responsibility": "<single responsibility>",
      "in_scope": ["<inside>"],
      "out_of_scope": ["<elsewhere>"],
      "ubiquitous_language": ["<term>"],
      "invariants": ["<owned rule>"],
      "source_of_truth": ["<owned concept>"],
      "publishes": ["<event>"],
      "consumes": ["<event>"],
      "actors": ["<actor>"],
      "external_systems": ["<optional>"],
      "confidence": "high"
    }
  ],
  "assumptions": [
    {"item": "<item>", "type": "Open question", "impact_on_boundaries": "<impact>", "confidence": "low"}
  ],
  "mapping_handoff": {
    "contexts_ready": ["<bounded context>"],
    "unresolved_risks": ["<risk>"]
  }
}
```

## Contract

- Top-level keys (exact, no extras): `schema_version`, `report_type`, `metadata`, `business_summary`, `ubiquitous_language`, `subdomains`, `bounded_contexts`, `assumptions`, `mapping_handoff`.
- Fixed: `schema_version="1.0"`; `report_type="domain-boundary-draft"`; `metadata.agent="domain-boundary-discovery-specialist"`; `metadata.generated_at` ISO-8601.
- Optional: `metadata.run_id`, `metadata.source_description`, `metadata.confidence`; `ubiquitous_language[].synonyms_conflicts`; `bounded_contexts[].external_systems`.
- Non-empty lists: `ubiquitous_language`, `subdomains`, `bounded_contexts`; `assumptions` may be `[]`.
- Enums: `subdomains[].type = core|supporting|generic`; `confidence = high|medium|low`; `assumptions[].type = Assumption|Ambiguity|Open question`.
- Types: `business_summary.goal` text; `actors`, `end_to_end_processes`, `key_outcomes` string[]; narrative fields = non-empty string|string[]; other collections = `[]`; `contexts_ready` = exact context names.
- Uniqueness: context names, subdomain names; each invariant and source-of-truth concept has exactly one owner; no duplicate rules.
- Do not persist Markdown tables/headings/prose.

## Persisting

- Primary:

```bash
python3 .opencode/skills/read-write-file-ddd/writer-file/scripts/writer_file.py \
  --source - --report-type discovery <<'JSON'
{ ...complete report payload... }
JSON
```

- Target/flags: default `blackboard/domain-boundary-draft.json`; `--force` only for requested regeneration; `--emit-template discovery` for a skeleton.
- Exit: `0` written | `1` schema rejected (fix, never bypass) | `2` source error | `3` write error or target exists without `--force`.
- Do not use raw file-write while the writer is available; use the agent fallback only when the writer cannot run.

## Handoff & constraints

- Handoff: pass JSON to `domain-context-mapping` for relationships, cross-boundary flows, validation, and final architect handoff. Mapping reads `blackboard/domain-boundary-draft.json`; if invoked alone, state mapping is pending.
- Analysis only; no code or tactical design.
- Use domain language, not generic technical names.
- Never assign an invariant to two contexts.
- Never equate a bounded context with a microservice, module, or package.
- Always state confidence and unresolved questions.
