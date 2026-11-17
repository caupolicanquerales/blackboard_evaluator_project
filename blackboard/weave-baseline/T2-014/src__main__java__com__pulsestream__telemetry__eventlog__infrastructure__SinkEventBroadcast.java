package com.pulsestream.telemetry.eventlog.infrastructure;

import com.pulsestream.telemetry.eventlog.application.EventBroadcast;
import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;

public class SinkEventBroadcast implements EventBroadcast {

    private final Sinks.Many<EventRecord> sink;

    public SinkEventBroadcast(TelemetryProperties properties) {
        this.sink = Sinks.many().multicast().onBackpressureBuffer(properties.bufferCapacity(), false);
    }

    @Override
    public Flux<EventRecord> stream() {
        return sink.asFlux();
    }

    public synchronized boolean publish(EventRecord record) {
        return sink.tryEmitNext(record) == Sinks.EmitResult.OK;
    }
}
