package com.pulsestream.telemetry.ingestion.infrastructure;

import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;
import com.pulsestream.telemetry.ingestion.application.TelemetryEventBus;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;

@Component
public class InMemoryTelemetryEventBus implements TelemetryEventBus {

    private final Sinks.Many<TelemetrySample> sink;

    public InMemoryTelemetryEventBus(TelemetryProperties properties) {
        this.sink = Sinks.many().multicast().onBackpressureBuffer(properties.busBufferCapacity());
    }

    @Override
    public Flux<TelemetrySample> stream() {
        return sink.asFlux();
    }

    @Override
    public Mono<Void> publish(TelemetrySample sample) {
        return Mono.defer(() -> {
            Sinks.EmitResult result;
            do {
                result = sink.tryEmitNext(sample);
            } while (result == Sinks.EmitResult.FAIL_NON_SERIALIZED);
            if (result.isFailure() && result != Sinks.EmitResult.FAIL_ZERO_SUBSCRIBER) {
                return Mono.<Void>error(new IllegalStateException("Telemetry event bus emit failed: " + result));
            }
            return Mono.<Void>empty();
        });
    }
}
