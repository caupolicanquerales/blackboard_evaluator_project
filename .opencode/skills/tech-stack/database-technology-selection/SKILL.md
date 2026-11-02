---
name: database-technology-selection
description: Maps the abstract persistence strategy to one concrete storage technology allowed by the project. Use when the database architect must choose a store for a context.
---

# Database Technology Selection

Maps the persistence strategy (`persistence` key) to one allowed storage technology per context. Choose the simplest technology meeting every strategy capability. Never select a product outside the allowed list.

## Allowed technologies

- `PostgreSQL`: default relational store; ACID, invariants, multi-row transactions, joins; `jsonb` for durable single-row schema-less payloads.
- `PostgreSQL + pgvector`: relational data plus embedding similarity in the same transaction.
- `MongoDB`: document aggregates with variable fields, read whole, no cross-document invariants.
- `Redis`: cache, rate limits, sessions, short-lived state, pub/sub, locks; never sole copy of business data unless durability is waived by the strategy.
- `TimescaleDB`: high-rate time-series, retention, time-bucket aggregates; runs on PostgreSQL.
- `Elasticsearch`: full-text, faceted, relevance search; never system of record.
- `S3-compatible object storage`: binary and large files (images, PDFs, documents, audio, video); bytes only. Vendor from tech-stack skill (e.g. self-hosted MinIO in project compose files).
- Out of scope: any capability none of these covers. Record as risk; do not invent a product.

## Decision rules

1. Start from PostgreSQL; switch only when a capability is unmet by it.
2. Relational invariants, multi-row transactions, foreign keys: PostgreSQL.
3. Vector search: pgvector when vectors must stay consistent with domain rows; add Elasticsearch only when keyword and vector search are both required at scale.
4. Flexible document shape, no cross-document invariants: MongoDB.
5. Ephemeral or cache-only data with rebuildable source: Redis. Recovery-critical data stays in the primary store.
6. Time-ordered append-only measurements with retention: TimescaleDB.
7. Search over data owned elsewhere: Elasticsearch as derived index fed from primary store.
8. Multiple technologies only when each owns a distinct capability. Each names its system of record. One store owns each aggregate.
9. Binaries: S3-compatible storage holds bytes; primary store holds one metadata row per object (`object_key`, `content_type`, `size_bytes`, `checksum`, owning aggregate ID). Never binaries in DB columns or Redis.
10. Schema-less payloads: `jsonb` if durable and single-row owned; MongoDB only when the document is the aggregate with its own query surface; Redis only for ephemeral rebuildable keys.

## Performance drivers

Apply after decision rules; each matching driver adds its effect to rationale.

1. Tight write latency or high write rate: Redis or append-only time-series/log; no heavy relational indexes on write path.
2. p99-bound read latency: derived key-value caches or specialized indexes; no raw table scans on read path.
3. High concurrent updates to same row/entity: no relational row locks; use optimistic versioning, event-sourcing append logs, or Redis atomic operations.
4. Payloads above 1 MB at high frequency: S3-compatible offload to protect PostgreSQL buffer pools and Redis memory.
5. Millions of time-stamped events with sliding-window metrics: TimescaleDB continuous aggregates, not runtime `GROUP BY`.

## Output

One record per context:

```json
{
  "context": "<slug>",
  "primary_store": "<allowed technology, version pinned by tech-stack skill>",
  "secondary_stores": [{"capability": "<text>", "store": "<allowed technology>", "system_of_record": false}],
  "performance_drivers": [{"driver": 1-5, "trigger": "<matched strategy fact>", "effect": "<store or pattern added>"}],
  "rationale": ["<one sentence per applied decision rule>"],
  "risks": ["<unmet capability | dual-write concern | consistency gap>"]
}
```

## Constraints

- No SQL dialects, ORM names, or migration tool names; those belong to the concrete migration skill.
- Select only technologies the strategy requires.
- Ambiguous strategy: ask the user before selecting.
