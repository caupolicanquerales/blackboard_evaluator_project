package com.pulsestream.telemetry.broadcasting.application;

import com.pulsestream.telemetry.broadcasting.application.port.in.BroadcastTelemetryUseCase;
import com.pulsestream.telemetry.broadcasting.application.port.out.TelemetryStreamGateway;
import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryStreamPublishedEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;
import java.time.Clock;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Service
public class BroadcastingService {

    private final TelemetryStreamGateway gateway;

    private final BoundedEventChannel<TelemetryStreamPublishedEvent> streamPublications;

    private final Clock clock;

    public BroadcastingService(TelemetryStreamGateway gateway, BoundedEventChannel<TelemetryStreamPublishedEvent> streamPublications, Clock clock) {
        this.gateway = gateway;
        this.streamPublications = streamPublications;
        this.clock = clock;
    }

    @Override
    public Mono<Void> broadcastWindow(TelemetryWindowClosedEvent window) {
        return Mono.defer(() -> publish(BroadcastItem.window(window)));
    }

    @Override
    public Flux<BroadcastItem> stream(String deviceId) {
        Flux<BroadcastItem> items = gateway.items();
        return deviceId == null ? items : items.filter(item -> deviceId.equals(item.deviceId()));
    }

    private Mono<Void> publish(BroadcastItem item) {
        return gateway.publish(item).then(Mono.defer(() -> streamPublications.publish(new TelemetryStreamPublishedEvent(item.kind().name(), item.deviceId(), item.samples().size(), clock.instant())).onErrorResume(error -> Mono.empty())));
    }

    @Override
    public Mono<Void> broadcastSample(TelemetrySampleEvent sample) {
        return Mono.defer(() -> publish(BroadcastItem.sample(sample)));
    }
}
