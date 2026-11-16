package com.blackboard.telemetry.history.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.blackboard.telemetry.history.application.ReorderHistoryService;
import com.blackboard.telemetry.ingestion.application.ValidatedSampleStream;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidatedSampleEvent;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

@ExtendWith(MockitoExtension.class)
class PipelineSubscriberTest {

    @Mock
    private ValidatedSampleStream stream;

    @Mock
    private ReorderHistoryService service;

    private static ValidatedSampleEvent event(String correlationId) {
        TelemetrySample sample = new TelemetrySample("dev-1", MetricKind.values()[0],
                Instant.parse("2026-01-01T00:00:00Z"), Instant.parse("2026-01-01T00:00:01Z"),
                21.5, ValidationStatus.VALID);
        return new ValidatedSampleEvent(sample, correlationId);
    }

    @Test
    void isRunning_beforeStart_returnsFalse() {
        assertThat(new PipelineSubscriber(stream, service).isRunning()).isFalse();
    }

    @Test
    void isRunning_afterStart_returnsTrue() {
        when(stream.events()).thenReturn(Sinks.many().multicast().<ValidatedSampleEvent>directBestEffort().asFlux());
        PipelineSubscriber subscriber = new PipelineSubscriber(stream, service);

        subscriber.start();

        assertThat(subscriber.isRunning()).isTrue();
        subscriber.stop();
    }

    @Test
    void isRunning_afterStop_returnsFalse() {
        when(stream.events()).thenReturn(Sinks.many().multicast().<ValidatedSampleEvent>directBestEffort().asFlux());
        PipelineSubscriber subscriber = new PipelineSubscriber(stream, service);
        subscriber.start();

        subscriber.stop();

        assertThat(subscriber.isRunning()).isFalse();
    }

    @Test
    void start_eventEmitted_delegatesToServiceHandle() {
        ValidatedSampleEvent event = event("req-1");
        when(stream.events()).thenReturn(Flux.just(event));
        when(service.handle(event)).thenReturn(Mono.empty());

        new PipelineSubscriber(stream, service).start();

        verify(service).handle(event);
    }

    @Test
    void start_handleErrorOnFirstEvent_stillHandlesNextEvent() {
        ValidatedSampleEvent first = event("req-1");
        ValidatedSampleEvent second = event("req-2");
        when(stream.events()).thenReturn(Flux.just(first, second));
        when(service.handle(first)).thenReturn(Mono.error(new IllegalStateException("boom")));
        when(service.handle(second)).thenReturn(Mono.empty());

        new PipelineSubscriber(stream, service).start();

        verify(service).handle(second);
    }
}
