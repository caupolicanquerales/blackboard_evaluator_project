package com.pulsestream.telemetry.ingestion.application;

import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class EventPublisherTest {

    private static TelemetryEvent event() {
        Instant t = Instant.parse("2025-01-01T00:00:00Z");
        String key = TelemetryEvent.keyOf("dev-1", "heart_rate", t, 1);
        return new TelemetryEvent(1, TelemetryEvent.Type.values()[0], key, "dev-1", "heart_rate", t, 1, 60.0,
                ValidationStatus.values()[0], "pub-1");
    }

    @Test
    void publish_busAccepts_emitsTrue() {
        EventPublisher publisher = e -> Mono.just(true);

        StepVerifier.create(publisher.publish(event())).expectNext(true).verifyComplete();
    }

    @Test
    void publish_busOverflow_emitsFalse() {
        EventPublisher publisher = e -> Mono.just(false);

        StepVerifier.create(publisher.publish(event())).expectNext(false).verifyComplete();
    }
}
