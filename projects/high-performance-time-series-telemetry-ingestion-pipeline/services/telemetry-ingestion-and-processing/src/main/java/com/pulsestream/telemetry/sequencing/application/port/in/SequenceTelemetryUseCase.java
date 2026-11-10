package com.pulsestream.telemetry.sequencing.application.port.in;

import reactor.core.publisher.Mono;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;

public interface SequenceTelemetryUseCase {

    Mono<Void> onSampleReceived(TelemetrySampleEvent sample);

    Mono<Void> flush();
}
