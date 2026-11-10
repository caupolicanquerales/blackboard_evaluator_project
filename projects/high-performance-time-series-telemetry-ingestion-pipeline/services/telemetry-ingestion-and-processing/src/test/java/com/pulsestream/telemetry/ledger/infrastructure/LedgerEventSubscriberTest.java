package com.pulsestream.telemetry.ledger.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.timeout;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ledger.application.DeadLetterSink;
import com.pulsestream.telemetry.ledger.application.RecordTelemetryService;
import com.pulsestream.telemetry.ledger.domain.EventRevision;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.shared.event.TelemetryEvent;
import com.pulsestream.telemetry.shared.event.TelemetryEventBus;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

class LedgerEventSubscriberTest {

    private final TelemetryEventBus bus = mock(TelemetryEventBus.class);
    private final RecordTelemetryService service = mock(RecordTelemetryService.class);
    private final DeadLetterSink deadLetters = mock(DeadLetterSink.class);
    private final TelemetryProperties props = mock(TelemetryProperties.class);
    private final Sinks.Many<TelemetryEvent> events = Sinks.many().multicast().onBackpressureBuffer();

    private LedgerEventSubscriber subscriber() {
        when(props.retryMaxAttempts()).thenReturn(2);
        when(props.retryBackoff()).thenReturn(Duration.ofMillis(1));
        when(bus.stream()).thenReturn(events.asFlux());
        when(deadLetters.reject(any(), any())).thenReturn(Mono.empty());
        return new LedgerEventSubscriber(bus, service, deadLetters, props);
    }

    @Test
    void isRunning_beforeStart_returnsFalse() {
        assertThat(subscriber().isRunning()).isFalse();
    }

    @Test
    void start_marksRunningAndStopClearsIt() {
        LedgerEventSubscriber subscriber = subscriber();

        subscriber.start();
        boolean runningAfterStart = subscriber.isRunning();
        subscriber.stop();

        assertThat(runningAfterStart).isTrue();
        assertThat(subscriber.isRunning()).isFalse();
    }

    @Test
    void start_withPublishedEvent_recordsEvent() {
        LedgerEventSubscriber subscriber = subscriber();
        TelemetryEvent event = mock(TelemetryEvent.class);
        when(service.record(event)).thenReturn(Mono.just(mock(EventRevision.class)));

        subscriber.start();
        events.tryEmitNext(event);

        verify(service, timeout(2000)).record(event);
        subscriber.stop();
    }

    @Test
    void start_whenRecordKeepsFailing_sendsEventToDeadLetterSink() {
        LedgerEventSubscriber subscriber = subscriber();
        TelemetryEvent event = mock(TelemetryEvent.class);
        when(service.record(event)).thenReturn(Mono.error(new IllegalStateException("down")));

        subscriber.start();
        events.tryEmitNext(event);

        verify(deadLetters, timeout(3000)).reject(eq(event), any(Throwable.class));
        subscriber.stop();
    }

    @Test
    void start_afterDeadLetter_continuesProcessingNextEvents() {
        LedgerEventSubscriber subscriber = subscriber();
        TelemetryEvent bad = mock(TelemetryEvent.class);
        TelemetryEvent good = mock(TelemetryEvent.class);
        when(service.record(bad)).thenReturn(Mono.error(new IllegalStateException("down")));
        when(service.record(good)).thenReturn(Mono.just(mock(EventRevision.class)));

        subscriber.start();
        events.tryEmitNext(bad);
        events.tryEmitNext(good);

        verify(service, timeout(3000)).record(good);
        subscriber.stop();
    }

    @Test
    void stop_afterStop_noLongerRecordsEvents() {
        LedgerEventSubscriber subscriber = subscriber();
        TelemetryEvent event = mock(TelemetryEvent.class);
        subscriber.start();
        subscriber.stop();

        events.tryEmitNext(event);

        verify(service, times(0)).record(any());
    }
}
