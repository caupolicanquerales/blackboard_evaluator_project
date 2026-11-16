package com.blackboard.telemetry.history.application;

import com.blackboard.telemetry.history.domain.RevisionReason;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import java.time.Instant;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface TelemetryHistoryRepository {

    Mono<Long> appendSample(TelemetrySample sample);

    Mono<Integer> appendRevision(long sampleId, RevisionReason reason, double value, Instant tIngress);

    Mono<Instant> findLatestTDevice(String deviceId, MetricKind metric);

    Flux<TelemetrySample> findWindow(String deviceId, MetricKind metric, Instant from, Instant to, int limit);
}
