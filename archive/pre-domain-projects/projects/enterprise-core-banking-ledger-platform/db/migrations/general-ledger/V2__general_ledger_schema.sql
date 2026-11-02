-- Bounded context: general-ledger (PostgreSQL 16)
-- Chart of accounts, fiscal periods, append-only journal, balance projection, outbox. Expand-only.

CREATE TABLE IF NOT EXISTS general_ledger.ledger_accounts (
    id            uuid         PRIMARY KEY,
    code          varchar(34)  NOT NULL,
    name          varchar(255) NOT NULL,
    account_type  varchar(20)  NOT NULL,
    currency      char(3)      NOT NULL,
    version       integer      NOT NULL DEFAULT 0,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_ledger_accounts_code UNIQUE (code),
    CONSTRAINT ck_ledger_accounts_type CHECK (account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE'))
);

CREATE TABLE IF NOT EXISTS general_ledger.fiscal_periods (
    id          uuid         PRIMARY KEY,
    name        varchar(50)  NOT NULL,
    start_date  date         NOT NULL,
    end_date    date         NOT NULL,
    status      varchar(20)  NOT NULL DEFAULT 'OPEN',
    closed_at   timestamptz,
    version     integer      NOT NULL DEFAULT 0,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_fiscal_periods_name UNIQUE (name),
    CONSTRAINT ck_fiscal_periods_status CHECK (status IN ('OPEN', 'CLOSED')),
    CONSTRAINT ck_fiscal_periods_dates CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS general_ledger.journal_entries (
    id                    uuid         PRIMARY KEY,
    fiscal_period_id      uuid         NOT NULL,
    status                varchar(20)  NOT NULL,
    description           varchar(255),
    reverses_entry_id     uuid,
    source_event_id       varchar(100),
    posted_at             timestamptz  NOT NULL DEFAULT now(),
    version               integer      NOT NULL DEFAULT 0,
    CONSTRAINT fk_journal_entries_period FOREIGN KEY (fiscal_period_id) REFERENCES general_ledger.fiscal_periods (id),
    CONSTRAINT fk_journal_entries_reverses FOREIGN KEY (reverses_entry_id) REFERENCES general_ledger.journal_entries (id),
    CONSTRAINT uq_journal_entries_source_event UNIQUE (source_event_id),
    CONSTRAINT uq_journal_entries_reverses UNIQUE (reverses_entry_id),
    CONSTRAINT ck_journal_entries_status CHECK (status IN ('PENDING', 'POSTED'))
);

CREATE TABLE IF NOT EXISTS general_ledger.journal_lines (
    id                 uuid          PRIMARY KEY,
    journal_entry_id   uuid          NOT NULL,
    line_number        integer       NOT NULL,
    ledger_account_id  uuid          NOT NULL,
    direction          char(1)       NOT NULL,
    amount             numeric(19,4) NOT NULL,
    currency           char(3)       NOT NULL,
    CONSTRAINT fk_journal_lines_entry FOREIGN KEY (journal_entry_id) REFERENCES general_ledger.journal_entries (id),
    CONSTRAINT fk_journal_lines_account FOREIGN KEY (ledger_account_id) REFERENCES general_ledger.ledger_accounts (id),
    CONSTRAINT uq_journal_lines_entry_line UNIQUE (journal_entry_id, line_number),
    CONSTRAINT ck_journal_lines_direction CHECK (direction IN ('D', 'C')),
    CONSTRAINT ck_journal_lines_amount CHECK (amount > 0)
);

-- Balance projection (derived; rebuildable from the journal)
CREATE TABLE IF NOT EXISTS general_ledger.account_balances (
    ledger_account_id  uuid          NOT NULL,
    fiscal_period_id   uuid          NOT NULL,
    debit_total        numeric(19,4) NOT NULL DEFAULT 0,
    credit_total       numeric(19,4) NOT NULL DEFAULT 0,
    version            integer       NOT NULL DEFAULT 0,
    updated_at         timestamptz   NOT NULL DEFAULT now(),
    PRIMARY KEY (ledger_account_id, fiscal_period_id),
    CONSTRAINT fk_account_balances_account FOREIGN KEY (ledger_account_id) REFERENCES general_ledger.ledger_accounts (id),
    CONSTRAINT fk_account_balances_period FOREIGN KEY (fiscal_period_id) REFERENCES general_ledger.fiscal_periods (id),
    CONSTRAINT ck_account_balances_totals CHECK (debit_total >= 0 AND credit_total >= 0)
);

CREATE TABLE IF NOT EXISTS general_ledger.outbox_events (
    id             uuid         PRIMARY KEY,
    aggregate_id   uuid         NOT NULL,
    event_type     varchar(100) NOT NULL,
    payload        jsonb        NOT NULL,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    published_at   timestamptz
);

-- Idempotent event consumption
CREATE TABLE IF NOT EXISTS general_ledger.processed_events (
    event_id      varchar(100) PRIMARY KEY,
    processed_at  timestamptz  NOT NULL DEFAULT now()
);

-- Access path: journal by period
CREATE INDEX IF NOT EXISTS ix_journal_entries_period_posted_id
    ON general_ledger.journal_entries (fiscal_period_id, posted_at, id);

-- Access paths: balance by account, trial balance
CREATE INDEX IF NOT EXISTS ix_journal_lines_account_entry
    ON general_ledger.journal_lines (ledger_account_id, journal_entry_id);

CREATE INDEX IF NOT EXISTS ix_account_balances_period
    ON general_ledger.account_balances (fiscal_period_id);

-- Outbox relay reads unpublished events in order
CREATE INDEX IF NOT EXISTS ix_outbox_events_unpublished
    ON general_ledger.outbox_events (created_at, id) WHERE published_at IS NULL;
