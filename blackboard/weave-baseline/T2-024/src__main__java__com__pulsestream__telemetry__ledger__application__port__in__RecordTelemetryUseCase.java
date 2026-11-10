package com.pulsestream.telemetry.ledger.application.port.in;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryBackfillDetectedEvent;
import reactor.core.publisher.Mono;

public interface RecordTelemetryUseCase {

    Mono<TelemetryRecord> recordSequenced(TelemetrySampleEvent sample);

    Mono<TelemetryRecord> recordBackfill(TelemetryBackfillDetectedEvent event);
}
