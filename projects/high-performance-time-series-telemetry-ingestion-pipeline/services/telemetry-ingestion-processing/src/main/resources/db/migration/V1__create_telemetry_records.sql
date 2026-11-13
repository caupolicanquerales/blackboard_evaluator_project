CREATE TABLE IF NOT EXISTS telemetry_records (
    device_id         VARCHAR(128)     NOT NULL,
    metric            VARCHAR(128)     NOT NULL,
    t_device          TIMESTAMP WITH TIME ZONE NOT NULL,
    revision          INTEGER          NOT NULL DEFAULT 0,
    "value"           DOUBLE PRECISION,
    validation_status VARCHAR(32)      NOT NULL,
    t_ingress         TIMESTAMP WITH TIME ZONE NOT NULL,
    version           INTEGER          NOT NULL DEFAULT 0,
    CONSTRAINT pk_telemetry_records PRIMARY KEY (device_id, metric, t_device, revision),
    CONSTRAINT ck_telemetry_records_revision CHECK (revision >= 0)
);

CREATE INDEX IF NOT EXISTS ix_telemetry_records_sample_revision
    ON telemetry_records (device_id, metric, t_device, revision);
