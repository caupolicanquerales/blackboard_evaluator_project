-- Only the indexes required by the strategy's query paths (write-heavy table).
-- Q1: history by device and device-timestamp range ordered by t_device
CREATE INDEX IF NOT EXISTS ix_telemetry_record_events_device_time
    ON ledger.telemetry_record_events (device_id, device_timestamp, id);
-- Q2 (revisions of one record) is served by uq_telemetry_record_events_record_revision.
-- Q3: latest effective revision per record
CREATE INDEX IF NOT EXISTS ix_telemetry_record_events_record_latest
    ON ledger.telemetry_record_events (record_id, revision_number DESC);
