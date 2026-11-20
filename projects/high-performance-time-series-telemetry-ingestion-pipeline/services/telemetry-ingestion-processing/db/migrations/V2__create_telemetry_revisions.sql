-- Appended correction/backfill records referencing the untouched original event.
CREATE TABLE IF NOT EXISTS telemetry_revisions (
    revision_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    original_event_id BIGINT NOT NULL,
    revision_number   INTEGER NOT NULL,
    revision_kind     VARCHAR(32) NOT NULL,
    metric_value      DOUBLE PRECISION,
    t_ingress         TIMESTAMP WITH TIME ZONE NOT NULL,
    payload           TEXT NOT NULL,
    CONSTRAINT fk_telemetry_revisions_event FOREIGN KEY (original_event_id) REFERENCES telemetry_sample_events (event_id),
    CONSTRAINT ck_telemetry_revisions_kind CHECK (revision_kind IN ('CORRECTION', 'BACKFILL')),
    CONSTRAINT ck_telemetry_revisions_number CHECK (revision_number >= 1)
);
