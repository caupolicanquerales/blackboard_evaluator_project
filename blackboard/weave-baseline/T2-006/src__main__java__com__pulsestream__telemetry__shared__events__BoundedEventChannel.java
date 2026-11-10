package com.pulsestream.telemetry.shared.events;

import java.util.Objects;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

public class BoundedEventChannel {

    private final String name;

    private final Sinks.Many<T> sink;

    public Mono<Void> publish(T event) {
        return Mono.defer(() -> {
            Objects.requireNonNull(event, "event must not be null");
            Sinks.EmitResult result;
            do {
                result = sink.tryEmitNext(event);
            } while (result == Sinks.EmitResult.FAIL_NON_SERIALIZED);
            if (result.isSuccess()) {
                return Mono.<Void>empty();
            }
            if (result == Sinks.EmitResult.FAIL_OVERFLOW) {
                return Mono.<Void>error(new OverflowException(name));
            }
            return Mono.<Void>error(new IllegalStateException("channel " + name + " emission failed: " + result));
        });
    }

    public Flux<T> stream() {
        return sink.asFlux();
    }

    public String name() {
        return name;
    }

    public static class OverflowException extends RuntimeException {

        public OverflowException(String channelName) {
            super("Event channel overflow: " + channelName);
        }
    }

    public void BoundedEventChannel(String name, int capacity) {
        if (capacity <= 0) {
            throw new IllegalArgumentException("capacity must be positive");
        }
        this.name = Objects.requireNonNull(name, "name must not be null");
        this.sink = Sinks.many().multicast().onBackpressureBuffer(capacity, false);
    }
}
