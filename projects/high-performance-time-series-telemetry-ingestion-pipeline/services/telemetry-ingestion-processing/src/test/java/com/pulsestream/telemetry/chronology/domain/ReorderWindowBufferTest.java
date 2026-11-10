package com.pulsestream.telemetry.chronology.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.shared.events.TelemetryContracts.MetricType;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetrySample;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetrySampleOrdered;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.ValidationStatus;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class ReorderWindowBufferTest {

    private static final Instant BASE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Duration WINDOW = Duration.ofSeconds(10);
    private static final ValidationStatus VALID = ValidationStatus.VALID;

    private ReorderWindowBuffer buffer;

    @BeforeEach
    void setUp() {
        buffer = new ReorderWindowBuffer(WINDOW);
    }

    private static TelemetrySample sample(String device, MetricType type, long seconds) {
        return new TelemetrySample(device, type, BASE.plusSeconds(seconds), BASE.plusSeconds(1000 - seconds), 1.0);
    }

    private static TelemetrySample sample(long seconds) {
        return sample("d1", MetricType.HEART_RATE, seconds);
    }

    private static List<Instant> times(List<TelemetrySampleOrdered> ordered) {
        return ordered.stream().map(o -> o.sample().tDevice()).toList();
    }

    @Test
    void constructor_nonPositiveWindow_throws() {
        assertThatThrownBy(() -> new ReorderWindowBuffer(Duration.ZERO))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new ReorderWindowBuffer(Duration.ofSeconds(-1)))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void accept_firstSample_isBufferedNotLate() {
        ReorderWindowBuffer.Result result = buffer.accept(sample(0), VALID);

        assertThat(result.released()).isEmpty();
        assertThat(result.late()).isFalse();
        assertThat(result.lateness()).isEqualTo(Duration.ZERO);
    }

    @Test
    void accept_watermarkAdvances_releasesSamplesUpToWatermarkMinusWindowInOrder() {
        buffer.accept(sample(5), VALID);
        buffer.accept(sample(0), VALID);

        ReorderWindowBuffer.Result result = buffer.accept(sample(16), VALID);

        assertThat(times(result.released())).containsExactly(BASE, BASE.plusSeconds(5));
        assertThat(buffer.drain()).hasSize(1);
        assertThat(result.late()).isFalse();
    }

    @Test
    void accept_sampleExactlyAtWatermarkMinusWindow_isReleased() {
        buffer.accept(sample(0), VALID);

        ReorderWindowBuffer.Result result = buffer.accept(sample(10), VALID);

        assertThat(times(result.released())).containsExactly(BASE);
        assertThat(result.released().get(0).status()).isEqualTo(VALID);
    }

    @Test
    void accept_olderThanWatermarkButInsideWindow_isReindexedChronologically() {
        buffer.accept(sample(8), VALID);
        buffer.accept(sample(5), VALID);
        buffer.accept(sample(3), VALID);

        ReorderWindowBuffer.Result result = buffer.accept(sample(20), VALID);

        assertThat(times(result.released()))
                .containsExactly(BASE.plusSeconds(3), BASE.plusSeconds(5), BASE.plusSeconds(8));
    }

    @Test
    void accept_sampleBeforeWatermarkMinusWindow_isLateWithLateness() {
        buffer.accept(sample(30), VALID);

        ReorderWindowBuffer.Result result = buffer.accept(sample(5), VALID);

        assertThat(result.late()).isTrue();
        assertThat(result.released()).isEmpty();
        assertThat(result.lateness()).isEqualTo(Duration.ofSeconds(25));
        assertThat(buffer.drain()).hasSize(1);
    }

    @Test
    void accept_sampleExactlyAtLateBoundary_isNotLate() {
        buffer.accept(sample(30), VALID);

        ReorderWindowBuffer.Result result = buffer.accept(sample(20), VALID);

        assertThat(result.late()).isFalse();
    }

    @Test
    void accept_equalTDevice_keepsArrivalOrder() {
        TelemetrySample first = new TelemetrySample("d1", MetricType.POWER, BASE, BASE.plusSeconds(9), 1.0);
        TelemetrySample second = new TelemetrySample("d1", MetricType.POWER, BASE, BASE.plusSeconds(1), 2.0);
        buffer.accept(first, VALID);
        buffer.accept(second, VALID);

        List<TelemetrySampleOrdered> released = buffer.accept(
                new TelemetrySample("d1", MetricType.POWER, BASE.plusSeconds(10), BASE, 3.0), VALID).released();

        assertThat(released).extracting(TelemetrySampleOrdered::sample).containsExactly(first, second);
    }

    @Test
    void accept_differentKeys_keepIndependentWatermarks() {
        buffer.accept(sample("d1", MetricType.HEART_RATE, 100), VALID);

        ReorderWindowBuffer.Result otherDevice = buffer.accept(sample("d2", MetricType.HEART_RATE, 0), VALID);
        ReorderWindowBuffer.Result otherMetric = buffer.accept(sample("d1", MetricType.POWER, 0), VALID);

        assertThat(otherDevice.late()).isFalse();
        assertThat(otherMetric.late()).isFalse();
    }

    @Test
    void accept_statusIsCarriedToOrderedSample() {
        buffer.accept(sample(0), ValidationStatus.VALIDATION_FAILED);

        List<TelemetrySampleOrdered> released = buffer.accept(sample(10), VALID).released();

        assertThat(released).extracting(TelemetrySampleOrdered::status)
                .containsExactly(ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void drain_releasesEverythingSortedPerKeyAndClearsState() {
        buffer.accept(sample("d1", MetricType.HEART_RATE, 4), VALID);
        buffer.accept(sample("d1", MetricType.HEART_RATE, 2), VALID);
        buffer.accept(sample("d2", MetricType.POWER, 3), VALID);

        List<TelemetrySampleOrdered> drained = buffer.drain();

        assertThat(drained).hasSize(3);
        assertThat(drained.stream().filter(o -> o.sample().deviceId().equals("d1")).map(o -> o.sample().tDevice()))
                .containsExactly(BASE.plusSeconds(2), BASE.plusSeconds(4));
        assertThat(buffer.drain()).isEmpty();
    }

    @Test
    void drain_clearsWatermark_soOldSampleIsNotLateAfterwards() {
        buffer.accept(sample(100), VALID);
        buffer.drain();

        assertThat(buffer.accept(sample(0), VALID).late()).isFalse();
    }
}
