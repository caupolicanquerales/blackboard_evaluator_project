CREATE TABLE IF NOT EXISTS telemetry.telemetry_record_revisions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id VARCHAR(128) NOT NULL,
    metric_type VARCHAR(64) NOT NULL,
    t_device TIMESTAMP WITH TIME ZONE NOT NULL,
    t_ingress TIMESTAMP WITH TIME ZONE NOT NULL,
    metric_value DOUBLE PRECISION,
    validation_status VARCHAR(32) NOT NULL,
    revision INTEGER NOT NULL,
    revision_reason VARCHAR(16) NOT NULL,
    CONSTRAINT uq_telemetry_record_revisions_sample_revision
        UNIQUE (device_id, metric_type, t_device, revision),
    CONSTRAINT ck_telemetry_record_revisions_revision CHECK (revision >= 1),
    CONSTRAINT ck_telemetry_record_revisions_reason
        CHECK (revision_reason IN ('ORIGINAL', 'CORRECTION', 'BACKFILL')),
    CONSTRAINT ck_telemetry_record_revisions_status
        CHECK (validation_status IN ('VALID', 'VALIDATION_FAILED'))
);

CREATE INDEX IF NOT EXISTS ix_telemetry_record_revisions_device_t_device
    ON telemetry.telemetry_record_revisions (device_id, t_device);
