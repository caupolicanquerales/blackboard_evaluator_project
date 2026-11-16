package com.blackboard.telemetry.shared.audit;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Method;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class AuditTrailTest {

    private static AuditEntry entry() {
        return new AuditEntry("device-1", AuditAction.values()[0], "SUCCESS",
                Instant.parse("2025-01-01T00:00:00Z"), "req-1");
    }

    @Test
    void record_validEntry_completesAndAppendsEntry() {
        List<AuditEntry> stored = new ArrayList<>();
        AuditTrail trail = e -> Mono.fromRunnable(() -> stored.add(e));
        AuditEntry entry = entry();

        StepVerifier.create(trail.record(entry)).verifyComplete();

        assertThat(stored).containsExactly(entry);
    }

    @Test
    void record_storageFails_emitsErrorSignal() {
        AuditTrail trail = e -> Mono.error(new IllegalStateException("storage down"));

        StepVerifier.create(trail.record(entry()))
                .expectErrorMatches(t -> t instanceof IllegalStateException)
                .verify();
    }

    @Test
    void record_calledTwice_accumulatesEntries() {
        List<AuditEntry> stored = new ArrayList<>();
        AuditTrail trail = e -> Mono.fromRunnable(() -> stored.add(e));

        StepVerifier.create(trail.record(entry()).then(trail.record(entry()))).verifyComplete();

        assertThat(stored).hasSize(2);
    }

    @Test
    void port_declaresOnlyRecordOperation() {
        List<String> names = Arrays.stream(AuditTrail.class.getDeclaredMethods())
                .map(Method::getName).toList();

        assertThat(names).containsExactly("record");
    }
}
