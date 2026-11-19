package com.pulsestream.telemetry.ingestion.application;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.ingestion.domain.TelemetryRevision;
import java.time.Instant;
import reactor.core.publisher.Mono;

public interface TelemetryRecordRepository {

    Mono<Boolean> appendRecord(TelemetrySample sample);

    Mono<Void> appendRevision(TelemetryRevision revision);

    Mono<TelemetryRevision> findLatestRevision(String deviceId, String metric, Instant tDevice);
}
