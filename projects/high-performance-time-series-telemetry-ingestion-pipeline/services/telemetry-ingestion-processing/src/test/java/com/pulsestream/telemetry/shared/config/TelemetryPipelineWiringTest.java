package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.eventlog.application.EventLogService;
import com.pulsestream.telemetry.ingestion.application.TelemetryEventBus;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.reordering.application.ReorderingService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

@ExtendWith(MockitoExtension.class)
class TelemetryPipelineWiringTest {

    @Mock
    private TelemetryEventBus eventBus;
    @Mock
    private ReorderingService reorderingService;
    @Mock
    private EventLogService eventLogService;

    private Sinks.Many<TelemetrySample> sink;
    private TelemetryPipelineWiring wiring;

    @BeforeEach
    void setUp() {
        sink = Sinks.many().multicast().directBestEffort();
        lenient().when(eventBus.stream()).thenReturn(sink.asFlux());
        lenient().when(reorderingService.windows(any()))
                .thenAnswer(invocation -> invocation.<Flux<TelemetrySample>>getArgument(0));
        lenient().when(eventLogService.record(any())).thenReturn(Mono.empty());
        wiring = new TelemetryPipelineWiring(eventBus, reorderingService, eventLogService);
    }

    private static TelemetrySample sample(long t) {
        return new TelemetrySample("dev-1", "temp", t, 1.5, t + 1, TelemetrySample.VALID);
    }

    @Test
    void start_called_subscribesToEventBusStreamOnce() {
        wiring.start();

        verify(eventBus, times(1)).stream();
    }

    @Test
    void start_sampleEmitted_recordsSampleInEventLog() {
        TelemetrySample sample = sample(10L);
        wiring.start();

        sink.tryEmitNext(sample);

        verify(eventLogService).record(sample);
    }

    @Test
    void start_called_feedsStreamThroughReorderingWindows() {
        wiring.start();

        verify(reorderingService).windows(any());
    }

    @Test
    void start_recordFails_subscriptionKeepsRecordingLaterSamples() {
        TelemetrySample first = sample(10L);
        TelemetrySample second = sample(20L);
        when(eventLogService.record(first)).thenReturn(Mono.error(new IllegalStateException("boom")));
        wiring.start();

        sink.tryEmitNext(first);
        sink.tryEmitNext(second);

        verify(eventLogService).record(second);
    }

    @Test
    void stop_afterStart_disposesSubscriptions() {
        wiring.start();

        wiring.stop();

        assertThat(sink.currentSubscriberCount()).isZero();
    }

    @Test
    void stop_afterStart_noFurtherSamplesRecorded() {
        wiring.start();
        wiring.stop();

        sink.tryEmitNext(sample(30L));

        verify(eventLogService, never()).record(any());
    }
}
