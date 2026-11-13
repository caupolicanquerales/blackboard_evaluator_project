CREATE TABLE IF NOT EXISTS audit_trail (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor          VARCHAR(128) NOT NULL,
    action         VARCHAR(128) NOT NULL,
    outcome        VARCHAR(64)  NOT NULL,
    occurred_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    correlation_id VARCHAR(128) NOT NULL
);
