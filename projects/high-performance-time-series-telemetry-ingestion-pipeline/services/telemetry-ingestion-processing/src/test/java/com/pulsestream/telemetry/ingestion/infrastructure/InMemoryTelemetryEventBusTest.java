package com.pulsestream.telemetry.ingestion.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import java.time.Duration;
import java.util.Map;
import org.junit.jupiter.api.Test;
import reactor.test.StepVerifier;

class InMemoryTelemetryEventBusTest {

    private static final TelemetrySample SAMPLE =
            new TelemetrySample("d1", "temp", 1000L, 20.0, 1001L, TelemetrySample.VALID);

    private final TelemetryProperties properties = new TelemetryProperties(
            60L, 8, Map.of("temp", new TelemetryProperties.Bounds(-10.0, 50.0)));

    @Test
    void publish_afterSubscribe_deliversSampleToSubscriber() {
        InMemoryTelemetryEventBus bus = new InMemoryTelemetryEventBus(properties);

        StepVerifier.create(bus.stream().take(1))
                .then(() -> bus.publish(SAMPLE).block(Duration.ofSeconds(1)))
                .expectNext(SAMPLE)
                .verifyComplete();
    }

    @Test
    void publish_multipleSubscribers_eachReceivesSample() {
        InMemoryTelemetryEventBus bus = new InMemoryTelemetryEventBus(properties);
        var first = StepVerifier.create(bus.stream().take(1)).expectNext(SAMPLE).expectComplete().verifyLater();
        var second = StepVerifier.create(bus.stream().take(1)).expectNext(SAMPLE).expectComplete().verifyLater();

        bus.publish(SAMPLE).block(Duration.ofSeconds(1));

        first.verify(Duration.ofSeconds(1));
        second.verify(Duration.ofSeconds(1));
    }

    @Test
    void publish_withoutSubscribers_completesWithoutBlocking() {
        InMemoryTelemetryEventBus bus = new InMemoryTelemetryEventBus(properties);

        StepVerifier.create(bus.publish(SAMPLE)).verifyComplete();
    }

    @Test
    void publish_manySamplesWithinCapacity_allCompleteAndAreDelivered() {
        InMemoryTelemetryEventBus bus = new InMemoryTelemetryEventBus(properties);
        var verifier = StepVerifier.create(bus.stream().take(properties.busBufferCapacity()))
                .expectNextCount(properties.busBufferCapacity())
                .expectComplete().verifyLater();

        for (int i = 0; i < properties.busBufferCapacity(); i++) {
            assertThat(bus.publish(SAMPLE).block(Duration.ofSeconds(1))).isNull();
        }

        verifier.verify(Duration.ofSeconds(1));
    }
}
