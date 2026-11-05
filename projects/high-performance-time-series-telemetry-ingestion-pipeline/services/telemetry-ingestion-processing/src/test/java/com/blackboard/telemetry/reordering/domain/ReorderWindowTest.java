package com.blackboard.telemetry.reordering.domain;
import com.blackboard.telemetry.shared.events.TelemetryEvents;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.blackboard.telemetry.reordering.domain.ReorderWindow.Outcome;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidated;
import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;

class ReorderWindowTest {

    private static final Instant BASE = Instant.parse("2026-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2026-01-01T10:05:00Z");
    private static final Instant FAR_FUTURE = BASE.plusSeconds(10_000);

    private ReorderWindow window;

    @BeforeEach
    void setUp() {
        window = new ReorderWindow();
    }

    private static Instant at(long seconds) {
        return BASE.plusSeconds(seconds);
    }

    private static TelemetrySampleValidated sample(String device, long seconds, Instant tIngress, double value) {
        return new TelemetrySampleValidated(device, at(seconds), tIngress, "heart_rate", value,
                ValidationStatus.VALID);
    }

    private static TelemetrySampleValidated sample(String device, long seconds) {
        return sample(device, seconds, T_INGRESS, 100.0 + seconds);
    }

    private static List<Instant> tDevices(List<TelemetrySampleValidated> samples) {
        return samples.stream().map(TelemetrySampleValidated::tDevice).toList();
    }

    @Test
    void drain_samplesOfferedOutOfOrder_releasesAscendingByTDevice() {
        window.offer(sample("d1", 30));
        window.offer(sample("d1", 10));
        window.offer(sample("d1", 20));

        assertThat(tDevices(window.drain(FAR_FUTURE))).containsExactly(at(10), at(20), at(30));
    }

    @Test
    void offer_sampleAheadOfWatermark_returnsInOrder() {
        window.offer(sample("d1", 10));

        assertThat(window.offer(sample("d1", 20))).isEqualTo(Outcome.IN_ORDER);
    }

    @Test
    void offer_sampleLateWithinSixtySeconds_returnsBackfilled() {
        window.offer(sample("d1", 100));

        assertThat(window.offer(sample("d1", 70))).isEqualTo(Outcome.BACKFILLED);
    }

    @Test
    void offer_sampleExactlySixtySecondsLate_returnsBackfilled() {
        window.offer(sample("d1", 100));

        assertThat(window.offer(sample("d1", 40))).isEqualTo(Outcome.BACKFILLED);
    }

    @Test
    void drain_backfilledSample_isReleasedBeforeNewerSamples() {
        window.offer(sample("d1", 100));
        window.offer(sample("d1", 70));

        assertThat(tDevices(window.drain(FAR_FUTURE))).containsExactly(at(70), at(100));
    }

    @Test
    void offer_sampleOlderThanSixtySeconds_returnsTooLate() {
        window.offer(sample("d1", 100));

        assertThat(window.offer(sample("d1", 39))).isEqualTo(Outcome.TOO_LATE);
    }

    @Test
    void drain_tooLateSample_isNotInserted() {
        window.offer(sample("d1", 100));
        window.offer(sample("d1", 39));

        assertThat(tDevices(window.drain(FAR_FUTURE))).containsExactly(at(100));
    }

    @Test
    void drain_equalTDevice_keepsInsertionOrder() {
        window.offer(sample("d1", 10, T_INGRESS, 1.0));
        window.offer(sample("d1", 10, T_INGRESS, 2.0));
        window.offer(sample("d1", 10, T_INGRESS, 3.0));

        assertThat(window.drain(FAR_FUTURE))
                .extracting(TelemetrySampleValidated::value)
                .containsExactly(1.0, 2.0, 3.0);
    }

    @Test
    void offer_otherDeviceAdvancedWatermark_doesNotMakeSampleLate() {
        window.offer(sample("d2", 500));

        assertThat(window.offer(sample("d1", 10))).isEqualTo(Outcome.IN_ORDER);
    }

    @Test
    void drain_multipleDevices_keepsEachDeviceOrderedByTDevice() {
        window.offer(sample("d1", 30));
        window.offer(sample("d2", 25));
        window.offer(sample("d1", 10));
        window.offer(sample("d2", 5));

        List<TelemetrySampleValidated> drained = window.drain(FAR_FUTURE);

        assertThat(tDevices(drained.stream().filter(s -> s.deviceId().equals("d1")).toList()))
                .containsExactly(at(10), at(30));
        assertThat(tDevices(drained.stream().filter(s -> s.deviceId().equals("d2")).toList()))
                .containsExactly(at(5), at(25));
    }

    @Test
    void drain_ingressOrderContradictsDeviceOrder_ordersByTDevice() {
        window.offer(sample("d1", 10, T_INGRESS.plusSeconds(30), 1.0));
        window.offer(sample("d1", 20, T_INGRESS, 2.0));

        assertThat(tDevices(window.drain(FAR_FUTURE))).containsExactly(at(10), at(20));
    }

    @Test
    void offer_lateJudgedByTDeviceNotTIngress_returnsBackfilledDespiteLateIngress() {
        window.offer(sample("d1", 100, T_INGRESS, 1.0));

        assertThat(window.offer(sample("d1", 80, T_INGRESS.plusSeconds(3_600), 2.0)))
                .isEqualTo(Outcome.BACKFILLED);
    }

    @Test
    void drain_watermarkBeforeNewestSample_retainsNewerSamples() {
        window.offer(sample("d1", 10));
        window.offer(sample("d1", 50));

        assertThat(tDevices(window.drain(at(20)))).containsExactly(at(10));
        assertThat(tDevices(window.drain(FAR_FUTURE))).containsExactly(at(50));
    }

    @Test
    void drain_emptyWindow_returnsEmptyList() {
        assertThat(window.drain(FAR_FUTURE)).isEmpty();
    }
}
