package com.pulsestream.telemetry.distribution.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import reactor.test.StepVerifier;

class InProcessEventBusTest {

    private static TelemetryEvent event(String metric) {
        Instant t = Instant.parse("2026-01-01T00:00:00Z");
        return new TelemetryEvent(1, TelemetryEvent.Type.SAMPLE,
                TelemetryEvent.keyOf("dev-1", metric, t, 1),
                "dev-1", metric, t, 1, 1.5, null, "pub-1");
    }

    @Test
    void publish_withSubscriber_returnsTrueAndDelivers() {
        InProcessEventBus bus = new InProcessEventBus(8, new TelemetryMetrics(new SimpleMeterRegistry()));
        TelemetryEvent e = event("temp");

        StepVerifier.create(bus.events().take(1).doOnSubscribe(s ->
                        StepVerifier.create(bus.publish(e)).expectNext(true).verifyComplete()))
                .expectNext(e)
                .verifyComplete();
    }

    @Test
    void publish_overflowWithoutDemand_returnsFalseAndCountsDrop() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        InProcessEventBus bus = new InProcessEventBus(1, new TelemetryMetrics(registry));
        bus.events().subscribe(new reactor.core.publisher.BaseSubscriber<TelemetryEvent>() {
            @Override
            protected void hookOnSubscribe(org.reactivestreams.Subscription s) {
            }
        });
        bus.publish(event("a")).block();

        Boolean second = bus.publish(event("b")).block();
        Boolean third = bus.publish(event("c")).block();

        assertThat(second && third).isFalse();
        assertThat(registry.get("telemetry.broadcast.dropped").counter().count()).isGreaterThanOrEqualTo(1.0);
    }

    @Test
    void events_subscriberDisconnects_busCancelsWithoutError() {
        InProcessEventBus bus = new InProcessEventBus(4, new TelemetryMetrics(new SimpleMeterRegistry()));

        StepVerifier.create(bus.events())
                .thenCancel()
                .verify();

        StepVerifier.create(bus.publish(event("x"))).expectNextCount(1).verifyComplete();
    }
}
