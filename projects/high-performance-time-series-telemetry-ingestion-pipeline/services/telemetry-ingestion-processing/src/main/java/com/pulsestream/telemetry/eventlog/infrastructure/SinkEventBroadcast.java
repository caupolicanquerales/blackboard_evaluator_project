package com.pulsestream.telemetry.eventlog.infrastructure;

import com.pulsestream.telemetry.eventlog.application.EventBroadcast;
import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;

public class SinkEventBroadcast implements EventBroadcast {

    private final Sinks.Many<EventRecord> sink;
    private final int capacity;
    private int buffered;

    public SinkEventBroadcast(TelemetryProperties properties) {
        this.capacity = properties.bufferCapacity();
        this.sink = Sinks.many().multicast().onBackpressureBuffer(capacity, false);
    }

    @Override
    public Flux<EventRecord> stream() {
        return sink.asFlux();
    }

    public synchronized boolean publish(EventRecord record) {
        if (sink.currentSubscriberCount() > 0) {
            buffered = 0;
        } else if (buffered >= capacity) {
            return false;
        }
        boolean accepted = sink.tryEmitNext(record) == Sinks.EmitResult.OK;
        if (accepted && sink.currentSubscriberCount() == 0) {
            buffered++;
        }
        return accepted;
    }
}
