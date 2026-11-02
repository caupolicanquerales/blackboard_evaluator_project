-- Bounded context: accounts (PostgreSQL 16)
-- Account aggregate (state, overdraft boundary), holds children, outbox. Expand-only.

CREATE TABLE IF NOT EXISTS accounts.accounts (
    id                 uuid         PRIMARY KEY,
    account_number     varchar(34)  NOT NULL,
    state              varchar(20)  NOT NULL,
    currency           char(3)      NOT NULL,
    overdraft_limit    numeric(19,4) NOT NULL DEFAULT 0,
    version            integer      NOT NULL DEFAULT 0,
    created_at         timestamptz  NOT NULL DEFAULT now(),
    updated_at         timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_accounts_account_number UNIQUE (account_number),
    CONSTRAINT ck_accounts_state CHECK (state IN ('PENDING', 'ACTIVE', 'FROZEN', 'CLOSED')),
    CONSTRAINT ck_accounts_overdraft_limit CHECK (overdraft_limit >= 0)
);

CREATE TABLE IF NOT EXISTS accounts.account_holds (
    id           uuid          PRIMARY KEY,
    account_id   uuid          NOT NULL,
    amount       numeric(19,4) NOT NULL,
    reason       varchar(255),
    status       varchar(20)   NOT NULL,
    placed_at    timestamptz   NOT NULL DEFAULT now(),
    released_at  timestamptz,
    CONSTRAINT fk_account_holds_account FOREIGN KEY (account_id) REFERENCES accounts.accounts (id),
    CONSTRAINT ck_account_holds_amount CHECK (amount > 0),
    CONSTRAINT ck_account_holds_status CHECK (status IN ('ACTIVE', 'RELEASED'))
);

CREATE TABLE IF NOT EXISTS accounts.outbox_events (
    id             uuid         PRIMARY KEY,
    aggregate_id   uuid         NOT NULL,
    event_type     varchar(100) NOT NULL,
    payload        jsonb        NOT NULL,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    published_at   timestamptz
);

-- Idempotent event consumption
CREATE TABLE IF NOT EXISTS accounts.processed_events (
    event_id      varchar(100) PRIMARY KEY,
    processed_at  timestamptz  NOT NULL DEFAULT now()
);

-- Access path: accounts by state
CREATE INDEX IF NOT EXISTS ix_accounts_state_id ON accounts.accounts (state, id);

-- Access path: active holds per account
CREATE INDEX IF NOT EXISTS ix_account_holds_active_account
    ON accounts.account_holds (account_id) WHERE status = 'ACTIVE';

-- Outbox relay reads unpublished events in order
CREATE INDEX IF NOT EXISTS ix_outbox_events_unpublished
    ON accounts.outbox_events (created_at, id) WHERE published_at IS NULL;
