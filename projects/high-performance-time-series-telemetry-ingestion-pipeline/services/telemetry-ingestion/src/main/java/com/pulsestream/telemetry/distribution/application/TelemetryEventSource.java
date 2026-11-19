package com.pulsestream.telemetry.distribution.application;

import reactor.core.publisher.Flux;
import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;

public interface TelemetryEventSource {

    Flux<TelemetryEvent> events();
}
