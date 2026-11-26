CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id    VARCHAR(64) NOT NULL PRIMARY KEY,
    owner_user_id VARCHAR(64) NOT NULL,
    tenant_id     VARCHAR(64) NOT NULL,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version       INTEGER     NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS turns (
    turn_id         VARCHAR(64) NOT NULL PRIMARY KEY,
    session_id      VARCHAR(64) NOT NULL,
    state           VARCHAR(32) NOT NULL,
    tool_call_count INTEGER     NOT NULL DEFAULT 0,
    started_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version         INTEGER     NOT NULL DEFAULT 0,
    CONSTRAINT fk_turns_session FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id),
    CONSTRAINT ck_turns_tool_calls CHECK (tool_call_count >= 0 AND tool_call_count <= 5)
);

CREATE INDEX IF NOT EXISTS idx_turns_session ON turns (session_id);
