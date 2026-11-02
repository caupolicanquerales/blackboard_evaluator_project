-- Bounded context: payments (PostgreSQL 16)
-- Payment order state machine, settlement batches, status history, outbox/inbox. Expand-only.

CREATE TABLE IF NOT EXISTS payments.settlement_batches (
    id            uuid          PRIMARY KEY,
    status        varchar(20)   NOT NULL DEFAULT 'OPEN',
    currency      char(3)       NOT NULL,
    total_amount  numeric(19,4) NOT NULL DEFAULT 0,
    settled_at    timestamptz,
    version       integer       NOT NULL DEFAULT 0,
    created_at    timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT ck_settlement_batches_status CHECK (status IN ('OPEN', 'CLOSED', 'SETTLED', 'FAILED')),
    CONSTRAINT ck_settlement_batches_total CHECK (total_amount >= 0)
);

CREATE TABLE IF NOT EXISTS payments.payment_orders (
    id                    uuid          PRIMARY KEY,
    idempotency_key       varchar(100)  NOT NULL,
    debtor_account_id     uuid          NOT NULL,
    creditor_account_id   uuid          NOT NULL,
    amount                numeric(19,4) NOT NULL,
    currency              char(3)       NOT NULL,
    state                 varchar(20)   NOT NULL DEFAULT 'CREATED',
    settlement_batch_id   uuid,
    failure_reason        varchar(255),
    version               integer       NOT NULL DEFAULT 0,
    created_at            timestamptz   NOT NULL DEFAULT now(),
    updated_at            timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT fk_payment_orders_batch FOREIGN KEY (settlement_batch_id) REFERENCES payments.settlement_batches (id),
    CONSTRAINT uq_payment_orders_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT ck_payment_orders_amount CHECK (amount > 0),
    CONSTRAINT ck_payment_orders_accounts CHECK (debtor_account_id <> creditor_account_id),
    CONSTRAINT ck_payment_orders_state CHECK (state IN
        ('CREATED', 'VALIDATED', 'FUNDS_RESERVED', 'BATCHED', 'SETTLED', 'REJECTED', 'FAILED', 'COMPENSATED'))
);

-- Append-only audit trail of state transitions (saga state)
CREATE TABLE IF NOT EXISTS payments.payment_order_transitions (
    id                uuid         PRIMARY KEY,
    payment_order_id  uuid         NOT NULL,
    from_state        varchar(20),
    to_state          varchar(20)  NOT NULL,
    reason            varchar(255),
    occurred_at       timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT fk_payment_order_transitions_order FOREIGN KEY (payment_order_id) REFERENCES payments.payment_orders (id)
);

CREATE TABLE IF NOT EXISTS payments.outbox_events (
    id             uuid         PRIMARY KEY,
    aggregate_id   uuid         NOT NULL,
    event_type     varchar(100) NOT NULL,
    payload        jsonb        NOT NULL,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    published_at   timestamptz
);

-- Inbox: idempotent event consumption
CREATE TABLE IF NOT EXISTS payments.inbox_events (
    event_id      varchar(100) PRIMARY KEY,
    event_type    varchar(100) NOT NULL,
    processed_at  timestamptz  NOT NULL DEFAULT now()
);

-- Access path: orders by state
CREATE INDEX IF NOT EXISTS ix_payment_orders_state_created_id
    ON payments.payment_orders (state, created_at, id);

-- Access path: batch members
CREATE INDEX IF NOT EXISTS ix_payment_orders_batch
    ON payments.payment_orders (settlement_batch_id, id);

CREATE INDEX IF NOT EXISTS ix_payment_order_transitions_order
    ON payments.payment_order_transitions (payment_order_id, occurred_at);

-- Outbox relay reads unpublished events in order
CREATE INDEX IF NOT EXISTS ix_outbox_events_unpublished
    ON payments.outbox_events (created_at, id) WHERE published_at IS NULL;
