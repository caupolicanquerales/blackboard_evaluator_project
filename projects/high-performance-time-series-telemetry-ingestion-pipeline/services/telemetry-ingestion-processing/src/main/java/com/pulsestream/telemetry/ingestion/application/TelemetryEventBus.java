package com.pulsestream.telemetry.ingestion.application;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;

public interface TelemetryEventBus {

    Flux<TelemetrySample> stream();

    public reactor.core.publisher.Mono<Void> publish(TelemetrySample sample);
}
