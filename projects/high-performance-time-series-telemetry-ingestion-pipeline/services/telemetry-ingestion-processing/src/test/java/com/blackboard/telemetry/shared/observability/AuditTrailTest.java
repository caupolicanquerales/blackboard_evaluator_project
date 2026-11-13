package com.blackboard.telemetry.shared.observability;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Method;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class AuditTrailTest {

    private static final class RecordingTrail implements AuditTrail {
        final List<AuditEntry> entries = new ArrayList<>();

        @Override
        public Mono<Void> record(AuditEntry entry) {
            return Mono.fromRunnable(() -> entries.add(entry));
        }
    }

    private static AuditEntry entry() {
        return new AuditEntry("actor-1", "INGEST", "SUCCESS", Instant.parse("2024-01-01T00:00:00Z"), "req-1");
    }

    @Test
    void record_validEntry_completesEmpty() {
        RecordingTrail trail = new RecordingTrail();

        StepVerifier.create(trail.record(entry())).verifyComplete();
    }

    @Test
    void record_validEntry_appendsEntry() {
        RecordingTrail trail = new RecordingTrail();
        AuditEntry entry = entry();

        trail.record(entry).block();

        assertThat(trail.entries).containsExactly(entry);
    }

    @Test
    void declaredMethods_onlyRecord_noUpdateOrDelete() {
        Method[] methods = AuditTrail.class.getDeclaredMethods();

        assertThat(methods).extracting(Method::getName).containsExactly("record");
    }

    @Test
    void record_returnType_isMono() {
        Method[] methods = AuditTrail.class.getDeclaredMethods();

        assertThat(methods[0].getReturnType()).isEqualTo(Mono.class);
    }
}
