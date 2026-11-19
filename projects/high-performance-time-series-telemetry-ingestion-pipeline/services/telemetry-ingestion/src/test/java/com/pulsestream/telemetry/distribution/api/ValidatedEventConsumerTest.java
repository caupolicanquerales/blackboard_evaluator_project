package com.pulsestream.telemetry.distribution.api;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.distribution.application.TrustedPublisherPolicy;
import com.pulsestream.telemetry.distribution.domain.TelemetryWindowBroadcast;
import com.pulsestream.telemetry.ingestion.application.AuditTrail;
import com.pulsestream.telemetry.ingestion.application.RedactionPort;
import com.pulsestream.telemetry.ingestion.application.AuditEntry;
import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class ValidatedEventConsumerTest {

    private static final String TRUSTED = "ingestion";
    private static final Instant T0 = Instant.parse("2026-01-01T00:00:00Z");

    private final List<AuditEntry> audits = new ArrayList<>();
    private final SimpleMeterRegistry registry = new SimpleMeterRegistry();

    private ValidatedEventConsumer consumer(Duration duration, int max) {
        AuditTrail trail = entry -> {
            audits.add(entry);
            return Mono.empty();
        };
        RedactionPort redaction = value -> "***";
        return new ValidatedEventConsumer(new TrustedPublisherPolicy(TRUSTED), trail, redaction,
                new TelemetryMetrics(registry), duration, max);
    }

    private TelemetryEvent event(String deviceId, String keyDevice, String publisher, int offset) {
        Instant t = T0.plusSeconds(offset);
        return new TelemetryEvent(1, TelemetryEvent.Type.TELEMETRY_VALIDATED,
                TelemetryEvent.keyOf(keyDevice, "temperature", t, 1), deviceId, "temperature", t, 1, 20.0,
                com.pulsestream.telemetry.ingestion.domain.ValidationStatus.VALIDATED, publisher);
    }

    @Test
    void buffer_trustedEvent_isEmittedInWindow() {
        Flux<TelemetryWindowBroadcast> out = consumer(Duration.ofSeconds(30), 1)
                .buffer(Flux.just(event("d1", "d1", TRUSTED, 0)));

        StepVerifier.create(out)
                .assertNext(w -> assertThat(w.events()).hasSize(1))
                .verifyComplete();
        assertThat(registry.get("telemetry.broadcast.windows").counter().count()).isEqualTo(1.0);
    }

    @Test
    void buffer_unknownPublisher_isDroppedWithAuditAndCounter() {
        Flux<TelemetryWindowBroadcast> out = consumer(Duration.ofSeconds(30), 1)
                .buffer(Flux.just(event("d1", "d1", "intruder", 0)));

        StepVerifier.create(out).verifyComplete();
        assertThat(audits).hasSize(1);
        assertThat(registry.get("telemetry.broadcast.dropped").counter().count()).isEqualTo(1.0);
    }

    @Test
    void buffer_identityNotMatchingPayloadDevice_isRefused() {
        Flux<TelemetryWindowBroadcast> out = consumer(Duration.ofSeconds(30), 1)
                .buffer(Flux.just(event("d1", "d2", TRUSTED, 0)));

        StepVerifier.create(out).verifyComplete();
        assertThat(registry.get("telemetry.broadcast.dropped").counter().count()).isEqualTo(1.0);
    }

    @Test
    void buffer_sizeReached_closesWindowAtMaxEvents() {
        Flux<TelemetryWindowBroadcast> out = consumer(Duration.ofMinutes(10), 2)
                .buffer(Flux.just(event("d1", "d1", TRUSTED, 0), event("d1", "d1", TRUSTED, 1),
                        event("d1", "d1", TRUSTED, 2), event("d1", "d1", TRUSTED, 3)));

        StepVerifier.create(out)
                .assertNext(w -> assertThat(w.events()).hasSize(2))
                .assertNext(w -> assertThat(w.events()).hasSize(2))
                .verifyComplete();
    }

    @Test
    void buffer_durationElapsed_closesWindowOnVirtualTime() {
        StepVerifier.withVirtualTime(() -> consumer(Duration.ofSeconds(5), 100)
                        .buffer(Flux.concat(Flux.just(event("d1", "d1", TRUSTED, 0)), Flux.never())))
                .thenAwait(Duration.ofSeconds(5))
                .assertNext(w -> assertThat(w.events()).hasSize(1))
                .thenCancel()
                .verify();
    }
}
