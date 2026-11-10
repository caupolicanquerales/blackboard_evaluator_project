package com.pulsestream.telemetry.intake.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class ReorderWindowTest {

    private static final Instant BASE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant INGRESS = Instant.parse("2030-01-01T00:00:00Z");
    private static final Duration WINDOW = Duration.ofSeconds(5);

    private ReorderWindow window;

    @BeforeEach
    void setUp() {
        window = new ReorderWindow(WINDOW);
    }

    private static TelemetrySample sampleAt(long offsetSeconds) {
        Instant deviceTs = BASE.plusSeconds(offsetSeconds);
        return new TelemetrySample(
                TelemetrySample.recordIdFor("dev-1", TelemetrySample.MetricType.HEART_RATE, deviceTs),
                "dev-1",
                TelemetrySample.MetricType.HEART_RATE,
                120.0,
                deviceTs,
                INGRESS,
                TelemetrySample.ValidationStatus.VALID);
    }

    @Test
    void offer_firstSample_isBufferedNormally() {
        ReorderWindow.OfferResult result = window.offer(sampleAt(10));

        assertThat(result.late()).isFalse();
        assertThat(result.outOfOrder()).isFalse();
        assertThat(window.bufferedCount()).isEqualTo(1);
    }

    @Test
    void offer_inOrderSample_isBufferedNormally() {
        window.offer(sampleAt(10));

        ReorderWindow.OfferResult result = window.offer(sampleAt(11));

        assertThat(result.late()).isFalse();
        assertThat(result.outOfOrder()).isFalse();
        assertThat(window.bufferedCount()).isEqualTo(2);
    }

    @Test
    void offer_olderThanNewestBufferedButNotReleased_isOutOfOrderAndBuffered() {
        window.offer(sampleAt(10));

        ReorderWindow.OfferResult result = window.offer(sampleAt(8));

        assertThat(result.outOfOrder()).isTrue();
        assertThat(result.late()).isFalse();
        assertThat(window.bufferedCount()).isEqualTo(2);
    }

    @Test
    void offer_olderThanReleasedWatermark_isLateAndNotBuffered() {
        window.offer(sampleAt(10));
        window.drainReleasable(BASE.plusSeconds(100));

        ReorderWindow.OfferResult result = window.offer(sampleAt(5));

        assertThat(result.late()).isTrue();
        assertThat(window.bufferedCount()).isZero();
    }

    @Test
    void drainReleasable_samplesOutsideWindow_returnsSortedByDeviceTimestamp() {
        TelemetrySample s3 = sampleAt(3);
        TelemetrySample s1 = sampleAt(1);
        TelemetrySample s2 = sampleAt(2);
        window.offer(s3);
        window.offer(s1);
        window.offer(s2);

        List<TelemetrySample> released = window.drainReleasable(BASE.plusSeconds(100));

        assertThat(released).containsExactly(s1, s2, s3);
        assertThat(window.bufferedCount()).isZero();
    }

    @Test
    void drainReleasable_sampleExactlyAtBoundary_isReleased() {
        TelemetrySample boundary = sampleAt(10);
        window.offer(boundary);

        List<TelemetrySample> released = window.drainReleasable(BASE.plusSeconds(10).plus(WINDOW));

        assertThat(released).containsExactly(boundary);
    }

    @Test
    void drainReleasable_sampleInsideWindow_isRetained() {
        TelemetrySample recent = sampleAt(10);
        window.offer(recent);

        List<TelemetrySample> released = window.drainReleasable(BASE.plusSeconds(12));

        assertThat(released).isEmpty();
        assertThat(window.bufferedCount()).isEqualTo(1);
    }

    @Test
    void drainReleasable_mixedSamples_releasesOnlyEligibleOnes() {
        TelemetrySample old = sampleAt(1);
        TelemetrySample recent = sampleAt(20);
        window.offer(recent);
        window.offer(old);

        List<TelemetrySample> released = window.drainReleasable(BASE.plusSeconds(10));

        assertThat(released).containsExactly(old);
        assertThat(window.bufferedCount()).isEqualTo(1);
    }

    @Test
    void drainReleasable_emptyBuffer_returnsEmptyList() {
        assertThat(window.drainReleasable(BASE.plusSeconds(100))).isEmpty();
    }

    @Test
    void offer_orderingUsesDeviceTimestampNotIngress_outOfOrderByDeviceTime() {
        TelemetrySample newerDevice = sampleAt(10);
        TelemetrySample olderDevice = new TelemetrySample(
                TelemetrySample.recordIdFor("dev-1", TelemetrySample.MetricType.HEART_RATE, BASE.plusSeconds(5)),
                "dev-1",
                TelemetrySample.MetricType.HEART_RATE,
                120.0,
                BASE.plusSeconds(5),
                INGRESS.plusSeconds(1000),
                TelemetrySample.ValidationStatus.VALID);
        window.offer(newerDevice);

        ReorderWindow.OfferResult result = window.offer(olderDevice);

        assertThat(result.outOfOrder()).isTrue();
    }
}
