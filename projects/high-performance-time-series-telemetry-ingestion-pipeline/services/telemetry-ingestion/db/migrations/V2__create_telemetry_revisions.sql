CREATE TABLE IF NOT EXISTS telemetry_revisions (
    revision_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    record_id       BIGINT        NOT NULL,
    revision_number INTEGER       NOT NULL,
    sample_value    DOUBLE PRECISION NOT NULL,
    reason          VARCHAR(64)   NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT fk_telemetry_revisions_record FOREIGN KEY (record_id) REFERENCES telemetry_records (record_id),
    CONSTRAINT ck_telemetry_revisions_number CHECK (revision_number >= 1)
);

-- Latest-revision lookup per record.
CREATE UNIQUE INDEX IF NOT EXISTS ux_telemetry_revisions_record_number
    ON telemetry_revisions (record_id, revision_number);
