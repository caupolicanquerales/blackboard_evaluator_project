package com.pulsestream.telemetry.shared.events;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

public class BoundedEventChannel<T> {

    private final String name;

    private final Sinks.Many<T> sink;

    public BoundedEventChannel(String name, int capacity) {
        if (capacity <= 0) {
            throw new IllegalArgumentException("capacity must be positive");
        }
        this.name = name;
        this.sink = Sinks.many().multicast().onBackpressureBuffer(capacity, false);
    }

    public Mono<Void> offer(T event) {
        return publish(event);
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

    public Mono<Void> publish(T event) {
        if (event == null) {
            return Mono.error(new NullPointerException("event must not be null"));
        }
        return Mono.defer(() -> {
            Sinks.EmitResult result;
            do {
                result = sink.tryEmitNext(event);
            } while (result == Sinks.EmitResult.FAIL_NON_SERIALIZED);
            if (result == Sinks.EmitResult.FAIL_OVERFLOW) {
                return Mono.<Void>error(new OverflowException(name));
            }
            return Mono.<Void>empty();
        });
    }
}
