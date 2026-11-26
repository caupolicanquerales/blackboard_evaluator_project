CREATE TABLE IF NOT EXISTS rolling_summaries (
    session_id         VARCHAR(64) NOT NULL PRIMARY KEY,
    summary_text       TEXT        NOT NULL DEFAULT '',
    last_applied_turn_id VARCHAR(64),
    token_count        INTEGER     NOT NULL DEFAULT 0,
    version            INTEGER     NOT NULL DEFAULT 0,
    CONSTRAINT ck_rolling_summaries_tokens CHECK (token_count >= 0 AND token_count <= 16000)
);

CREATE TABLE IF NOT EXISTS context_messages (
    session_id  VARCHAR(64) NOT NULL,
    turn_id     VARCHAR(64) NOT NULL,
    sequence    INTEGER     NOT NULL,
    role        VARCHAR(16) NOT NULL,
    content     TEXT        NOT NULL,
    token_count INTEGER     NOT NULL,
    PRIMARY KEY (session_id, turn_id, sequence),
    CONSTRAINT ck_context_messages_role CHECK (role IN ('USER', 'ASSISTANT', 'TOOL')),
    CONSTRAINT ck_context_messages_sequence CHECK (sequence >= 0),
    CONSTRAINT ck_context_messages_tokens CHECK (token_count >= 0)
);
