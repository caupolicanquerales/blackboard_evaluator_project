-- Append-only ledger: corrections append a new revision row; no UPDATE/DELETE.
CREATE TABLE IF NOT EXISTS ledger.telemetry_records (
    id                UUID             PRIMARY KEY,
    device_id         VARCHAR(128)     NOT NULL,
    metric            VARCHAR(128)     NOT NULL,
    value             DOUBLE PRECISION NOT NULL,
    t_device          TIMESTAMPTZ      NOT NULL,
    t_ingress         TIMESTAMPTZ      NOT NULL,
    validation_status VARCHAR(32)      NOT NULL,
    revision          INTEGER          NOT NULL DEFAULT 0 CHECK (revision >= 0),
    supersedes_id     UUID             NULL REFERENCES ledger.telemetry_records (id),
    version           INTEGER          NOT NULL DEFAULT 0,
    CONSTRAINT uq_telemetry_records_sample_revision UNIQUE (device_id, metric, t_device, revision)
);

-- history by device and t_device range ordered by t_device
CREATE INDEX IF NOT EXISTS ix_telemetry_records_device_t_device
    ON ledger.telemetry_records (device_id, t_device);

-- revision audit chain
CREATE INDEX IF NOT EXISTS ix_telemetry_records_supersedes
    ON ledger.telemetry_records (supersedes_id) WHERE supersedes_id IS NOT NULL;

-- enforce append-only
CREATE OR REPLACE FUNCTION ledger.forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'telemetry_records is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_telemetry_records_append_only ON ledger.telemetry_records;
CREATE TRIGGER trg_telemetry_records_append_only
    BEFORE UPDATE OR DELETE ON ledger.telemetry_records
    FOR EACH ROW EXECUTE FUNCTION ledger.forbid_mutation();
