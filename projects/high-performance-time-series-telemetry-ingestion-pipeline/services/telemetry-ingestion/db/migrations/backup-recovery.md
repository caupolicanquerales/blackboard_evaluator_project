# Backup and recovery - telemetry-ingestion (PostgreSQL)

- Append-only history (telemetry_records, telemetry_revisions, audit_trail) is the source of truth.
- Backup: scheduled base snapshots plus continuous WAL archiving (PITR) of the production database.
- Recovery: restore the latest snapshot, replay WAL to the target time, then run Flyway (forward-only).
- Rollback posture: expand-only migrations; fix forward with a new V<n> script, never edit applied scripts.
