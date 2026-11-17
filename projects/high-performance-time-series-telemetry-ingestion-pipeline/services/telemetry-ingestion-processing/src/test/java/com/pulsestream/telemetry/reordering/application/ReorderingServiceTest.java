package com.pulsestream.telemetry.reordering.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.shared.observability.StepLog;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentMatchers;

class ReorderingServiceTest {

    private static final Instant BASE = Instant.parse("2025-01-01T10:00:00Z");

    private StepLog stepLog;
    private SimpleMeterRegistry meters;
    private ReorderingService service;

    @BeforeEach
    void setUp() {
        stepLog = mock(StepLog.class);
        meters = new SimpleMeterRegistry();
        var props = new TelemetryProperties(60, 1024, 30, 240, 0, 2500, 0, 220, 45);
        service = new ReorderingService(props, stepLog, meters);
    }

    private static TelemetrySample sample(String metric, long deviceOffsetSec, long ingressOffsetSec) {
        return new TelemetrySample("dev-1", metric, BASE.plusSeconds(deviceOffsetSec),
                BASE.plusSeconds(ingressOffsetSec), 1.0, "PENDING", "corr-1");
    }

    @Test
    void reorderWindow_outOfOrder_returnsSortedByTDevice() {
        var result = service.reorderWindow(List.of(sample("a", 3, 4), sample("b", 1, 4), sample("c", 2, 4)));

        assertThat(result).extracting(TelemetrySample::metric).containsExactly("b", "c", "a");
    }

    @Test
    void reorderWindow_equalTDevice_keepsArrivalOrder() {
        var result = service.reorderWindow(List.of(sample("first", 1, 2), sample("second", 1, 2)));

        assertThat(result).extracting(TelemetrySample::metric).containsExactly("first", "second");
    }

    @Test
    void reorderWindow_emptyWindow_returnsEmptyWithoutMetersOrLogs() {
        var result = service.reorderWindow(List.of());

        assertThat(result).isEmpty();
        assertThat(meters.getMeters()).isEmpty();
        verify(stepLog, never()).emit(ArgumentMatchers.anyString(), ArgumentMatchers.any());
    }

    @Test
    void reorderWindow_inWindowBackfill_countsLateInWindowAndLogsBackfill() {
        service.reorderWindow(List.of(sample("a", 10, 11), sample("b", 5, 11)));

        assertThat(meters.get("telemetry.reordering.late").tag("kind", "in_window").counter().count())
                .isEqualTo(1.0);
        verify(stepLog).emit("reordering.backfill.applied", "corr-1");
    }

    @Test
    void reorderWindow_beyondWindowSample_isReturnedAndCountedBeyondWindow() {
        var result = service.reorderWindow(List.of(sample("late", 0, 120)));

        assertThat(result).hasSize(1);
        assertThat(meters.get("telemetry.reordering.late").tag("kind", "beyond_window").counter().count())
                .isEqualTo(1.0);
    }

    @Test
    void reorderWindow_nonEmptyWindow_recordsLatencyTimerAndFlushStep() {
        service.reorderWindow(List.of(sample("a", 1, 2)));

        assertThat(meters.get("telemetry.pipeline.latency").tag("stage", "reordering").timer().count())
                .isEqualTo(1L);
        verify(stepLog).emit("reordering.window.flushed", "corr-1");
    }

    @Test
    void reorderWindow_orderedWindow_doesNotCountInWindowBackfill() {
        service.reorderWindow(List.of(sample("a", 1, 2), sample("b", 2, 3)));

        assertThat(meters.find("telemetry.reordering.late").tag("kind", "in_window").counter()).isNull();
        verify(stepLog, never()).emit("reordering.backfill.applied", "corr-1");
    }
}
