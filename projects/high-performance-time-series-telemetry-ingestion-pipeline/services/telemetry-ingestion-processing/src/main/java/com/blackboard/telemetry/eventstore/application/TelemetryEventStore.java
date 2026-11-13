package com.blackboard.telemetry.eventstore.application;

import com.blackboard.telemetry.eventstore.domain.TelemetryRecord;
import java.time.Instant;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface TelemetryEventStore {

    Mono<TelemetryRecord> append(TelemetryRecord record);

    Flux<TelemetryRecord> findLatestInRange(String deviceId, String metric, Instant from, Instant to);
}
