-- Bounded context: general-ledger (PostgreSQL 16)
-- Store setup: creates the owning schema. Expand-only.
CREATE SCHEMA IF NOT EXISTS general_ledger;

COMMENT ON SCHEMA general_ledger IS 'Bounded context general-ledger: owned exclusively by this context.';
