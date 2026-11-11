-- Append-only: no updates/deletes are issued by the application.
CREATE TABLE IF NOT EXISTS telemetry_event_log.telemetry_records (
    device_id          VARCHAR(128)     NOT NULL,
    metric             VARCHAR(128)     NOT NULL,
    t_device           TIMESTAMPTZ      NOT NULL,
    value              DOUBLE PRECISION,
    validation_status  VARCHAR(32)      NOT NULL,
    t_ingress          TIMESTAMPTZ      NOT NULL,
    version            BIGINT           NOT NULL DEFAULT 0,
    -- sample identity makes append idempotent (at-least-once delivery)
    CONSTRAINT pk_telemetry_records PRIMARY KEY (device_id, metric, t_device),
    CONSTRAINT ck_telemetry_records_status CHECK (validation_status IN ('VALID', 'INVALID'))
);

CREATE TABLE IF NOT EXISTS telemetry_event_log.telemetry_record_revisions (
    revision_id        BIGINT GENERATED ALWAYS AS IDENTITY,
    device_id          VARCHAR(128)     NOT NULL,
    metric             VARCHAR(128)     NOT NULL,
    t_device           TIMESTAMPTZ      NOT NULL,
    value              DOUBLE PRECISION,
    reason             VARCHAR(64)      NOT NULL,
    t_revised          TIMESTAMPTZ      NOT NULL,
    version            BIGINT           NOT NULL DEFAULT 0,
    CONSTRAINT pk_telemetry_record_revisions PRIMARY KEY (revision_id),
    CONSTRAINT fk_revisions_record FOREIGN KEY (device_id, metric, t_device)
        REFERENCES telemetry_event_log.telemetry_records (device_id, metric, t_device)
);

-- Query: read revisions by device and t_device range (records are covered by the PK).
CREATE INDEX IF NOT EXISTS ix_telemetry_record_revisions_device_t_device
    ON telemetry_event_log.telemetry_record_revisions (device_id, t_device, revision_id);
