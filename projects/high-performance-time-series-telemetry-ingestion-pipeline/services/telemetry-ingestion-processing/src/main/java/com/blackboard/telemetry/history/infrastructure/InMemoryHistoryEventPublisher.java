package com.blackboard.telemetry.history.infrastructure;

import java.time.Duration;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;
import com.blackboard.telemetry.history.application.HistoryEventPublisher;
import com.blackboard.telemetry.history.domain.HistoryEvent;
import com.blackboard.telemetry.shared.config.TelemetryProperties;

public class InMemoryHistoryEventPublisher implements HistoryEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(InMemoryHistoryEventPublisher.class);

    private final Sinks.Many<HistoryEvent> sink;

    private final Duration emitRetryTimeout;

    public InMemoryHistoryEventPublisher(TelemetryProperties properties) {
        this.sink = Sinks.many().replay().limit(properties.broadcastCapacity());
        this.emitRetryTimeout = properties.emitRetryTimeout();
    }

    @Override
    public Flux<HistoryEvent> events() {
        return sink.asFlux();
    }

    public Mono<Void> publish(HistoryEvent event) {
        return Mono.fromRunnable(() -> {
            sink.emitNext(event, Sinks.EmitFailureHandler.busyLooping(emitRetryTimeout));
            log.info("event broadcast downstream");
        });
    }
}
