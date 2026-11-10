-- Append-only ledger: revisions add rows, no updates or deletes of raw records
CREATE TABLE IF NOT EXISTS ledger.telemetry_record_events (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    record_id          UUID                     NOT NULL,
    revision_number    INTEGER                  NOT NULL DEFAULT 0,
    device_id          VARCHAR(128)             NOT NULL,
    metric_type        VARCHAR(64)              NOT NULL,
    metric_value       DOUBLE PRECISION,
    device_timestamp   TIMESTAMP WITH TIME ZONE NOT NULL,
    ingress_timestamp  TIMESTAMP WITH TIME ZONE NOT NULL,
    validation_status  ledger.validation_status NOT NULL,
    payload            JSONB,
    revision_reason    ledger.revision_reason   NOT NULL DEFAULT 'ORIGINAL',
    recorded_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT uq_telemetry_record_events_record_revision UNIQUE (record_id, revision_number),
    CONSTRAINT ck_telemetry_record_events_revision_non_negative CHECK (revision_number >= 0),
    CONSTRAINT ck_telemetry_record_events_original_rev0 CHECK (
        (revision_reason = 'ORIGINAL') = (revision_number = 0))
);
