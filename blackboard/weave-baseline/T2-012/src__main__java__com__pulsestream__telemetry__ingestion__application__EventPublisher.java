package com.pulsestream.telemetry.ingestion.application;
import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;

import reactor.core.publisher.Mono;

public interface EventPublisher {

    Mono<Boolean> publish(TelemetryEvent event);
}
