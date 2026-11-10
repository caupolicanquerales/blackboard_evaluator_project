---
name: database-technology-selection
description: Maps the abstract persistence strategy to one concrete storage technology allowed by the project. Use when the database architect must choose a store for a context.
---
# Rules
Map `persistence` to ONE primary store per context (+ derived only where a capability is unmet). Simplest technology meeting every invariant/access path; never outside the allowed list; versions from the tech-stack skill.
# Allowed
PostgreSQL - default; ACID, multi-row transactions, joins, invariants; jsonb for durable schema-less payloads. PostgreSQL+pgvector - embeddings consistent with rows in-transaction. MongoDB - document aggregates, variable shape, read-whole, no cross-document invariants. Redis - cache, rate limits, sessions, locks, pub/sub; never the sole copy unless the strategy waives durability. TimescaleDB - high-rate time-series, retention, time buckets (on PostgreSQL). Elasticsearch - full-text/faceted search, DERIVED index fed from the source of truth; never system of record. S3-compatible object storage - bytes only (images/PDF/audio/video); vendor per tech-stack (e.g. MinIO in compose).
# Decisions
Start at PostgreSQL; switch only on a named unmet capability. Vectors consistent with rows => pgvector; keyword+vector both needed at scale => ES as derived. Document-shaped, no cross-doc invariants => MongoDB. Ephemeral/rebuildable => Redis (recovery-critical data stays primary). Time-ordered append-only with retention => TimescaleDB. Search over data owned elsewhere => ES fed by events. Large binary => object store, metadata stays relational.
# Record (per context)
primary store + why; secondary with rebuild source + staleness; performance drivers honored; rejected alternatives with reason; migration tool per tech-stack skill; risks + open questions (capacity, durability gaps, capabilities none of the allowed list covers => explicit risk, never an invented product).
