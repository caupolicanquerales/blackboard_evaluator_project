package com.pulsestream.telemetry.ingestion.application;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

class BackfillReordererTest {

    private static final Duration WINDOW = Duration.ofSeconds(5);
    private static final Instant BASE = Instant.parse("2026-01-01T00:00:00Z");

    private static TelemetrySample sample(int offsetSeconds) {
        return new TelemetrySample("dev-1", "temp", BASE.plusSeconds(offsetSeconds), BASE.plusSeconds(100),
                1.0, ValidationStatus.values()[0], "{}");
    }

    @Test
    void reorder_outOfOrderWithinWindow_emitsSortedAndCountsMovedSample() {
        TelemetryMetrics metrics = mock(TelemetryMetrics.class);
        BackfillReorderer reorderer = new BackfillReorderer(WINDOW, 100, metrics);
        TelemetrySample early = sample(1);
        TelemetrySample late = sample(2);

        StepVerifier.withVirtualTime(() -> reorderer.reorder(Flux.just(late, early)))
                .thenAwait(WINDOW.plusSeconds(1))
                .expectNext(early, late)
                .verifyComplete();

        verify(metrics, times(1)).backfillReordered();
    }

    @Test
    void reorder_inOrderStream_emitsUnchangedAndDoesNotCount() {
        TelemetryMetrics metrics = mock(TelemetryMetrics.class);
        BackfillReorderer reorderer = new BackfillReorderer(WINDOW, 100, metrics);
        TelemetrySample first = sample(1);
        TelemetrySample second = sample(2);

        StepVerifier.withVirtualTime(() -> reorderer.reorder(Flux.just(first, second)))
                .thenAwait(WINDOW.plusSeconds(1))
                .expectNext(first, second)
                .verifyComplete();

        verify(metrics, never()).backfillReordered();
    }

    @Test
    void reorder_bufferCapacityReached_flushesSortedBeforeWindowElapses() {
        TelemetryMetrics metrics = mock(TelemetryMetrics.class);
        BackfillReorderer reorderer = new BackfillReorderer(Duration.ofHours(1), 2, metrics);
        TelemetrySample early = sample(1);
        TelemetrySample late = sample(2);

        StepVerifier.withVirtualTime(() -> reorderer.reorder(Flux.just(late, early).concatWith(Flux.never())))
                .expectNext(early)
                .thenCancel()
                .verify(Duration.ofSeconds(2));
    }
}
