-- Serves: events per device/metric ordered by t_device, reorder-window reads, latest revision per (device, metric, t_device).
CREATE INDEX IF NOT EXISTS ix_telemetry_sample_events_device_metric_t_device
    ON telemetry_sample_events (device_id, metric_kind, t_device);

-- Serves: latest revision lookup per original event.
CREATE INDEX IF NOT EXISTS ix_telemetry_revisions_original_event
    ON telemetry_revisions (original_event_id, revision_number);
