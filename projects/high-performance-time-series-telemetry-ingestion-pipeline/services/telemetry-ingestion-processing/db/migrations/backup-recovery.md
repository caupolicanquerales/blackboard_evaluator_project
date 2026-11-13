# Backup and recovery: telemetry-ingestion-processing (PostgreSQL)

- Platform-level periodic snapshots of the database plus WAL/log-based point-in-time recovery.
- Migrations are expand-only: rollback = forward-fix migration or restore from snapshot.
- `telemetry_records` and `audit_trail` are append-only, so replaying the log after a restore is safe and idempotent on the key (device_id, metric, t_device, revision).
- Verify: restore into a scratch instance and run Flyway `validate` plus a row-count check.
- Open: retention period and partitioning of raw history.
