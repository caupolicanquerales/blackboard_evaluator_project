package com.pulsestream.telemetry.broadcasting.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;

import com.pulsestream.telemetry.broadcasting.application.port.out.TelemetryStreamGateway;
import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

class ReactorTelemetryStreamGatewayTest {

    private static final Duration TIMEOUT = Duration.ofSeconds(2);

    private static BroadcastItem item() {
        return mock(BroadcastItem.class);
    }

    @ParameterizedTest
    @ValueSource(ints = {0, -1})
    void constructor_nonPositiveBuffer_throws(int buffer) {
        assertThatThrownBy(() -> new ReactorTelemetryStreamGateway(buffer))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void gateway_implementsOutboundPort() {
        assertThat(new ReactorTelemetryStreamGateway(4)).isInstanceOf(TelemetryStreamGateway.class);
    }

    @Test
    void publish_noSubscribers_completesWithoutError() {
        ReactorTelemetryStreamGateway gateway = new ReactorTelemetryStreamGateway(4);

        StepVerifier.create(gateway.publish(item())).verifyComplete();
    }

    @Test
    void items_subscriberBeforePublish_receivesItem() {
        ReactorTelemetryStreamGateway gateway = new ReactorTelemetryStreamGateway(4);
        BroadcastItem item = item();

        StepVerifier.create(gateway.items().take(1))
                .then(() -> gateway.publish(item).block(TIMEOUT))
                .expectNext(item)
                .verifyComplete();
    }

    @Test
    void items_subscriberAfterPublish_doesNotReceiveEarlierItem() {
        ReactorTelemetryStreamGateway gateway = new ReactorTelemetryStreamGateway(4);
        BroadcastItem early = item();
        BroadcastItem later = item();
        gateway.publish(early).block(TIMEOUT);

        StepVerifier.create(gateway.items().take(1))
                .then(() -> gateway.publish(later).block(TIMEOUT))
                .expectNext(later)
                .verifyComplete();
    }

    @Test
    void items_multipleSubscribers_eachReceivesItem() {
        ReactorTelemetryStreamGateway gateway = new ReactorTelemetryStreamGateway(4);
        BroadcastItem item = item();
        Flux<BroadcastItem> first = gateway.items().take(1);
        Flux<BroadcastItem> second = gateway.items().take(1);

        StepVerifier.create(Flux.merge(first, second))
                .then(() -> gateway.publish(item).block(TIMEOUT))
                .expectNext(item, item)
                .verifyComplete();
    }

    @Test
    void publish_slowSubscriberWithNoDemand_neverFailsPublisher() {
        ReactorTelemetryStreamGateway gateway = new ReactorTelemetryStreamGateway(2);
        StepVerifier slow = StepVerifier.create(gateway.items(), 0)
                .thenAwait()
                .thenCancel()
                .verifyLater();

        for (int i = 0; i < 10; i++) {
            StepVerifier.create(gateway.publish(item())).verifyComplete();
        }
        slow.verify(TIMEOUT);
    }

    @Test
    void items_bufferOverflow_dropsOldestKeepsLatest() {
        ReactorTelemetryStreamGateway gateway = new ReactorTelemetryStreamGateway(2);
        BroadcastItem a = item();
        BroadcastItem b = item();
        BroadcastItem c = item();

        StepVerifier.create(gateway.items(), 0)
                .then(() -> {
                    gateway.publish(a).block(TIMEOUT);
                    gateway.publish(b).block(TIMEOUT);
                    gateway.publish(c).block(TIMEOUT);
                })
                .thenRequest(3)
                .expectNext(b, c)
                .thenCancel()
                .verify(TIMEOUT);
    }
}
