-- Bounded context: treasury-fx (PostgreSQL 16)
-- Exchange rate quotes (time-bounded), FX conversions, treasury positions, outbox/inbox. Expand-only.

CREATE TABLE IF NOT EXISTS treasury_fx.exchange_rate_quotes (
    id              uuid           PRIMARY KEY,
    base_currency   char(3)        NOT NULL,
    quote_currency  char(3)        NOT NULL,
    rate            numeric(19,8)  NOT NULL,
    valid_from      timestamptz    NOT NULL,
    valid_until     timestamptz    NOT NULL,
    status          varchar(20)    NOT NULL DEFAULT 'ACTIVE',
    provider        varchar(100),
    version         integer        NOT NULL DEFAULT 0,
    created_at      timestamptz    NOT NULL DEFAULT now(),
    CONSTRAINT ck_exchange_rate_quotes_rate CHECK (rate > 0),
    CONSTRAINT ck_exchange_rate_quotes_currencies CHECK (base_currency <> quote_currency),
    CONSTRAINT ck_exchange_rate_quotes_validity CHECK (valid_until > valid_from),
    CONSTRAINT ck_exchange_rate_quotes_status CHECK (status IN ('ACTIVE', 'EXPIRED', 'CONSUMED', 'REVOKED'))
);

CREATE TABLE IF NOT EXISTS treasury_fx.fx_conversions (
    id                uuid           PRIMARY KEY,
    idempotency_key   varchar(100)   NOT NULL,
    quote_id          uuid           NOT NULL,
    source_currency   char(3)        NOT NULL,
    target_currency   char(3)        NOT NULL,
    source_amount     numeric(19,4)  NOT NULL,
    target_amount     numeric(19,4)  NOT NULL,
    applied_rate      numeric(19,8)  NOT NULL,
    status            varchar(20)    NOT NULL DEFAULT 'EXECUTED',
    version           integer        NOT NULL DEFAULT 0,
    created_at        timestamptz    NOT NULL DEFAULT now(),
    CONSTRAINT fk_fx_conversions_quote FOREIGN KEY (quote_id) REFERENCES treasury_fx.exchange_rate_quotes (id),
    CONSTRAINT uq_fx_conversions_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT ck_fx_conversions_source_amount CHECK (source_amount > 0),
    CONSTRAINT ck_fx_conversions_target_amount CHECK (target_amount > 0),
    CONSTRAINT ck_fx_conversions_rate CHECK (applied_rate > 0),
    CONSTRAINT ck_fx_conversions_currencies CHECK (source_currency <> target_currency),
    CONSTRAINT ck_fx_conversions_status CHECK (status IN ('EXECUTED', 'REVERSED'))
);

CREATE TABLE IF NOT EXISTS treasury_fx.treasury_positions (
    id          uuid           PRIMARY KEY,
    currency    char(3)        NOT NULL,
    balance     numeric(19,4)  NOT NULL DEFAULT 0,
    version     integer        NOT NULL DEFAULT 0,
    updated_at  timestamptz    NOT NULL DEFAULT now(),
    CONSTRAINT uq_treasury_positions_currency UNIQUE (currency)
);

-- Append-only audit trail of position movements
CREATE TABLE IF NOT EXISTS treasury_fx.position_movements (
    id             uuid           PRIMARY KEY,
    position_id    uuid           NOT NULL,
    conversion_id  uuid,
    amount         numeric(19,4)  NOT NULL,
    occurred_at    timestamptz    NOT NULL DEFAULT now(),
    CONSTRAINT fk_position_movements_position FOREIGN KEY (position_id) REFERENCES treasury_fx.treasury_positions (id),
    CONSTRAINT fk_position_movements_conversion FOREIGN KEY (conversion_id) REFERENCES treasury_fx.fx_conversions (id)
);

CREATE TABLE IF NOT EXISTS treasury_fx.outbox_events (
    id            uuid          PRIMARY KEY,
    aggregate_id  uuid          NOT NULL,
    event_type    varchar(100)  NOT NULL,
    payload       jsonb         NOT NULL,
    created_at    timestamptz   NOT NULL DEFAULT now(),
    published_at  timestamptz
);

-- Inbox: idempotent event consumption
CREATE TABLE IF NOT EXISTS treasury_fx.inbox_events (
    event_id      varchar(100)  PRIMARY KEY,
    event_type    varchar(100)  NOT NULL,
    processed_at  timestamptz   NOT NULL DEFAULT now()
);

-- Access path: active quote by id is served by the primary key; validity filtering by pair
CREATE INDEX IF NOT EXISTS ix_exchange_rate_quotes_active_pair
    ON treasury_fx.exchange_rate_quotes (base_currency, quote_currency, valid_until)
    WHERE status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS ix_fx_conversions_quote
    ON treasury_fx.fx_conversions (quote_id);

-- Access path: position by currency is served by uq_treasury_positions_currency
CREATE INDEX IF NOT EXISTS ix_position_movements_position
    ON treasury_fx.position_movements (position_id, occurred_at, id);

CREATE INDEX IF NOT EXISTS ix_outbox_events_unpublished
    ON treasury_fx.outbox_events (created_at, id) WHERE published_at IS NULL;
