-- Append-only audit entries written through the application audit port.
CREATE TABLE IF NOT EXISTS audit_trail (
    audit_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor          VARCHAR(128) NOT NULL,
    action         VARCHAR(64) NOT NULL,
    outcome        VARCHAR(32) NOT NULL,
    occurred_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    correlation_id VARCHAR(128) NOT NULL,
    CONSTRAINT ck_audit_trail_action CHECK (action IN ('INGEST_PACKET', 'VALIDATE_SAMPLE', 'APPEND_REVISION', 'BROADCAST_WINDOW', 'SUBSCRIBE_STREAM')),
    CONSTRAINT ck_audit_trail_outcome CHECK (outcome IN ('SUCCESS', 'VALIDATION_FAILED', 'REJECTED', 'ERROR'))
);
