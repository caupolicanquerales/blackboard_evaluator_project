package com.pulsestream.telemetry.broadcasting.infrastructure;

import java.util.Objects;
import com.pulsestream.telemetry.broadcasting.application.port.out.TelemetryStreamGateway;
import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import reactor.core.publisher.BufferOverflowStrategy;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

public class ReactorTelemetryStreamGateway {

    private final Sinks.Many<BroadcastItem> sink = Sinks.many().multicast().directBestEffort();

    private final int subscriberBuffer;

    public ReactorTelemetryStreamGateway(int subscriberBuffer) {
        if (subscriberBuffer <= 0) {
            throw new IllegalArgumentException("subscriberBuffer must be greater than zero");
        }
        this.subscriberBuffer = subscriberBuffer;
    }

    @Override
    public Mono<Void> publish(BroadcastItem item) {
        Objects.requireNonNull(item, "item must not be null");
        return Mono.fromRunnable(() -> sink.tryEmitNext(item));
    }

    @Override
    public Flux<BroadcastItem> items() {
        return sink.asFlux().onBackpressureBuffer(subscriberBuffer, BufferOverflowStrategy.DROP_OLDEST);
    }

    public void ReactorTelemetryStreamGateway(int subscriberBuffer) {
        if (subscriberBuffer <= 0) {
            throw new IllegalArgumentException("subscriberBuffer must be greater than zero");
        }
        this.subscriberBuffer = subscriberBuffer;
    }
}
