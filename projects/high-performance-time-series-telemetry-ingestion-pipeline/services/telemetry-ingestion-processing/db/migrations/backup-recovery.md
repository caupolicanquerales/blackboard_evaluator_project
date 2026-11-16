# Backup and recovery: telemetry history

- Store: PostgreSQL (primary); H2 in PostgreSQL mode is boot/test only and not backed up.
- Periodic base snapshots (pg_basebackup) plus continuous WAL archiving for point-in-time recovery.
- Tables are append-only (telemetry_sample, event_revision, audit_trail); restore to a point in time, then let Flyway validate.
- Derived views are rebuilt by replaying event_revision ordered by (sample_id, revision_no).
