CREATE TABLE telemetry_record (
    device_id         VARCHAR(128)             NOT NULL,
    metric            VARCHAR(64)              NOT NULL,
    t_device          TIMESTAMP WITH TIME ZONE NOT NULL,
    revision          INTEGER                  NOT NULL,
    t_ingress         TIMESTAMP WITH TIME ZONE NOT NULL,
    sample_value      DOUBLE PRECISION         NOT NULL,
    validation_status VARCHAR(32)              NOT NULL,
    version           INTEGER                  NOT NULL DEFAULT 0,
    CONSTRAINT pk_telemetry_record PRIMARY KEY (device_id, metric, t_device, revision),
    CONSTRAINT ck_telemetry_record_revision CHECK (revision >= 0)
);

CREATE INDEX ix_telemetry_record_range ON telemetry_record (t_device, device_id, metric);
