package com.blackboard.telemetry.ingestion.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import com.blackboard.telemetry.ingestion.domain.ValidatedSampleEvent;
import com.blackboard.telemetry.shared.config.TelemetryProperties;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.Disposable;
import reactor.test.StepVerifier;

class InMemoryValidatedSampleStreamTest {

    private static InMemoryValidatedSampleStream streamWithCapacity(int capacity) {
        TelemetryProperties properties = new TelemetryProperties(
                Duration.ofSeconds(1), 1, capacity, 1, Duration.ofMillis(100), List.of());
        return new InMemoryValidatedSampleStream(properties);
    }

    @Test
    void publish_eventsPublished_deliversInOrderToSubscriber() {
        InMemoryValidatedSampleStream stream = streamWithCapacity(4);
        ValidatedSampleEvent first = mock(ValidatedSampleEvent.class);
        ValidatedSampleEvent second = mock(ValidatedSampleEvent.class);

        StepVerifier.create(stream.publish(first)).verifyComplete();
        StepVerifier.create(stream.publish(second)).verifyComplete();

        StepVerifier.create(stream.events().take(2))
                .expectNext(first, second)
                .verifyComplete();
    }

    @Test
    void publish_beyondCapacity_errorsWithIllegalStateException() {
        InMemoryValidatedSampleStream stream = streamWithCapacity(1);
        StepVerifier.create(stream.publish(mock(ValidatedSampleEvent.class))).verifyComplete();

        StepVerifier.create(stream.publish(mock(ValidatedSampleEvent.class)))
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void publish_afterSubscriberCancel_stillCompletesAndDelivers() {
        InMemoryValidatedSampleStream stream = streamWithCapacity(2);
        Disposable subscription = stream.events().subscribe();
        subscription.dispose();
        ValidatedSampleEvent event = mock(ValidatedSampleEvent.class);

        StepVerifier.create(stream.publish(event)).verifyComplete();

        StepVerifier.create(stream.events().take(1))
                .expectNext(event)
                .verifyComplete();
        assertThat(subscription.isDisposed()).isTrue();
    }
}
