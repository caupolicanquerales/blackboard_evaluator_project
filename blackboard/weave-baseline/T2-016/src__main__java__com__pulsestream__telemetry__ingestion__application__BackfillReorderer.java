package com.pulsestream.telemetry.ingestion.application;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import reactor.core.publisher.Flux;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;

public class BackfillReorderer {

    private final Duration reorderWindow;

    private final int bufferCapacity;

    private final TelemetryMetrics metrics;

    public BackfillReorderer(Duration reorderWindow, int bufferCapacity, TelemetryMetrics metrics) {
        this.reorderWindow = Objects.requireNonNull(reorderWindow, "reorderWindow");
        this.bufferCapacity = bufferCapacity;
        this.metrics = Objects.requireNonNull(metrics, "metrics");
    }

    public Flux<TelemetrySample> reorder(Flux<TelemetrySample> arrivals) {
        return arrivals.windowTimeout(bufferCapacity, reorderWindow).concatMap(Flux::collectList).concatMap(batch -> {
            List<TelemetrySample> sorted = new ArrayList<>(batch);
            sorted.sort(Comparator.comparing(TelemetrySample::tDevice));
            for (int i = 0; i < sorted.size(); i++) {
                if (batch.indexOf(sorted.get(i)) > i) {
                    metrics.backfillReordered();
                }
            }
            return Flux.fromIterable(sorted);
        });
    }
}
