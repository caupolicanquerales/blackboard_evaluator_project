# Backup and recovery

- `telemetry_record` and `audit_trail` are append-only: the application never
  updates or deletes rows, so history is replayable from the tables.
- Operator-level: scheduled full database backups (PostgreSQL `pg_dump` or
  base backups) plus WAL archiving for point-in-time recovery.
- Restore: recover to the target time, then start the service; Flyway
  validates the history table and applies only pending expand-only scripts.
- Downstream analytics replay by `t_device` range read after recovery;
  consumers must be idempotent (duplicate revisions are possible).
- No in-app deletion or retention job exists; retention is an operator decision.
