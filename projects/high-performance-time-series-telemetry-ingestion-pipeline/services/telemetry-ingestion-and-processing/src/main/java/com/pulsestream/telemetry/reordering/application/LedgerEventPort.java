package com.pulsestream.telemetry.reordering.application;

import reactor.core.publisher.Mono;

public interface LedgerEventPort {

    Mono<Void> publish(Object event);
}
