-- Bounded context: compliance-risk (PostgreSQL 16)
-- Store setup: creates the owning schema. Expand-only.
CREATE SCHEMA IF NOT EXISTS compliance_risk;

COMMENT ON SCHEMA compliance_risk IS 'Bounded context compliance-risk (Transaction Screening): owned exclusively by this context.';
