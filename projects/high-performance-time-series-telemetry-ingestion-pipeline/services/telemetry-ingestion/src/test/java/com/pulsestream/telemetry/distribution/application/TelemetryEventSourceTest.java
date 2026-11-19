package com.pulsestream.telemetry.distribution.application;

import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

class TelemetryEventSourceTest {

    private static final Instant T = Instant.parse("2025-01-01T00:00:00Z");

    private static TelemetryEvent event() {
        return new TelemetryEvent(1, TelemetryEvent.Type.values()[0],
                TelemetryEvent.keyOf("dev-1", "temp", T, 1), "dev-1", "temp", T, 1, 1.5,
                ValidationStatus.values()[0], "pub-1");
    }

    @Test
    void events_stubEmitsEvents_emitsThemInOrder() {
        TelemetryEvent first = event();
        TelemetryEvent second = event();
        TelemetryEventSource source = () -> Flux.just(first, second);

        StepVerifier.create(source.events())
                .expectNext(first)
                .expectNext(second)
                .verifyComplete();
    }

    @Test
    void events_stubEmitsNothing_completesEmpty() {
        TelemetryEventSource source = Flux::empty;

        StepVerifier.create(source.events()).verifyComplete();
    }
}
