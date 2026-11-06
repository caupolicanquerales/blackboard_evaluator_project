package com.pulsestream.telemetry.intake.application;

import reactor.core.publisher.Mono;

public interface ReorderingEventPort {

    Mono<Void> publish(Object event);
}
