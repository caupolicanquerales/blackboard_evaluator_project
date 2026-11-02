-- Bounded context: compliance-risk (PostgreSQL 16)
-- Screening Result, Compliance Hold, Override Log (append-only), SAR, outbox, idempotency. Expand-only.

CREATE TABLE IF NOT EXISTS compliance_risk.screening_results (
    id               uuid          PRIMARY KEY,
    subject_type     varchar(30)   NOT NULL,
    subject_id       uuid          NOT NULL,
    transaction_id   uuid,
    outcome          varchar(20)   NOT NULL,
    risk_score       numeric(5,2),
    decision_reason  varchar(500),
    version          integer       NOT NULL DEFAULT 0,
    screened_at      timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT ck_screening_results_subject_type CHECK (subject_type IN ('ACCOUNT', 'PAYMENT')),
    CONSTRAINT ck_screening_results_outcome CHECK (outcome IN ('CLEARED', 'FLAGGED', 'SUSPENDED')),
    CONSTRAINT ck_screening_results_risk_score CHECK (risk_score IS NULL OR risk_score >= 0)
);

CREATE TABLE IF NOT EXISTS compliance_risk.compliance_holds (
    id                   uuid         PRIMARY KEY,
    transaction_id       uuid         NOT NULL,
    screening_result_id  uuid         NOT NULL,
    status               varchar(20)  NOT NULL,
    reason               varchar(500),
    version              integer      NOT NULL DEFAULT 0,
    placed_at            timestamptz  NOT NULL DEFAULT now(),
    released_at          timestamptz,
    CONSTRAINT fk_compliance_holds_screening_result FOREIGN KEY (screening_result_id)
        REFERENCES compliance_risk.screening_results (id),
    CONSTRAINT ck_compliance_holds_status CHECK (status IN ('OPEN', 'RELEASED', 'REJECTED'))
);

-- Append-only: rows are never updated or deleted (enforced by trigger below)
CREATE TABLE IF NOT EXISTS compliance_risk.override_logs (
    id                   uuid         PRIMARY KEY,
    compliance_hold_id   uuid         NOT NULL,
    overridden_by        varchar(100) NOT NULL,
    justification        varchar(1000) NOT NULL,
    previous_status      varchar(20)  NOT NULL,
    new_status           varchar(20)  NOT NULL,
    recorded_at          timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT fk_override_logs_hold FOREIGN KEY (compliance_hold_id)
        REFERENCES compliance_risk.compliance_holds (id)
);

CREATE TABLE IF NOT EXISTS compliance_risk.suspicious_activity_reports (
    id                   uuid         PRIMARY KEY,
    screening_result_id  uuid         NOT NULL,
    status               varchar(20)  NOT NULL,
    narrative            text,
    version              integer      NOT NULL DEFAULT 0,
    created_at           timestamptz  NOT NULL DEFAULT now(),
    filed_at             timestamptz,
    CONSTRAINT fk_sars_screening_result FOREIGN KEY (screening_result_id)
        REFERENCES compliance_risk.screening_results (id),
    CONSTRAINT ck_sars_status CHECK (status IN ('DRAFT', 'UNDER_REVIEW', 'FILED'))
);

CREATE TABLE IF NOT EXISTS compliance_risk.outbox_events (
    id             uuid         PRIMARY KEY,
    aggregate_id   uuid         NOT NULL,
    event_type     varchar(100) NOT NULL,
    payload        jsonb        NOT NULL,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    published_at   timestamptz
);

-- Idempotent event consumption (AccountCreated, PaymentRequested)
CREATE TABLE IF NOT EXISTS compliance_risk.processed_events (
    event_id      varchar(100) PRIMARY KEY,
    processed_at  timestamptz  NOT NULL DEFAULT now()
);

-- Access path: open holds by transaction
CREATE INDEX IF NOT EXISTS ix_compliance_holds_open_transaction
    ON compliance_risk.compliance_holds (transaction_id) WHERE status = 'OPEN';

-- Access path: decision history by subject (keyset pagination)
CREATE INDEX IF NOT EXISTS ix_screening_results_subject_screened_id
    ON compliance_risk.screening_results (subject_id, screened_at, id);

-- Override history per hold
CREATE INDEX IF NOT EXISTS ix_override_logs_hold_recorded
    ON compliance_risk.override_logs (compliance_hold_id, recorded_at);

-- Outbox relay reads unpublished events in order
CREATE INDEX IF NOT EXISTS ix_outbox_events_unpublished
    ON compliance_risk.outbox_events (created_at, id) WHERE published_at IS NULL;

-- Immutability of the decision log
CREATE OR REPLACE FUNCTION compliance_risk.reject_override_log_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'override_logs is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_override_logs_append_only
    BEFORE UPDATE OR DELETE ON compliance_risk.override_logs
    FOR EACH ROW EXECUTE FUNCTION compliance_risk.reject_override_log_change();
