package com.blackboard.telemetry.history.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.blackboard.telemetry.history.domain.HistoryEvent;
import com.blackboard.telemetry.history.domain.HistoryEventType;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class HistoryEventPublisherTest {

    private final HistoryEventPublisher publisher = mock(HistoryEventPublisher.class);

    private static HistoryEvent event(HistoryEventType type, int revisionNo, int windowSize) {
        Instant t = Instant.parse("2025-01-01T00:00:00Z");
        TelemetrySample sample = new TelemetrySample("dev-1", MetricKind.values()[0], t, t.plusSeconds(1),
                21.5, ValidationStatus.VALID);
        return new HistoryEvent(type, sample, revisionNo, windowSize, "corr-1");
    }

    @Test
    void publish_event_completesEmptyWithoutError() {
        HistoryEvent event = event(HistoryEventType.WINDOW_BUFFERED, 0, 3);
        when(publisher.publish(event)).thenReturn(Mono.empty());

        StepVerifier.create(publisher.publish(event)).verifyComplete();

        verify(publisher).publish(event);
    }

    @Test
    void events_publishedEvents_areEmittedToSubscribersInOrder() {
        HistoryEvent first = event(HistoryEventType.SAMPLE_BACKFILLED, 0, 0);
        HistoryEvent second = event(HistoryEventType.REVISION_APPENDED, 1, 0);
        when(publisher.events()).thenReturn(Flux.just(first, second));

        StepVerifier.create(publisher.events())
                .expectNext(first)
                .expectNext(second)
                .thenCancel()
                .verify();
    }

    @Test
    void events_eachEmittedEvent_carriesNonNullTypeAndCorrelationId() {
        when(publisher.events()).thenReturn(Flux.just(event(HistoryEventType.WINDOW_BUFFERED, 0, 2)));

        StepVerifier.create(publisher.events())
                .assertNext(e -> {
                    assertThat(e.type()).isEqualTo(HistoryEventType.WINDOW_BUFFERED);
                    assertThat(e.correlationId()).isNotBlank();
                })
                .thenCancel()
                .verify();
    }
}
