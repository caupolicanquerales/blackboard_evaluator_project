-- Bounded context: general-ledger (PostgreSQL 16)
-- Immutability of the journal: corrections happen only via reversal entries. Expand-only.

CREATE OR REPLACE FUNCTION general_ledger.reject_journal_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'journal tables are append-only; post a reversal entry instead';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_journal_lines_immutable ON general_ledger.journal_lines;
CREATE TRIGGER trg_journal_lines_immutable
    BEFORE UPDATE OR DELETE ON general_ledger.journal_lines
    FOR EACH ROW EXECUTE FUNCTION general_ledger.reject_journal_mutation();

DROP TRIGGER IF EXISTS trg_journal_entries_immutable ON general_ledger.journal_entries;
CREATE TRIGGER trg_journal_entries_immutable
    BEFORE DELETE ON general_ledger.journal_entries
    FOR EACH ROW EXECUTE FUNCTION general_ledger.reject_journal_mutation();

-- Entries may only move PENDING -> POSTED; all other columns stay frozen.
CREATE OR REPLACE FUNCTION general_ledger.guard_journal_entry_update() RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'POSTED'
       OR NEW.id IS DISTINCT FROM OLD.id
       OR NEW.fiscal_period_id IS DISTINCT FROM OLD.fiscal_period_id
       OR NEW.reverses_entry_id IS DISTINCT FROM OLD.reverses_entry_id
       OR NEW.source_event_id IS DISTINCT FROM OLD.source_event_id THEN
        RAISE EXCEPTION 'posted journal entries are immutable; post a reversal entry instead';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_journal_entries_guard_update ON general_ledger.journal_entries;
CREATE TRIGGER trg_journal_entries_guard_update
    BEFORE UPDATE ON general_ledger.journal_entries
    FOR EACH ROW EXECUTE FUNCTION general_ledger.guard_journal_entry_update();

-- Balanced entry: debits equal credits, checked at commit for POSTED entries.
CREATE OR REPLACE FUNCTION general_ledger.assert_entry_balanced() RETURNS trigger AS $$
DECLARE
    unbalanced boolean;
BEGIN
    SELECT COALESCE(SUM(CASE direction WHEN 'D' THEN amount ELSE -amount END), 0) <> 0
      INTO unbalanced
      FROM general_ledger.journal_lines
     WHERE journal_entry_id = NEW.journal_entry_id;
    IF unbalanced THEN
        RAISE EXCEPTION 'journal entry % is not balanced', NEW.journal_entry_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_journal_lines_balanced ON general_ledger.journal_lines;
CREATE CONSTRAINT TRIGGER trg_journal_lines_balanced
    AFTER INSERT ON general_ledger.journal_lines
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION general_ledger.assert_entry_balanced();
