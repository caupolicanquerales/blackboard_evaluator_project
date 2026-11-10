package com.pulsestream.telemetry.sequencing.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.sequencing.domain.ReorderWindow.Outcome;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class ReorderWindowTest {

    private static final Instant BASE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Duration WINDOW = Duration.ofSeconds(60);

    private static TelemetrySampleEvent sample(long deviceSec, long ingressSec) {
        return sample(deviceSec, ingressSec, TelemetrySampleEvent.VALID);
    }

    private static TelemetrySampleEvent sample(long deviceSec, long ingressSec, String status) {
        return new TelemetrySampleEvent("dev-1", "temp", 1.0,
                BASE.plusSeconds(deviceSec), BASE.plusSeconds(ingressSec), status);
    }

    private static ReorderWindow window() {
        return new ReorderWindow(WINDOW, 100);
    }

    @Test
    void constructor_nonPositiveCapacity_throws() {
        assertThatThrownBy(() -> new ReorderWindow(WINDOW, 0))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_zeroWindow_throws() {
        assertThatThrownBy(() -> new ReorderWindow(Duration.ZERO, 10))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_negativeWindow_throws() {
        assertThatThrownBy(() -> new ReorderWindow(Duration.ofSeconds(-1), 10))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void offer_firstSample_isInOrder() {
        assertThat(window().offer(sample(100, 100))).isEqualTo(Outcome.IN_ORDER);
    }

    @Test
    void offer_sameTimestampAsHighest_isInOrder() {
        ReorderWindow w = window();
        w.offer(sample(100, 100));

        assertThat(w.offer(sample(100, 101))).isEqualTo(Outcome.IN_ORDER);
    }

    @Test
    void offer_olderWithinWindow_isBackfill() {
        ReorderWindow w = window();
        w.offer(sample(100, 100));

        assertThat(w.offer(sample(70, 101))).isEqualTo(Outcome.BACKFILL);
    }

    @Test
    void offer_exactlyWindowOlder_isBackfill() {
        ReorderWindow w = window();
        w.offer(sample(100, 100));

        assertThat(w.offer(sample(40, 101))).isEqualTo(Outcome.BACKFILL);
    }

    @Test
    void offer_olderThanWindow_isLate() {
        ReorderWindow w = window();
        w.offer(sample(100, 100));

        assertThat(w.offer(sample(39, 101))).isEqualTo(Outcome.LATE);
    }

    @Test
    void offer_lateSample_isNotBuffered() {
        ReorderWindow w = window();
        w.offer(sample(100, 100));
        w.offer(sample(10, 101));

        assertThat(w.drainAll()).containsExactly(sample(100, 100));
    }

    @Test
    void offer_customWindow_usesConstructorDuration() {
        ReorderWindow w = new ReorderWindow(Duration.ofSeconds(5), 10);
        w.offer(sample(100, 100));

        assertThat(w.offer(sample(94, 101))).isEqualTo(Outcome.LATE);
    }

    @Test
    void offer_ignoresIngressTime_usesDeviceTime() {
        ReorderWindow w = window();
        w.offer(sample(100, 0));

        assertThat(w.offer(sample(90, 500))).isEqualTo(Outcome.BACKFILL);
    }

    @Test
    void drainReady_nothingOldEnough_returnsEmpty() {
        ReorderWindow w = window();
        w.offer(sample(100, 100));
        w.offer(sample(90, 101));

        assertThat(w.drainReady()).isEmpty();
    }

    @Test
    void drainReady_samplesOlderThanWindow_returnedAscendingAndRemoved() {
        ReorderWindow w = window();
        w.offer(sample(50, 1));
        w.offer(sample(30, 2));
        w.offer(sample(40, 3));
        w.offer(sample(200, 4));

        List<TelemetrySampleEvent> ready = w.drainReady();

        assertThat(ready).containsExactly(sample(30, 2), sample(40, 3), sample(50, 1));
        assertThat(w.drainReady()).isEmpty();
    }

    @Test
    void drainReady_sampleExactlyAtThreshold_isReleased() {
        ReorderWindow w = window();
        w.offer(sample(40, 1));
        w.offer(sample(100, 2));

        assertThat(w.drainReady()).containsExactly(sample(40, 1));
    }

    @Test
    void drainReady_equalDeviceTimes_orderedByArrival() {
        ReorderWindow w = window();
        TelemetrySampleEvent first = sample(10, 5);
        TelemetrySampleEvent second = sample(10, 1);
        w.offer(first);
        w.offer(second);
        w.offer(sample(200, 6));

        assertThat(w.drainReady()).containsExactly(first, second);
    }

    @Test
    void drainReady_ordersByDeviceTimeNotIngressTime() {
        ReorderWindow w = window();
        TelemetrySampleEvent a = sample(20, 900);
        TelemetrySampleEvent b = sample(10, 800);
        w.offer(a);
        w.offer(b);
        w.offer(sample(300, 1));

        assertThat(w.drainReady()).containsExactly(b, a);
    }

    @Test
    void drainReady_validationFailedSample_isOrderedLikeAnyOther() {
        ReorderWindow w = window();
        TelemetrySampleEvent failed = sample(10, 1, TelemetrySampleEvent.VALIDATION_FAILED);
        TelemetrySampleEvent ok = sample(5, 2);
        w.offer(failed);
        w.offer(ok);
        w.offer(sample(200, 3));

        assertThat(w.drainReady()).containsExactly(ok, failed);
    }

    @Test
    void drainReady_overCapacity_releasesOldestSamples() {
        ReorderWindow w = new ReorderWindow(WINDOW, 2);
        w.offer(sample(1, 1));
        w.offer(sample(2, 2));
        w.offer(sample(3, 3));

        assertThat(w.drainReady()).containsExactly(sample(1, 1));
    }

    @Test
    void drainReady_overCapacity_leavesCapacityBuffered() {
        ReorderWindow w = new ReorderWindow(WINDOW, 2);
        w.offer(sample(1, 1));
        w.offer(sample(2, 2));
        w.offer(sample(3, 3));
        w.drainReady();

        assertThat(w.drainAll()).containsExactly(sample(2, 2), sample(3, 3));
    }

    @Test
    void drainAll_releasesEverythingOrderedAndEmptiesBuffer() {
        ReorderWindow w = window();
        w.offer(sample(100, 1));
        w.offer(sample(80, 2));
        w.offer(sample(90, 3));

        assertThat(w.drainAll()).containsExactly(sample(80, 2), sample(90, 3), sample(100, 1));
        assertThat(w.drainAll()).isEmpty();
    }

    @Test
    void drainAll_emptyWindow_returnsEmpty() {
        assertThat(window().drainAll()).isEmpty();
    }
}
