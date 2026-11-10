package com.pulsestream.telemetry.ledger.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.shared.event.TelemetryEvent;
import com.pulsestream.telemetry.shared.event.TelemetryEvent.TelemetryRevisionAppended;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class DeadLetterSinkTest {

    private static final Instant OCCURRED_AT = Instant.parse("2024-01-01T00:00:00Z");

    private static final class RecordingSink implements DeadLetterSink {
        final List<TelemetryEvent> events = new ArrayList<>();
        final List<Throwable> causes = new ArrayList<>();

        @Override
        public Mono<Void> reject(TelemetryEvent event, Throwable cause) {
            return Mono.fromRunnable(() -> {
                events.add(event);
                causes.add(cause);
            });
        }
    }

    private static TelemetryEvent event() {
        return new TelemetryRevisionAppended(
                UUID.fromString("00000000-0000-0000-0000-000000000001"), 1, OCCURRED_AT);
    }

    @Test
    void reject_withEventAndCause_completesEmpty() {
        DeadLetterSink sink = new RecordingSink();

        StepVerifier.create(sink.reject(event(), new IllegalStateException("boom")))
                .verifyComplete();
    }

    @Test
    void reject_withEventAndCause_capturesBoth() {
        RecordingSink sink = new RecordingSink();
        TelemetryEvent event = event();
        Throwable cause = new IllegalStateException("boom");

        StepVerifier.create(sink.reject(event, cause)).verifyComplete();

        assertThat(sink.events).containsExactly(event);
        assertThat(sink.causes).containsExactly(cause);
    }

    @Test
    void reject_beforeSubscription_returnsLazyMono() {
        RecordingSink sink = new RecordingSink();

        Mono<Void> result = sink.reject(event(), new RuntimeException("x"));

        assertThat(result).isNotNull();
        assertThat(sink.events).isEmpty();
    }
}
