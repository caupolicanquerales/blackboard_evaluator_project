-- Bounded context: payments (PostgreSQL 16)
-- Store setup: creates the owning schema. Expand-only.
CREATE SCHEMA IF NOT EXISTS payments;

COMMENT ON SCHEMA payments IS 'Bounded context payments: owned exclusively by this context.';
