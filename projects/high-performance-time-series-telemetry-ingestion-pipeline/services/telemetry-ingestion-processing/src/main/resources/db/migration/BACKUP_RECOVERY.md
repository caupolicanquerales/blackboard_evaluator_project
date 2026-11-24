# Backup and recovery - telemetry event log (PostgreSQL)

Owner: platform operations. Tables: `telemetry_records`, `telemetry_event_revisions`, `audit_trail` (all append-only).

- Backup: periodic logical dump (`pg_dump --format=custom`) of the three tables plus `flyway_schema_history`; retain per data-classification policy (athlete biometric data: encrypt at rest, restrict access).
- Recovery: restore the latest dump into an empty database, then start the service so Flyway applies any newer `V<n>__*.sql` scripts. Records newer than the dump are replayed from upstream devices/log shipper; history is append-only, so replay only appends.
- Rollback posture: expand-only migrations; fix forward with a new script, or restore from backup. Never edit an applied script.
- The in-memory reordering window is transient and rebuilt from `telemetry_records`.
