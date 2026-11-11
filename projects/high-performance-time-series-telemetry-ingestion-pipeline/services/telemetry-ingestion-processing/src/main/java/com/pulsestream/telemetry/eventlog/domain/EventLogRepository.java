package com.pulsestream.telemetry.eventlog.domain;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface EventLogRepository {

    Mono<Void> appendRevision(TelemetrySample revision);

    Flux<TelemetrySample> findByDeviceAndRange(String deviceId, long fromEpochMs, long toEpochMs);

    Mono<Boolean> appendRecord(TelemetrySample sample);
}
