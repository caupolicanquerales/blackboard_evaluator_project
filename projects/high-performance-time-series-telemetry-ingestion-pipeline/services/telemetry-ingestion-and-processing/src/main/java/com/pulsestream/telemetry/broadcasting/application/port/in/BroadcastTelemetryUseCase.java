package com.pulsestream.telemetry.broadcasting.application.port.in;

import reactor.core.publisher.Mono;
import reactor.core.publisher.Flux;
import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;

public interface BroadcastTelemetryUseCase {

    Mono<Void> broadcastSample(TelemetrySampleEvent sample);

    Mono<Void> broadcastWindow(TelemetryWindowClosedEvent window);

    Flux<BroadcastItem> stream(String deviceId);
}
