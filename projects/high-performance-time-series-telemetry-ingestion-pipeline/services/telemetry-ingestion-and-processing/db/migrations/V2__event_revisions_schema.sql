-- Append-only Event Revision ledger, range-partitioned by device timestamp.
CREATE TABLE IF NOT EXISTS telemetry.event_revisions (
    device_id         TEXT             NOT NULL,
    metric            TEXT             NOT NULL,
    t_device          TIMESTAMPTZ      NOT NULL,
    revision_number   INTEGER          NOT NULL CHECK (revision_number >= 1),
    t_ingress         TIMESTAMPTZ      NOT NULL,
    validation_status TEXT             NOT NULL,
    value             DOUBLE PRECISION,
    raw_payload       JSONB            NOT NULL,
    version           INTEGER          NOT NULL DEFAULT 0,
    PRIMARY KEY (device_id, metric, t_device, revision_number)
) PARTITION BY RANGE (t_device);

-- Catch-all so writes never fail; finer partitions are added by later migrations.
CREATE TABLE IF NOT EXISTS telemetry.event_revisions_default
    PARTITION OF telemetry.event_revisions DEFAULT;

-- Never update or delete revisions.
CREATE OR REPLACE FUNCTION telemetry.reject_revision_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'event_revisions is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS event_revisions_append_only ON telemetry.event_revisions;
CREATE TRIGGER event_revisions_append_only
    BEFORE UPDATE OR DELETE ON telemetry.event_revisions
    FOR EACH ROW EXECUTE FUNCTION telemetry.reject_revision_mutation();

-- The primary key (device_id, metric, t_device, revision_number) serves append,
-- time-range history and latest-revision (backward scan) access paths.
