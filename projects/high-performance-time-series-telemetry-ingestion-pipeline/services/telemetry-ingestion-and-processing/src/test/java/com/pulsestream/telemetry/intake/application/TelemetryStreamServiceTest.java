package com.pulsestream.telemetry.intake.application;
import java.util.UUID;
import java.time.Duration;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.pulsestream.telemetry.shared.event.TelemetryEvent;
import com.pulsestream.telemetry.shared.event.TelemetryEvent.TelemetryBackfillReordered;
import com.pulsestream.telemetry.shared.event.TelemetryEvent.TelemetryRevisionAppended;
import com.pulsestream.telemetry.shared.event.TelemetryEvent.TelemetrySampleValidated;
import com.pulsestream.telemetry.shared.event.TelemetryEvent.TelemetrySampleValidationFailed;
import com.pulsestream.telemetry.shared.event.TelemetryEvent.TelemetryWindowBuffered;
import com.pulsestream.telemetry.shared.event.TelemetryEventBus;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;
import reactor.test.StepVerifier;

class TelemetryStreamServiceTest {

    private static final Instant T0 = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T1 = Instant.parse("2024-01-01T00:01:00Z");

    private TelemetryEventBus bus;
    private TelemetryStreamService service;
    private Sinks.Many<TelemetryEvent> sink;
    private TelemetrySample sample;

    @BeforeEach
    void setUp() {
        bus = mock(TelemetryEventBus.class);
        sink = Sinks.many().multicast().onBackpressureBuffer();
        when(bus.stream()).thenReturn(sink.asFlux());
        service = new TelemetryStreamService(bus);
        sample = mock(TelemetrySample.class);
    }

    private TelemetryWindowBuffered window() {
        return new TelemetryWindowBuffered(List.of(), T0, T1, T1);
    }

    @Test
    void windows_mixedEvents_returnsOnlyWindowBuffered() {
        TelemetryWindowBuffered window = window();
        Flux<TelemetryWindowBuffered> flux = service.windows();

        StepVerifier.create(flux.take(1))
                .then(() -> {
                    sink.tryEmitNext(new TelemetrySampleValidated(sample, T0));
                    sink.tryEmitNext(new TelemetryBackfillReordered(sample, T0));
                    sink.tryEmitNext(new TelemetryRevisionAppended(java.util.UUID.fromString(
                            "00000000-0000-0000-0000-000000000001"), 1, T0));
                    sink.tryEmitNext(window);
                })
                .expectNext(window)
                .verifyComplete();
    }

    @Test
    void outcomes_mixedEvents_returnsOnlyValidatedAndFailed() {
        TelemetrySampleValidated validated = new TelemetrySampleValidated(sample, T0);
        TelemetrySampleValidationFailed failed = new TelemetrySampleValidationFailed(sample, T1);
        Flux<TelemetryEvent> flux = service.outcomes();

        StepVerifier.create(flux.take(2))
                .then(() -> {
                    sink.tryEmitNext(window());
                    sink.tryEmitNext(validated);
                    sink.tryEmitNext(new TelemetryBackfillReordered(sample, T0));
                    sink.tryEmitNext(failed);
                })
                .expectNext(validated, failed)
                .verifyComplete();
    }

    @Test
    void windows_eventsBeforeSubscription_areNotReplayed() {
        sink.tryEmitNext(window());
        TelemetryWindowBuffered later = new TelemetryWindowBuffered(List.of(), T1, T1, T1);

        StepVerifier.create(service.windows().take(1))
                .then(() -> sink.tryEmitNext(later))
                .expectNext(later)
                .verifyComplete();
    }

    @Test
    void outcomes_noMatchingEvents_emitsNothingUntilCancelled() {
        StepVerifier.create(service.outcomes())
                .then(() -> sink.tryEmitNext(window()))
                .expectNoEvent(java.time.Duration.ZERO)
                .thenCancel()
                .verify();
    }
}
