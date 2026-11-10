package com.pulsestream.telemetry.shared.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import reactor.test.StepVerifier;

class BoundedEventChannelTest {

    @ParameterizedTest
    @ValueSource(ints = {0, -1, Integer.MIN_VALUE})
    void constructor_nonPositiveCapacity_throwsIllegalArgument(int capacity) {
        assertThatThrownBy(() -> new BoundedEventChannel<String>(capacity))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_positiveCapacity_createsChannel() {
        assertThat(new BoundedEventChannel<String>(1)).isNotNull();
    }

    @Test
    void publish_withBufferSpace_completesEmpty() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>(4);

        StepVerifier.create(channel.publish("event")).verifyComplete();
    }

    @Test
    void stream_activeSubscriber_receivesPublishedEventsInOrder() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>(4);

        StepVerifier.create(channel.stream())
                .then(() -> {
                    channel.publish("a").block();
                    channel.publish("b").block();
                })
                .expectNext("a", "b")
                .thenCancel()
                .verify();
    }

    @Test
    void publish_beforeSubscription_buffersEventsForLateSubscriber() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>(2);
        channel.publish("a").block();
        channel.publish("b").block();

        StepVerifier.create(channel.stream())
                .expectNext("a", "b")
                .thenCancel()
                .verify();
    }

    @Test
    void publish_bufferFull_emitsIllegalStateException() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>(2);
        channel.publish("a").block();
        channel.publish("b").block();

        StepVerifier.create(channel.publish("c"))
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void publish_bufferFull_doesNotThrowSynchronously() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>(1);
        channel.publish("a").block();

        assertThat(channel.publish("b")).isNotNull();
    }
}
