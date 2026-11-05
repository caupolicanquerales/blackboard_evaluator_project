-- Columnar compression for cold chunks. Compressed chunks remain readable for
-- audit range scans by device and t_device. Retention is deliberately not set
-- (open question in strategy); add a retention policy in a later expand step.
ALTER TABLE telemetry_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby = 't_device DESC, revision DESC'
);

SELECT add_compression_policy('telemetry_events', INTERVAL '7 days', if_not_exists => TRUE);
