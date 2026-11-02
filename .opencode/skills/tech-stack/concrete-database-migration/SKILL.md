---
name: concrete-database-migration
description: Translates the selected storage technology and persistence strategy into expand-only DDL migration scripts and one infrastructure task handoff per context. Use after database-technology-selection.
---

Inputs: `database-technology-selection` record, `persistence` strategy key, `query_performance` access paths. Outputs: migration scripts under `db/migrations/<slug>/` and queued infrastructure tasks. Rules are technology-agnostic; dialects, types, migration tool, and filename convention come only from the active tech-stack skill.

## Scope

- Generate DDL migration files and infrastructure task payloads only.
- Forbidden: application source, ORM entity classes, repositories, live database execution, edits to existing queue files.

## Modeling

- Physical names: snake_case, plural table/collection names from aggregates and entities.
- Primary keys: distributed unique ID (ULID or UUID v7) or auto-increment, as required by strategy; concrete type from tech-stack skill.
- Invariants map to constraints: `FOREIGN KEY`, `CHECK`, `UNIQUE`, `NOT NULL`. Enforce in the primary store only.
- Concurrency: root aggregate tables get `version` as a non-null integer defaulting to 0.
- Initial release is expand-only: create tables, indexes, nullable columns. No drops, renames, or non-null backfills in release one.
- One script per ordered step; each script is idempotent and recorded by the tech-stack migration tool.
- Non-primary stores: write only their schema or index definitions; use the store's native mechanism from the tech-stack skill (e.g. bucket policy and lifecycle for object storage, key naming and TTL for Redis, retention and continuous aggregate policy for time-series). Never write database DDL for object storage.

## Access path to index mapping

- Keyset pagination: composite index on `(sort_column, id)`.
- Equality and range filters: B-tree index.
- Unstructured JSON payload queries: GIN index, or partial index when the predicate is fixed.
- Write-heavy tables: index only columns required by a `query_performance` path; no speculative indexes.
- Full-text or vector paths: index type from tech-stack skill for the selected store.

## Infrastructure task handoff

- Queue one task per concern: store setup, schema migration, configuration profile, backup and recovery settings.
- Task ID: `T0-###`, the next free id given in the orchestrator prompt.
- Payload keys: `id, targetAgent, stage, dependsOn, path, kind, layer, feature, export, intent`. Fixed values: `targetAgent` "agent-container", `stage` 0, `dependsOn` [], `kind` "bootstrap", `layer` "root", `feature` null. `intent` carries the engine and version, migration runner setup, and ordered script paths.
- Queue only through `python3 <runner> --emit <draft files>`; the validator rejects unknown keys.
- Application tasks queued later list these ids in `dependsOn`; this skill never edits them.

## Output

```json
{
  "context": "<slug>",
  "engine": "<technology and version from tech-stack skill>",
  "migration_tool": "<from tech-stack skill>",
  "scripts": ["db/migrations/<slug>/<ordered-file>"],
  "indexes": [{"table": "<name>", "columns": ["<col>"], "type": "<btree|gin|composite|partial>", "access_path": "<query_performance id>"}],
  "tasks": [{"id": "T0-###", "concern": "<store|schema|config|backup>", "dependsOn": []}],
  "risks": ["<unmet constraint | nullable backfill deferred | missing access path>"]
}
```

## Constraints

- Ambiguous strategy or missing tech-stack skill: ask the user before generating.
- Do not guess dialect syntax; if the tech-stack skill does not define it, record a risk.
