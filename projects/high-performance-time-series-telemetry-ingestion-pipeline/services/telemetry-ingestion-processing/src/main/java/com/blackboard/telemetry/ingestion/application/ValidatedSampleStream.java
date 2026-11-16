package com.blackboard.telemetry.ingestion.application;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import com.blackboard.telemetry.ingestion.domain.ValidatedSampleEvent;

public interface ValidatedSampleStream {

    Mono<Void> publish(ValidatedSampleEvent event);

    Flux<ValidatedSampleEvent> events();
}
