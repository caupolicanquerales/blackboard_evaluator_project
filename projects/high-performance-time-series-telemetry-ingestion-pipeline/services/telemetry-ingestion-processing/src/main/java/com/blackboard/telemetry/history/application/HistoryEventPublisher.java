package com.blackboard.telemetry.history.application;

import com.blackboard.telemetry.history.domain.HistoryEvent;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface HistoryEventPublisher {

    Mono<Void> publish(HistoryEvent event);

    Flux<HistoryEvent> events();
}
