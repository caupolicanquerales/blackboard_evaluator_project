package com.pulsestream.telemetry.distribution.infrastructure;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;
import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;
import com.pulsestream.telemetry.ingestion.application.EventPublisher;
import com.pulsestream.telemetry.distribution.application.TelemetryEventSource;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;

public class InProcessEventBus implements EventPublisher, TelemetryEventSource {

    private static final String OVERFLOW_REASON = "bus-overflow";

    private final Sinks.Many<TelemetryEvent> sink;

    private final TelemetryMetrics metrics;

    @Override
    public Mono<Boolean> publish(TelemetryEvent event) {
        return Mono.fromSupplier(() -> emit(event));
    }

    @Override
    public Flux<TelemetryEvent> events() {
        return sink.asFlux();
    }

    private boolean emit(TelemetryEvent event) {
        Sinks.EmitResult result;
        do {
            result = sink.tryEmitNext(event);
        } while (result == Sinks.EmitResult.FAIL_NON_SERIALIZED);
        if (result == Sinks.EmitResult.FAIL_OVERFLOW) {
            metrics.broadcastDropped(OVERFLOW_REASON);
        }
        return result.isSuccess();
    }

    public InProcessEventBus(int capacity, TelemetryMetrics metrics) {
        this.metrics = metrics;
        this.sink = Sinks.many().multicast().onBackpressureBuffer(capacity, false);
    }
}
