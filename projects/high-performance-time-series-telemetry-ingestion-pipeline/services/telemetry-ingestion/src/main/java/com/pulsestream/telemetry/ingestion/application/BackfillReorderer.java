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
        return arrivals.windowTimeout(bufferCapacity, reorderWindow)
                .concatMap(Flux::collectList)
                .concatMap(this::sortAndRecordMoves);
    }

    private Flux<TelemetrySample> sortAndRecordMoves(List<TelemetrySample> arrivalOrder) {
        List<TelemetrySample> sorted = new ArrayList<>(arrivalOrder);
        sorted.sort(Comparator.comparing(TelemetrySample::tDevice));
        for (int position = 0; position < sorted.size(); position++) {
            if (arrivalOrder.indexOf(sorted.get(position)) > position) {
                metrics.backfillReordered();
            }
        }
        return Flux.fromIterable(sorted);
    }
}
