package com.pulsestream.telemetry.broadcasting.application.port.out;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;
import reactor.test.StepVerifier;

class TelemetryStreamGatewayTest {

    private static final class HotGateway implements TelemetryStreamGateway {
        private final Sinks.Many<BroadcastItem> sink = Sinks.many().multicast().directBestEffort();

        @Override
        public Mono<Void> publish(BroadcastItem item) {
            return Mono.fromRunnable(() -> sink.tryEmitNext(item));
        }

        @Override
        public Flux<BroadcastItem> items() {
            return sink.asFlux();
        }
    }

    private static BroadcastItem item() {
        return mock(BroadcastItem.class);
    }

    @Test
    void publish_withoutSubscribers_completesEmptyWithoutError() {
        TelemetryStreamGateway gateway = new HotGateway();

        StepVerifier.create(gateway.publish(item()))
                .expectComplete()
                .verify(Duration.ofSeconds(2));
    }

    @Test
    void items_afterPublish_deliversItemToSubscriber() {
        TelemetryStreamGateway gateway = new HotGateway();
        BroadcastItem item = item();

        StepVerifier.create(gateway.items().take(1))
                .then(() -> gateway.publish(item).block(Duration.ofSeconds(2)))
                .expectNext(item)
                .expectComplete()
                .verify(Duration.ofSeconds(2));
    }

    @Test
    void items_lateSubscriber_doesNotReceiveEarlierItems() {
        TelemetryStreamGateway gateway = new HotGateway();
        BroadcastItem early = item();
        BroadcastItem later = item();
        gateway.publish(early).block(Duration.ofSeconds(2));

        StepVerifier.create(gateway.items().take(1))
                .then(() -> gateway.publish(later).block(Duration.ofSeconds(2)))
                .expectNext(later)
                .expectComplete()
                .verify(Duration.ofSeconds(2));
    }

    @Test
    void publish_withSlowSubscriber_stillCompletesWithoutError() {
        TelemetryStreamGateway gateway = new HotGateway();
        StepVerifier slow = StepVerifier.create(gateway.items(), 0)
                .thenCancel()
                .verifyLater();

        StepVerifier.create(gateway.publish(item()))
                .expectComplete()
                .verify(Duration.ofSeconds(2));
        assertThat(slow).isNotNull();
    }

    @Test
    void items_withTwoSubscribers_eachReceivesPublishedItem() {
        TelemetryStreamGateway gateway = new HotGateway();
        BroadcastItem item = item();
        Flux<BroadcastItem> first = gateway.items().take(1);
        Flux<BroadcastItem> second = gateway.items().take(1);

        StepVerifier.create(Flux.merge(first, second))
                .then(() -> gateway.publish(item).block(Duration.ofSeconds(2)))
                .expectNext(item, item)
                .expectComplete()
                .verify(Duration.ofSeconds(2));
    }
}
