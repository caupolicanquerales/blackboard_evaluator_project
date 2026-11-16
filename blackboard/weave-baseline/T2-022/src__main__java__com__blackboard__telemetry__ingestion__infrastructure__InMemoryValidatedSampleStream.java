package com.blackboard.telemetry.ingestion.infrastructure;
import java.time.Duration;

import reactor.core.publisher.Mono;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;
import com.blackboard.telemetry.ingestion.application.ValidatedSampleStream;
import com.blackboard.telemetry.shared.config.TelemetryProperties;
import com.blackboard.telemetry.ingestion.domain.ValidatedSampleEvent;

public class InMemoryValidatedSampleStream implements ValidatedSampleStream {

    private final Sinks.Many<ValidatedSampleEvent> sink;

    private final java.time.Duration emitRetryTimeout;

    public InMemoryValidatedSampleStream(TelemetryProperties properties) {
        this.sink = Sinks.many().multicast().onBackpressureBuffer(properties.validatedStreamCapacity(), false);
        this.emitRetryTimeout = properties.emitRetryTimeout();
    }

    public Flux<ValidatedSampleEvent> events() {
        return sink.asFlux();
    }

    public Mono<Void> publish(ValidatedSampleEvent event) {
        return Mono.fromRunnable(() -> sink.emitNext(event, Sinks.EmitFailureHandler.busyLooping(emitRetryTimeout))).onErrorMap(Sinks.EmissionException.class, e -> new IllegalStateException("Validated sample stream emit failed: " + e.getReason(), e)).then();
    }
}
