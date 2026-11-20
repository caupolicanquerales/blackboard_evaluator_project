# Backup and recovery: telemetry-ingestion-processing (PostgreSQL)

Tables: `telemetry_sample_events`, `telemetry_revisions`, `audit_trail` (all append-only).

- Snapshots: periodic `pg_dump -Fc` of the telemetry database, plus continuous WAL archiving for point-in-time recovery.
- Restore: restore the latest snapshot, replay WAL to the target timestamp, then start the service; Flyway applies only missing versions.
- Rollback posture: expand-only migrations, so recovery is forward-fix plus backup restore; never drop or rename.
- Derived state: Telemetry Stream Distribution window buffers are in-memory and are rebuilt by replaying events ordered by `t_device`.
- Open: retention period for raw 1Hz history is undecided; no purge is scheduled.
