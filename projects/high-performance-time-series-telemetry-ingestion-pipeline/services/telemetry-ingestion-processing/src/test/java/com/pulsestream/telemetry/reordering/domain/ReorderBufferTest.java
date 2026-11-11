package com.pulsestream.telemetry.reordering.domain;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class ReorderBufferTest {

    private static final long WINDOW_MS = 10_000L;

    private ReorderBuffer buffer;

    @BeforeEach
    void setUp() {
        buffer = new ReorderBuffer(new TelemetryProperties(10L, 16, Map.of()));
    }

    private static TelemetrySample sample(long tDevice, long tIngress) {
        return new TelemetrySample("dev-1", "temp", tDevice, 1.0, tIngress, TelemetrySample.VALID);
    }

    @Test
    void accept_sampleInsideWindow_isRetained() {
        List<TelemetrySample> released = buffer.accept(sample(95_000L, 95_000L), 100_000L);

        assertThat(released).isEmpty();
    }

    @Test
    void accept_sampleOlderThanWindow_isReleased() {
        TelemetrySample old = sample(80_000L, 80_000L);

        List<TelemetrySample> released = buffer.accept(old, 100_000L);

        assertThat(released).containsExactly(old);
    }

    @Test
    void accept_sampleExactlyAtWindowBoundary_isReleased() {
        TelemetrySample edge = sample(100_000L - WINDOW_MS, 1L);

        List<TelemetrySample> released = buffer.accept(edge, 100_000L);

        assertThat(released).containsExactly(edge);
    }

    @Test
    void accept_lateSampleWithinWindow_isPlacedChronologically() {
        TelemetrySample later = sample(105_000L, 105_000L);
        TelemetrySample late = sample(101_000L, 106_000L);
        TelemetrySample earlier = sample(100_000L, 100_000L);
        buffer.accept(later, 106_000L);
        buffer.accept(earlier, 106_000L);

        buffer.accept(late, 106_000L);

        assertThat(buffer.drain()).containsExactly(earlier, late, later);
    }

    @Test
    void accept_releasedSamples_areOrderedByDeviceTimeNotIngress() {
        TelemetrySample a = sample(50_000L, 300L);
        TelemetrySample b = sample(40_000L, 900L);
        buffer.accept(a, 55_000L);
        buffer.accept(b, 55_000L);

        List<TelemetrySample> released = buffer.accept(sample(99_000L, 1L), 200_000L);

        assertThat(released).extracting(TelemetrySample::tDeviceEpochMs)
                .containsExactly(40_000L, 50_000L, 99_000L);
    }

    @Test
    void accept_releasedBatch_removesSamplesFromBuffer() {
        buffer.accept(sample(10_000L, 1L), 12_000L);

        buffer.accept(sample(11_000L, 1L), 100_000L);

        assertThat(buffer.drain()).isEmpty();
    }

    @Test
    void drain_withRetainedSamples_returnsAllSortedAndEmptiesBuffer() {
        TelemetrySample s1 = sample(103_000L, 1L);
        TelemetrySample s2 = sample(101_000L, 2L);
        TelemetrySample s3 = sample(102_000L, 3L);
        buffer.accept(s1, 104_000L);
        buffer.accept(s2, 104_000L);
        buffer.accept(s3, 104_000L);

        List<TelemetrySample> drained = buffer.drain();

        assertThat(drained).containsExactly(s2, s3, s1);
        assertThat(buffer.drain()).isEmpty();
    }

    @Test
    void drain_onEmptyBuffer_returnsEmptyList() {
        assertThat(buffer.drain()).isEmpty();
    }
}
