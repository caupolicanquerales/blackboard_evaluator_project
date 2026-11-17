package com.pulsestream.telemetry.reordering.application;

import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.shared.observability.StepLog;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.TimeUnit;

public class ReorderingService {

    private static final Comparator<TelemetrySample> BY_DEVICE_TIME = Comparator.comparing(TelemetrySample::tDevice);

    private final TelemetryProperties properties;

    private final StepLog stepLog;

    private final MeterRegistry meterRegistry;

    public ReorderingService(TelemetryProperties properties, StepLog stepLog, MeterRegistry meterRegistry) {
        this.properties = properties;
        this.stepLog = stepLog;
        this.meterRegistry = meterRegistry;
    }

    public List<TelemetrySample> reorderWindow(List<TelemetrySample> window) {
        if (window.isEmpty()) {
            return List.of();
        }
        long startNanos = System.nanoTime();
        recordLateSamples(window);
        List<TelemetrySample> sorted = window.stream().sorted(BY_DEVICE_TIME).toList();
        Timer.builder("telemetry.pipeline.latency").tag("stage", "reordering").register(meterRegistry).record(System.nanoTime() - startNanos, TimeUnit.NANOSECONDS);
        stepLog.emit("reordering.window.flushed", window.get(0).correlationId());
        return sorted;
    }

    private void recordLateSamples(List<TelemetrySample> window) {
        Duration maxLag = Duration.ofSeconds(properties.reorderWindowSeconds());
        Instant maxSeen = null;
        for (TelemetrySample sample : window) {
            if (maxSeen != null && sample.tDevice().isBefore(maxSeen)) {
                countLate("in_window");
                stepLog.emit("reordering.backfill.applied", sample.correlationId());
            } else {
                maxSeen = sample.tDevice();
            }
            if (Duration.between(sample.tDevice(), sample.tIngress()).compareTo(maxLag) > 0) {
                countLate("beyond_window");
            }
        }
    }

    private void countLate(String kind) {
        meterRegistry.counter("telemetry.reordering.late", "kind", kind).increment();
    }
}
