package com.pulsestream.telemetry.reordering.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.pulsestream.telemetry.intake.domain.TelemetrySample;

class ReorderWindowTest {

    private static final Instant T0 = Instant.parse("2025-01-01T00:00:00Z");
    private static final Duration WINDOW = Duration.ofSeconds(60);

    private static TelemetrySample sample(String deviceId, long offsetSeconds) {
        return TelemetrySample.of(deviceId, "temperature", T0.plusSeconds(offsetSeconds), 1.0);
    }

    private static List<Instant> times(List<ReleasedSample> released) {
        return released.stream().map(r -> r.sample().tDevice()).toList();
    }

    @Test
    void release_outOfOrderSamplesWithinWindow_releasesOrderedByTDevice() {
        ReorderWindow window = new ReorderWindow(WINDOW);
        window.offer(sample("d1", 30));
        window.offer(sample("d1", 10));
        window.offer(sample("d1", 20));

        List<ReleasedSample> released = window.release(T0.plusSeconds(200));

        assertThat(times(released)).containsExactly(T0.plusSeconds(10), T0.plusSeconds(20), T0.plusSeconds(30));
    }

    @Test
    void release_samplesInsideWindow_areHeldBack() {
        ReorderWindow window = new ReorderWindow(WINDOW);
        window.offer(sample("d1", 100));

        List<ReleasedSample> released = window.release(T0.plusSeconds(120));

        assertThat(released).isEmpty();
    }

    @Test
    void release_inOrderSamples_areNotFlaggedAsBackfill() {
        ReorderWindow window = new ReorderWindow(WINDOW);
        window.offer(sample("d1", 10));
        window.offer(sample("d1", 20));

        List<ReleasedSample> released = window.release(T0.plusSeconds(200));

        assertThat(released).noneMatch(ReleasedSample::backfill);
    }

    @Test
    void offer_sampleOlderThanReleasedWatermark_isFlaggedAsBackfillNotDropped() {
        ReorderWindow window = new ReorderWindow(WINDOW);
        window.offer(sample("d1", 100));
        window.release(T0.plusSeconds(300));
        window.offer(sample("d1", 5));

        List<ReleasedSample> released = window.release(T0.plusSeconds(400));

        assertThat(released).hasSize(1);
        assertThat(released.get(0).backfill()).isTrue();
        assertThat(released.get(0).sample().tDevice()).isEqualTo(T0.plusSeconds(5));
    }

    @Test
    void release_lateSampleAtWatermark_isNotBackfill() {
        ReorderWindow window = new ReorderWindow(WINDOW);
        window.offer(sample("d1", 100));
        window.release(T0.plusSeconds(300));
        window.offer(sample("d1", 100));

        List<ReleasedSample> released = window.release(T0.plusSeconds(400));

        assertThat(released).hasSize(1);
        assertThat(released.get(0).backfill()).isFalse();
    }

    @Test
    void release_mixedArrivals_losesNoSample() {
        ReorderWindow window = new ReorderWindow(WINDOW);
        List<ReleasedSample> all = new ArrayList<>();
        window.offer(sample("d1", 50));
        window.offer(sample("d2", 40));
        all.addAll(window.release(T0.plusSeconds(200)));
        window.offer(sample("d1", 1));
        window.offer(sample("d2", 300));
        all.addAll(window.release(T0.plusSeconds(500)));

        assertThat(all).hasSize(4);
    }

    @Test
    void release_equalTDeviceSameDevice_keepsArrivalOrder() {
        ReorderWindow window = new ReorderWindow(WINDOW);
        TelemetrySample first = TelemetrySample.of("d1", "temperature", T0.plusSeconds(10), 1.0);
        TelemetrySample second = TelemetrySample.of("d1", "temperature", T0.plusSeconds(10), 2.0);
        window.offer(first);
        window.offer(second);

        List<ReleasedSample> released = window.release(T0.plusSeconds(200));

        assertThat(released).extracting(ReleasedSample::sample).containsExactly(first, second);
    }
}
