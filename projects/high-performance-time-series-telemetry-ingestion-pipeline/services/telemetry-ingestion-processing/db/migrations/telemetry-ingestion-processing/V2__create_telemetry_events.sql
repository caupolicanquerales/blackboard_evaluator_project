-- Telemetry Event Log: immutable raw records (revision 0) and correction revisions (revision > 0).
-- Revisions share (device_id, t_device) with the original record; no FK because
-- hypertables cannot be FK targets.
CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id            uuid         NOT NULL,
    device_id           text         NOT NULL,
    t_device            timestamptz  NOT NULL,
    revision            integer      NOT NULL DEFAULT 0,
    t_ingress           timestamptz  NOT NULL,
    validation_status   text         NOT NULL,
    payload             jsonb,
    original_event_id   uuid,
    version             integer      NOT NULL DEFAULT 0,
    recorded_at         timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_telemetry_events PRIMARY KEY (device_id, t_device, revision),
    CONSTRAINT ck_telemetry_events_revision CHECK (revision >= 0),
    CONSTRAINT ck_telemetry_events_validation_status
        CHECK (validation_status IN ('VALID', 'INVALID')),
    CONSTRAINT ck_telemetry_events_revision_ref
        CHECK ((revision = 0 AND original_event_id IS NULL)
            OR (revision > 0 AND original_event_id IS NOT NULL))
);

SELECT create_hypertable(
    'telemetry_events', 't_device',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Append-only guarantee: reject UPDATE and DELETE.
CREATE OR REPLACE FUNCTION telemetry_events_reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'telemetry_events is append-only (% rejected)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_telemetry_events_append_only'
    ) THEN
        CREATE TRIGGER trg_telemetry_events_append_only
            BEFORE UPDATE OR DELETE ON telemetry_events
            FOR EACH ROW EXECUTE FUNCTION telemetry_events_reject_mutation();
    END IF;
END
$$;
