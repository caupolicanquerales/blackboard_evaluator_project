package com.pulsestream.telemetry.eventlog.application;

import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import java.time.Instant;
import reactor.core.publisher.Mono;

public interface EventLogRepository {

    Mono<EventRecord> append(TelemetrySample sample);

    Mono<EventRecord> findLatest(String deviceId, String metric, Instant tDevice);
}
