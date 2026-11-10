package com.pulsestream.telemetry.broadcasting.application.port.out;

import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface TelemetryStreamGateway {

    Mono<Void> publish(BroadcastItem item);

    Flux<BroadcastItem> items();
}
