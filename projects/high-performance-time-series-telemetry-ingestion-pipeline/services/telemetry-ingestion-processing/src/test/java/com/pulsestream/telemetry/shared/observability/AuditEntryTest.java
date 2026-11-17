package com.pulsestream.telemetry.shared.observability;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class AuditEntryTest {

    private static final Instant TS = Instant.parse("2025-01-01T10:00:00Z");

    private static AuditEntry entry(String actor) {
        return new AuditEntry(actor, "intake.receive", "accepted", TS, "corr-1");
    }

    @Test
    void accessors_constructedEntry_returnEveryField() {
        AuditEntry e = entry("intake");

        assertThat(e.actor()).isEqualTo("intake");
        assertThat(e.action()).isEqualTo("intake.receive");
        assertThat(e.outcome()).isEqualTo("accepted");
        assertThat(e.timestamp()).isEqualTo(TS);
        assertThat(e.correlationId()).isEqualTo("corr-1");
    }

    @Test
    void equals_sameFields_areEqualWithSameHashCode() {
        assertThat(entry("intake")).isEqualTo(entry("intake"))
                .hasSameHashCodeAs(entry("intake"));
    }

    @Test
    void equals_differentActor_areNotEqual() {
        assertThat(entry("intake")).isNotEqualTo(entry("eventlog"));
    }
}
