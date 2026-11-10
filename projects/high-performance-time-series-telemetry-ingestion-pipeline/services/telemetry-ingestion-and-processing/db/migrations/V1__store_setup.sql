-- Store setup: Telemetry Event Ledger (PostgreSQL 16)
CREATE SCHEMA IF NOT EXISTS ledger;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                   WHERE t.typname = 'validation_status' AND n.nspname = 'ledger') THEN
        CREATE TYPE ledger.validation_status AS ENUM ('VALID', 'INVALID', 'LATE');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                   WHERE t.typname = 'revision_reason' AND n.nspname = 'ledger') THEN
        CREATE TYPE ledger.revision_reason AS ENUM ('ORIGINAL', 'CORRECTION', 'BACKFILL');
    END IF;
END
$$;
