package com.pulsestream.telemetry.ledger.application.port.out;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface TelemetryLedgerRepository {

    Mono<TelemetryRecord> append(TelemetryRecord record);

    Flux<TelemetryRecord> findHistory(String deviceId, Instant fromInclusive, Instant toExclusive);

    Mono<TelemetryRecord> findLatestRevision(String deviceId, String metric, Instant tDevice);

    Flux<TelemetryRecord> findRevisionChain(String deviceId, String metric, Instant tDevice);
}
