CREATE TABLE IF NOT EXISTS history_entries (
    session_id     VARCHAR(64)  NOT NULL,
    turn_id        VARCHAR(64)  NOT NULL,
    entry_sequence INTEGER      NOT NULL,
    kind           VARCHAR(16)  NOT NULL,
    content        TEXT         NOT NULL,
    token_count    INTEGER      NOT NULL,
    recorded_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, turn_id, entry_sequence),
    CONSTRAINT ck_history_entries_kind CHECK (kind IN ('USER_MESSAGE', 'TOOL_CALL', 'ASSISTANT_REPLY')),
    CONSTRAINT ck_history_entries_sequence CHECK (entry_sequence >= 0),
    CONSTRAINT ck_history_entries_tokens CHECK (token_count >= 0)
);

CREATE TABLE IF NOT EXISTS token_usage_records (
    session_id        VARCHAR(64) NOT NULL,
    turn_id           VARCHAR(64) NOT NULL,
    tenant_id         VARCHAR(64) NOT NULL,
    prompt_tokens     INTEGER     NOT NULL,
    completion_tokens INTEGER     NOT NULL,
    PRIMARY KEY (session_id, turn_id),
    CONSTRAINT ck_token_usage_records_prompt CHECK (prompt_tokens >= 0),
    CONSTRAINT ck_token_usage_records_completion CHECK (completion_tokens >= 0)
);

CREATE INDEX IF NOT EXISTS idx_token_usage_records_tenant ON token_usage_records (tenant_id);
