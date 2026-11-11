package com.pulsestream.telemetry.ingestion.application;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface TelemetryEventBus {

    Flux<TelemetrySample> stream();

    Mono<Void> publish(TelemetrySample sample);
}
