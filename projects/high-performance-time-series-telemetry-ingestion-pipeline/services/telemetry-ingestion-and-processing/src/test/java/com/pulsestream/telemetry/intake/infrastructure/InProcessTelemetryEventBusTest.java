package com.pulsestream.telemetry.intake.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.shared.event.TelemetryEvent;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

class InProcessTelemetryEventBusTest {

    private static TelemetryProperties properties(
            int capacity, TelemetryProperties.OverflowStrategy strategy, int attempts) {
        TelemetryProperties props = mock(TelemetryProperties.class);
        when(props.eventBufferCapacity()).thenReturn(capacity);
        when(props.overflowStrategy()).thenReturn(strategy);
        when(props.retryMaxAttempts()).thenReturn(attempts);
        when(props.retryBackoff()).thenReturn(Duration.ofMillis(1));
        return props;
    }

    @Test
    void publish_withSubscriber_deliversEventOnStream() {
        InProcessTelemetryEventBus bus =
                new InProcessTelemetryEventBus(properties(8, TelemetryProperties.OverflowStrategy.REJECT, 1));
        TelemetryEvent event = mock(TelemetryEvent.class);

        StepVerifier.create(bus.stream().take(1))
                .then(() -> StepVerifier.create(bus.publish(event)).verifyComplete())
                .expectNext(event)
                .verifyComplete();
    }

    @Test
    void publish_withoutSubscriber_completesWithoutError() {
        InProcessTelemetryEventBus bus =
                new InProcessTelemetryEventBus(properties(8, TelemetryProperties.OverflowStrategy.REJECT, 1));

        StepVerifier.create(bus.publish(mock(TelemetryEvent.class))).verifyComplete();
    }

    @Test
    void publish_whenBufferOverflowsWithReject_emitsIllegalStateException() {
        InProcessTelemetryEventBus bus =
                new InProcessTelemetryEventBus(properties(1, TelemetryProperties.OverflowStrategy.REJECT, 1));
        // A subscriber that never requests forces the buffer to fill up.
        bus.stream().subscribe(new reactor.core.publisher.BaseSubscriber<>() {
            @Override
            protected void hookOnSubscribe(org.reactivestreams.Subscription subscription) {
            }

            @Override
            protected void hookOnNext(TelemetryEvent value) {
            }
        });

        Flux<Void> publishes = Flux.range(0, 5)
                .concatMap(i -> bus.publish(mock(TelemetryEvent.class)));

        StepVerifier.create(publishes).expectError(IllegalStateException.class).verify();
    }

    @Test
    void publish_whenBufferOverflowsWithRetry_errorsAfterRetriesExhausted() {
        InProcessTelemetryEventBus bus =
                new InProcessTelemetryEventBus(properties(1, TelemetryProperties.OverflowStrategy.RETRY, 2));
        bus.stream().subscribe(new reactor.core.publisher.BaseSubscriber<>() {
            @Override
            protected void hookOnSubscribe(org.reactivestreams.Subscription subscription) {
            }

            @Override
            protected void hookOnNext(TelemetryEvent value) {
            }
        });

        Flux<Void> publishes = Flux.range(0, 5)
                .concatMap(i -> bus.publish(mock(TelemetryEvent.class)));

        StepVerifier.create(publishes).expectError().verify(Duration.ofSeconds(5));
    }

    @Test
    void stream_calledTwice_returnsFluxSharingSameSink() {
        InProcessTelemetryEventBus bus =
                new InProcessTelemetryEventBus(properties(8, TelemetryProperties.OverflowStrategy.REJECT, 1));
        TelemetryEvent event = mock(TelemetryEvent.class);

        assertThat(bus.stream()).isNotNull();
        StepVerifier.create(Flux.merge(bus.stream().take(1), bus.stream().take(1)))
                .then(() -> bus.publish(event).block(Duration.ofSeconds(1)))
                .expectNext(event, event)
                .verifyComplete();
    }
}
