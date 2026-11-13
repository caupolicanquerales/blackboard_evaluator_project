package com.blackboard.telemetry.shared.observability;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class AuditEntryTest {

    private static final Instant TS = Instant.parse("2024-01-01T00:00:00Z");

    @Test
    void accessors_returnConstructorValues() {
        AuditEntry entry = new AuditEntry("actor-1", "INGEST", "SUCCESS", TS, "req-1");

        assertThat(entry.actor()).isEqualTo("actor-1");
        assertThat(entry.action()).isEqualTo("INGEST");
        assertThat(entry.outcome()).isEqualTo("SUCCESS");
        assertThat(entry.timestamp()).isEqualTo(TS);
        assertThat(entry.correlationId()).isEqualTo("req-1");
    }

    @Test
    void equals_sameComponents_areEqualWithSameHashCode() {
        AuditEntry a = new AuditEntry("actor-1", "INGEST", "SUCCESS", TS, "req-1");
        AuditEntry b = new AuditEntry("actor-1", "INGEST", "SUCCESS", TS, "req-1");

        assertThat(a).isEqualTo(b).hasSameHashCodeAs(b);
    }

    @Test
    void equals_differentCorrelationId_areNotEqual() {
        AuditEntry a = new AuditEntry("actor-1", "INGEST", "SUCCESS", TS, "req-1");
        AuditEntry b = new AuditEntry("actor-1", "INGEST", "SUCCESS", TS, "req-2");

        assertThat(a).isNotEqualTo(b);
    }

    @Test
    void equals_differentOutcome_areNotEqual() {
        AuditEntry a = new AuditEntry("actor-1", "INGEST", "SUCCESS", TS, "req-1");
        AuditEntry b = new AuditEntry("actor-1", "INGEST", "FAILURE", TS, "req-1");

        assertThat(a).isNotEqualTo(b);
    }
}
