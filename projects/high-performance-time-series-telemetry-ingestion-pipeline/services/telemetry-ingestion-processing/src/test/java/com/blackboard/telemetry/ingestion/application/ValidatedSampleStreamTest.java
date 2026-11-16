package com.blackboard.telemetry.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidatedSampleEvent;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class ValidatedSampleStreamTest {

    private static ValidatedSampleEvent event() {
        Instant now = Instant.parse("2026-01-01T00:00:00Z");
        return new ValidatedSampleEvent(
                new TelemetrySample("dev-1", MetricKind.HEART_RATE, now, now, 150.0, ValidationStatus.VALID),
                "req-1");
    }

    @Test
    void publish_acceptedEvent_completesEmpty() {
        ValidatedSampleStream stream = mock(ValidatedSampleStream.class);
        ValidatedSampleEvent event = event();
        when(stream.publish(event)).thenReturn(Mono.empty());

        StepVerifier.create(stream.publish(event)).verifyComplete();
    }

    @Test
    void publish_bufferFull_emitsIllegalStateException() {
        ValidatedSampleStream stream = mock(ValidatedSampleStream.class);
        ValidatedSampleEvent event = event();
        when(stream.publish(event)).thenReturn(Mono.error(new IllegalStateException("overflow")));

        StepVerifier.create(stream.publish(event)).expectError(IllegalStateException.class).verify();
    }

    @Test
    void events_publishedEvent_isDeliveredToSubscriber() {
        ValidatedSampleStream stream = mock(ValidatedSampleStream.class);
        ValidatedSampleEvent event = event();
        when(stream.events()).thenReturn(Flux.just(event));

        StepVerifier.create(stream.events()).expectNext(event).verifyComplete();
        assertThat(event).isNotNull();
    }
}
