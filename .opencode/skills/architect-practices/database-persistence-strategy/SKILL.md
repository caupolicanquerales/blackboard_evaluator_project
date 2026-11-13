---
name: database-persistence-strategy
description: "Use when designing a bounded context's data layer: storage paradigm, data model, query/performance, migration. Technology-agnostic; no code, DDL, or vendor config."
---
# Scope
Analysis only: no DDL, query text, index syntax, ORM, config, migration scripts, vendors (capability names unless mandated). Missing context => `Open question`; never invent entities/invariants; state confidence.
- Paradigms: relational, document, key-value, wide-column, graph, search, log, cache. Weakest consistency + simplest paradigm meeting the invariants; record drivers, rationale, rejected alternatives, change conditions.
- One store per source-of-truth concept; one engine per context unless measured. Secondary stores are DERIVED (rebuild source + staleness bound).
- One consistency boundary per aggregate; cross-aggregate refs by ID; deliberate denormalization (copy, source, staleness).
- Each invariant: one enforcement layer (store/domain/both, reason if both). Keys, audit markers, optimistic versioning, sensitivity (classification, encryption, masking, retention, deletion) per concept.
- Queries drive access paths: caller, frequency, latency, staleness per read (strong for source of truth; bounded for read models/cache). No unbounded scans/offsets; keyset ordering. Never cache over a missing access path; bound results; archive cold; shard only on measured volume.
- Concurrent writers: optimistic version | pessimistic lock | owner serialization. Capacity: assumptions, measurement, threshold, response when exceeded.
- Migrations: ordered, recorded, expand-only, verification+rollback posture; backup/restore owned; growth/retention/lifecycle planned. Any operational profile fragment for the store MUST use the property namespace the RUNTIME actually reads (per the active tech-stack skill) and name the consuming configuration unit - a settings block in a file no runtime loads is schema fiction. The migration folder and the configured locations must ALIGN: the runner must be pointed at where these scripts physically land.
# Output (strategy `persistence` key)
drivers, storage_paradigm (primary+derived), data_model (concepts, keys, relationships, invariants, versioning, sensitivity), queries, performance, migration_plan, backup_recovery, open_questions.
