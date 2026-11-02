-- Bounded context: accounts (PostgreSQL 16)
-- Store setup: creates the owning schema. Expand-only.
CREATE SCHEMA IF NOT EXISTS accounts;

COMMENT ON SCHEMA accounts IS 'Bounded context accounts: owned exclusively by this context.';
