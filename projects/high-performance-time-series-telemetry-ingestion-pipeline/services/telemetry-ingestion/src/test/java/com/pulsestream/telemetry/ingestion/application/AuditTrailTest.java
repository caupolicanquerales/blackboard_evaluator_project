package com.pulsestream.telemetry.ingestion.application;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

import static org.assertj.core.api.Assertions.assertThat;

class AuditTrailTest {

    @Test
    void record_entry_completesEmptyAndCapturesEntry() {
        List<AuditEntry> captured = new ArrayList<>();
        AuditTrail trail = entry -> {
            captured.add(entry);
            return Mono.empty();
        };
        AuditEntry entry = new AuditEntry("a", "act", "ok", Instant.parse("2026-01-01T00:00:00Z"), "c-1");

        StepVerifier.create(trail.record(entry)).verifyComplete();

        assertThat(captured).containsExactly(entry);
    }
}
