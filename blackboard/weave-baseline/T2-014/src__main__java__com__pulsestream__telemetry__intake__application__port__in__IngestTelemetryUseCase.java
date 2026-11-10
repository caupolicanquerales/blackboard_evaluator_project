package com.pulsestream.telemetry.intake.application.port.in;

import com.pulsestream.telemetry.intake.application.IngressPacket;
import reactor.core.publisher.Mono;

public interface IngestTelemetryUseCase {

    Mono<Integer> ingest(IngressPacket packet);
}
