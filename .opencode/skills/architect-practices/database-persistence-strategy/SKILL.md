---
name: database-persistence-strategy
description: "Use when designing a bounded context's data layer: storage paradigm, data model, query/performance, migration. Technology-agnostic; no code, DDL, or vendor config."
---

# Database & Persistence Strategy

Parent: [[java-architect-practices]]

## Scope & Rules
- Analysis only: no DDL, query text, index syntax, ORM, config, or migration scripts. Missing context: `Open question`; never invent entities or invariants.
- Technology from drivers only (consistency, atomic aggregates, read patterns, rates, volume, growth, retention, lifecycle). Capability names, not vendors, unless mandated. Domain language. State confidence and open questions.
- Paradigms: relational, document, key-value, wide-column, graph, search, log, cache. Weakest consistency and simplest paradigm meeting invariants; record drivers, rationale, rejected alternatives, change conditions.
- One store per source-of-truth concept; one engine per context unless a measured need. Secondary stores are derived: record rebuild source and staleness bound.
- One consistency boundary per aggregate; reference other aggregates by identifier only. Denormalize deliberately: copy, source, staleness.
- Each invariant has one enforcement layer (store, domain, or both); critical invariants never rely on one layer without stated reason.
- Keying, audit markers, optimistic versioning, sensitivity (classification, encryption, masking, retention, deletion) per concept.
- Queries drive access paths; each maps to a store, access path, or derived model. Per read: caller, frequency, latency target, staleness (strong for source of truth; stale-tolerant with max bound for read model or cache).
- No unbounded scans or offsets; stable keyset ordering. Never add a cache to hide a missing access path. Bound results and collections; archive cold data; shard only if volume requires.
- Concurrent writers per aggregate: optimistic version, pessimistic lock, or owner serialization. Capacity: assumptions, measurement, threshold, response when exceeded.
- Migrations: ordered, recorded, same sequence in all environments; test data isolated. Expand, migrate, contract; prefer optional fields; removal or rename needs multi-release transition.
- Old and new app versions compatible on the same schema during rolling deploy. Data migrations: batched, idempotent, resumable, validated, with rollback or forward-fix.
- Per step: deploy order (schema before, with, or after app). Lock duration limit, timeout policy, mid-migration failure handling.
- Every schema change: compatibility window and rollback or forward-fix path. Backup/recovery: frequency, retention, restore test, RPO and RTO per context.
- Each context owns its tables or collections; destructive changes need named approval. No two contexts write the same table or collection unless recorded as shared kernel or published contract.

## Data Contract

## Data Contract Keys
Writer payload (types inline):
`{drivers:{invariants[],read_write_patterns[],volume_growth_retention[]}, paradigm:{selected,rationale,rejected[],change_conditions[]}, data_model:[{concept,persistence_form,consistency_boundary,enforced_invariants[],duplicated:bool,concurrency,sensitivity}], query_performance:[{query,caller,frequency,latency_target,served_by,access_path,staleness,bounded:bool}], capacity:{assumptions[],measurements[]}, migration:[{step,change_type:expand|migrate|contract|backfill,compatible_prev:bool,deploy_order,rollback_or_forward_fix,validation}], rpo_rto:{rpo,rto}, risks:[{item,type,impact,confidence}]}`

## DAG Handoff
Translate into `T-xxx` tasks for `task-decomposition-dag`:
- Stores and schema migrations: `layer: infrastructure`, before domain/application tasks that query them.
- Derived read models or projections: `layer: infrastructure`, depend on source-of-truth event/contract tasks.
- Tech tools (e.g. Flyway, PostgreSQL) only in task `intent`/`ast_hints`, never in the strategy.
