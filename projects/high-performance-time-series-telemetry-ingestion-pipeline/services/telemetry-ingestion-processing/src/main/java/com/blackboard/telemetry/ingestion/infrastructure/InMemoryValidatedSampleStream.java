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

    private final Duration emitRetryTimeout;

    public InMemoryValidatedSampleStream(TelemetryProperties properties) {
        this.sink = Sinks.many().multicast().onBackpressureBuffer(properties.validatedStreamCapacity(), false);
        this.emitRetryTimeout = properties.emitRetryTimeout();
    }

    public Flux<ValidatedSampleEvent> events() {
        return sink.asFlux();
    }

    public Mono<Void> publish(ValidatedSampleEvent event) {
        return Mono.defer(() -> {
            long deadline = System.nanoTime() + emitRetryTimeout.toNanos();
            Sinks.EmitResult result = sink.tryEmitNext(event);
            while (result == Sinks.EmitResult.FAIL_NON_SERIALIZED && System.nanoTime() < deadline) {
                result = sink.tryEmitNext(event);
            }
            if (result.isFailure()) {
                return Mono.<Void>error(new IllegalStateException("Validated sample stream emit failed: " + result));
            }
            return Mono.<Void>empty();
        });
    }
}
