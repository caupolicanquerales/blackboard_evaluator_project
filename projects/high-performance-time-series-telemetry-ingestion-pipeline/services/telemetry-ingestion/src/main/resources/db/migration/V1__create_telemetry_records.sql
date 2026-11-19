CREATE TABLE IF NOT EXISTS telemetry_records (
    record_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id         VARCHAR(128)  NOT NULL,
    metric            VARCHAR(64)   NOT NULL,
    t_device          TIMESTAMP WITH TIME ZONE NOT NULL,
    t_ingress         TIMESTAMP WITH TIME ZONE NOT NULL,
    sample_value      DOUBLE PRECISION NOT NULL,
    validation_status VARCHAR(32)   NOT NULL,
    payload_hash      VARCHAR(64)   NOT NULL,
    payload           TEXT,
    version           INTEGER       NOT NULL DEFAULT 0,
    CONSTRAINT ck_telemetry_records_status CHECK (validation_status IN ('VALIDATED', 'VALIDATION_FAILED'))
);

-- Dedup identity: value excluded; payload_hash separates a correction from a retry.
CREATE UNIQUE INDEX IF NOT EXISTS ux_telemetry_records_identity
    ON telemetry_records (device_id, metric, t_device, payload_hash);
