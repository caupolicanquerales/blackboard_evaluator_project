package com.pulsestream.telemetry.eventlog.domain;

import reactor.core.publisher.Mono;
import reactor.core.publisher.Flux;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;

public interface EventLogRepository {

    Mono<Void> appendRevision(TelemetrySample revision);

    Flux<TelemetrySample> findByDeviceAndRange(String deviceId, long fromEpochMs, long toEpochMs);

    public reactor.core.publisher.Mono<Boolean> appendRecord(TelemetrySample sample);
}
