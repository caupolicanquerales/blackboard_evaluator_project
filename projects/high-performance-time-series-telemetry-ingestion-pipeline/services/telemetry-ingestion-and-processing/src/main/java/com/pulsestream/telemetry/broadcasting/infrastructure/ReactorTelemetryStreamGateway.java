package com.pulsestream.telemetry.broadcasting.infrastructure;

import com.pulsestream.telemetry.broadcasting.application.port.out.TelemetryStreamGateway;
import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import reactor.core.publisher.BufferOverflowStrategy;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

public class ReactorTelemetryStreamGateway implements TelemetryStreamGateway {

    private final int subscriberBuffer;

    private final Sinks.Many<BroadcastItem> sink;

    public ReactorTelemetryStreamGateway(int subscriberBuffer) {
        if (subscriberBuffer <= 0) {
            throw new IllegalArgumentException("subscriberBuffer must be greater than zero");
        }
        this.subscriberBuffer = subscriberBuffer;
        this.sink = Sinks.many().multicast().directBestEffort();
    }

    @Override
    public Flux<BroadcastItem> items() {
        return sink.asFlux().onBackpressureBuffer(subscriberBuffer, BufferOverflowStrategy.DROP_OLDEST);
    }

    @Override
    public Mono<Void> publish(BroadcastItem item) {
        return Mono.fromRunnable(() -> sink.tryEmitNext(item));
    }
}
