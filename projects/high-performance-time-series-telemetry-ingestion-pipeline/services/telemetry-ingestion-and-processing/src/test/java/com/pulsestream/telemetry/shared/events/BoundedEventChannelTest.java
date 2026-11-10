package com.pulsestream.telemetry.shared.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import reactor.test.StepVerifier;

class BoundedEventChannelTest {

    @ParameterizedTest
    @ValueSource(ints = {0, -1, -100})
    void constructor_nonPositiveCapacity_throwsIllegalArgumentException(int capacity) {
        assertThatThrownBy(() -> new BoundedEventChannel<String>("events", capacity))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void name_afterConstruction_returnsGivenName() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>("telemetry", 4);

        assertThat(channel.name()).isEqualTo("telemetry");
    }

    @Test
    void publish_nullEvent_isRejected() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>("telemetry", 4);

        assertThatThrownBy(() -> channel.publish(null).block())
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @Test
    void publish_withinCapacity_completesEmpty() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>("telemetry", 4);

        StepVerifier.create(channel.publish("a")).verifyComplete();
    }

    @Test
    void stream_subscriberBeforePublish_receivesEventsInOrder() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>("telemetry", 4);

        StepVerifier.create(channel.stream().take(2))
                .then(() -> {
                    channel.publish("a").block();
                    channel.publish("b").block();
                })
                .expectNext("a", "b")
                .verifyComplete();
    }

    @Test
    void stream_eventsPublishedBeforeSubscription_areBufferedAndReplayed() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>("telemetry", 4);
        channel.publish("a").block();
        channel.publish("b").block();

        StepVerifier.create(channel.stream().take(2))
                .expectNext("a", "b")
                .verifyComplete();
    }

    @Test
    void publish_beyondCapacityWithoutConsumer_emitsOverflowException() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>("telemetry", 2);
        channel.publish("a").block();
        channel.publish("b").block();

        StepVerifier.create(channel.publish("c"))
                .expectErrorSatisfies(error -> assertThat(error)
                        .isInstanceOf(BoundedEventChannel.OverflowException.class))
                .verify();
    }

    @Test
    void publish_overflow_doesNotDropBufferedEvents() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>("telemetry", 2);
        channel.publish("a").block();
        channel.publish("b").block();
        channel.publish("c").onErrorResume(e -> reactor.core.publisher.Mono.empty()).block();

        StepVerifier.create(channel.stream().take(2))
                .expectNext("a", "b")
                .verifyComplete();
    }

    @Test
    void overflowException_isRuntimeExceptionMentioningChannelName() {
        BoundedEventChannel<String> channel = new BoundedEventChannel<>("telemetry", 1);
        channel.publish("a").block();

        assertThatThrownBy(() -> channel.publish("b").block())
                .isInstanceOf(BoundedEventChannel.OverflowException.class)
                .isInstanceOf(RuntimeException.class)
                .hasMessageContaining("telemetry");
    }
}
