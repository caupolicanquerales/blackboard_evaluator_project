CREATE INDEX idx_telemetry_records_device_metric_t_device
    ON telemetry_records (device_id, metric, t_device, id);
