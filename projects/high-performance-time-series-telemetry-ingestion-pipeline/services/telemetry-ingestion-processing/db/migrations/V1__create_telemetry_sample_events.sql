-- Append-only raw sample log owned by Telemetry Ingestion. Never updated or deleted.
CREATE TABLE IF NOT EXISTS telemetry_sample_events (
    event_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id         VARCHAR(128) NOT NULL,
    metric_kind       VARCHAR(64) NOT NULL,
    metric_value      DOUBLE PRECISION,
    t_device          TIMESTAMP WITH TIME ZONE NOT NULL,
    t_ingress         TIMESTAMP WITH TIME ZONE NOT NULL,
    validation_status VARCHAR(32) NOT NULL,
    revision_number   INTEGER NOT NULL DEFAULT 0,
    revision_kind     VARCHAR(32) NOT NULL DEFAULT 'ORIGINAL',
    payload           TEXT NOT NULL,
    CONSTRAINT ck_telemetry_sample_events_status CHECK (validation_status IN ('VALID', 'VALIDATION_FAILED')),
    CONSTRAINT ck_telemetry_sample_events_kind CHECK (revision_kind IN ('ORIGINAL', 'CORRECTION', 'BACKFILL')),
    CONSTRAINT ck_telemetry_sample_events_revision CHECK (revision_number >= 0)
);
