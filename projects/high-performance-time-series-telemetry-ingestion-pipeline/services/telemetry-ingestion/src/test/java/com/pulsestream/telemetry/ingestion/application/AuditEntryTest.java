package com.pulsestream.telemetry.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class AuditEntryTest {

    @Test
    void accessors_constructedValues_returnSameValues() {
        Instant now = Instant.parse("2026-01-01T00:00:00Z");

        AuditEntry entry = new AuditEntry("actor", "action", "outcome", now, "corr-1");

        assertThat(entry.actor()).isEqualTo("actor");
        assertThat(entry.action()).isEqualTo("action");
        assertThat(entry.outcome()).isEqualTo("outcome");
        assertThat(entry.timestamp()).isEqualTo(now);
        assertThat(entry.correlationId()).isEqualTo("corr-1");
    }
}
