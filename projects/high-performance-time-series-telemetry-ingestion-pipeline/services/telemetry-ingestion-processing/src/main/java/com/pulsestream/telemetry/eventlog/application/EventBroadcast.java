package com.pulsestream.telemetry.eventlog.application;

import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import reactor.core.publisher.Flux;

public interface EventBroadcast {

    boolean publish(EventRecord record);

    Flux<EventRecord> stream();
}
