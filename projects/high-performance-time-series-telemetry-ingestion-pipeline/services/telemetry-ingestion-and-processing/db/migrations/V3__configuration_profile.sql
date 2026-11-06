-- Configuration profile: metric boundary definitions held as data, not code.
CREATE TABLE IF NOT EXISTS telemetry.metric_boundaries (
    metric      TEXT             PRIMARY KEY,
    min_value   DOUBLE PRECISION,
    max_value   DOUBLE PRECISION,
    unit        TEXT,
    version     INTEGER          NOT NULL DEFAULT 0,
    CHECK (min_value IS NULL OR max_value IS NULL OR min_value <= max_value)
);
