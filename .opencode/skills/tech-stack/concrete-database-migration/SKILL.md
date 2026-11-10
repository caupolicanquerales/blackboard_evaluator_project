---
name: concrete-database-migration
description: Translates the selected storage technology and persistence strategy into expand-only DDL migration scripts and one infrastructure task handoff per context. Use after database-technology-selection.
---
# Input/Output
Inputs: selection record, persistence strategy, access paths. Outputs: DDL scripts under `services/<slug>/db/migrations/` + stage-0 task payloads per context. Dialects, types, tool and naming come ONLY from the active tech-stack skill. Forbidden: app source, ORM entities, live execution, editing existing queue files.
# Modeling
snake_case physical names, plural tables from aggregates/entities; PK = strategy's ID scheme (ULID/UUIDv7/auto-increment, concrete type from tech-stack); invariants -> constraints (FK, CHECK, UNIQUE, NOT NULL) in the PRIMARY store only; root aggregates carry `version` non-null default 0; first release EXPAND-ONLY: create tables/indexes/nullable columns - no drops, renames, or non-null backfills; one idempotent, recorded script per step. Secondary stores: only their native schema/index/TTL/lifecycle definitions (never DB DDL for object storage).
# Access paths -> indexes
Keyset: composite (sort, id); equality/range: B-tree; JSON containment: GIN (or partial for fixed predicates); write-heavy tables indexed ONLY for declared query_performance paths; covering index for hot reads; no speculative indexes.
# Handoff (one infra task per context)
Payload: name, technology+version, migration dir+ordering scheme, seed/reference data (if strategy names any), rollback posture (expand-only => forward-fix + backup restore), verification step (boot test / smoke), owner context, open risks. Naming/tooling per tech-stack skill.
# Checks
Every script expands, never destroys; every constraint maps to a named invariant; every index maps to a declared query; version columns present; non-primary stores carry only their own definitions.
