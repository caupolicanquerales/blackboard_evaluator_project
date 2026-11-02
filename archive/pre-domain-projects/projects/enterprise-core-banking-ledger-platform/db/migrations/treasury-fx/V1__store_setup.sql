-- Bounded context: treasury-fx (PostgreSQL 16)
-- Store setup: creates the owning schema. Expand-only.
CREATE SCHEMA IF NOT EXISTS treasury_fx;

COMMENT ON SCHEMA treasury_fx IS 'Bounded context treasury-fx: owned exclusively by this context.';
