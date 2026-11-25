# Backup and recovery - telemetry-ingestion-processing

Store: PostgreSQL (relational, append-only). Embedded H2 is boot/test only.

- Backup: operator-owned periodic full backup plus WAL archiving for point-in-time restore of `raw_telemetry_records`, `event_revisions`, `audit_trail`.
- Restore: restore the latest backup, replay WAL to the target time, then start the application; Flyway applies any missing `V<n>__*.sql` forward.
- Rollback: no down-scripts; migrations are expand-only, so recovery is forward-fix or restore from backup.
- Verification: compare row counts and `max(revision_number)` per (device_id, metric, t_device) between backup and restored store; the data is append-only so counts never decrease.
- Derived state: the distribution sliding window is in-memory and rebuilt from new events; nothing to restore.
- Open: retention/archival period and capacity sizing are operator decisions.
