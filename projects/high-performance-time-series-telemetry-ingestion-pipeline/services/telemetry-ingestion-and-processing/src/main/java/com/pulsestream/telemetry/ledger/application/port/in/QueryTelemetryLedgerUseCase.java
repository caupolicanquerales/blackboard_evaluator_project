package com.pulsestream.telemetry.ledger.application.port.in;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import reactor.core.publisher.Flux;

public interface QueryTelemetryLedgerUseCase {

    Flux<TelemetryRecord> history(String deviceId, Instant from, Instant toExclusive);

    Flux<TelemetryRecord> latestHistory(String deviceId, Instant from, Instant toExclusive);

    Flux<TelemetryRecord> revisionChain(String deviceId, String metric, Instant tDevice);
}
