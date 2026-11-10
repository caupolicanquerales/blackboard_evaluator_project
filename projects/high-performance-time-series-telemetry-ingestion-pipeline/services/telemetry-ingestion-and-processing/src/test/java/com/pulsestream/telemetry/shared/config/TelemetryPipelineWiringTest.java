package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.broadcasting.application.port.in.BroadcastTelemetryUseCase;
import com.pulsestream.telemetry.ledger.application.port.in.RecordTelemetryUseCase;
import com.pulsestream.telemetry.sequencing.application.port.in.SequenceTelemetryUseCase;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetryBackfillDetectedEvent;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;

class TelemetryPipelineWiringTest {

    private BoundedEventChannel<TelemetrySampleEvent> validated;
    private BoundedEventChannel<TelemetrySampleEvent> sequenced;
    private BoundedEventChannel<TelemetryBackfillDetectedEvent> backfills;
    private BoundedEventChannel<TelemetryWindowClosedEvent> windows;
    private SequenceTelemetryUseCase sequence;
    private RecordTelemetryUseCase record;
    private BroadcastTelemetryUseCase broadcast;
    private TelemetryPipelineWiring wiring;

    @BeforeEach
    void setUp() {
        validated = new BoundedEventChannel<>("validated", 8);
        sequenced = new BoundedEventChannel<>("sequenced", 8);
        backfills = new BoundedEventChannel<>("backfills", 8);
        windows = new BoundedEventChannel<>("windows", 8);
        sequence = mock(SequenceTelemetryUseCase.class);
        record = mock(RecordTelemetryUseCase.class);
        broadcast = mock(BroadcastTelemetryUseCase.class);
        when(sequence.onSampleReceived(any())).thenReturn(Mono.empty());
        when(sequence.flush()).thenReturn(Mono.empty());
        when(record.recordSequenced(any())).thenReturn(Mono.empty());
        when(record.recordBackfill(any())).thenReturn(Mono.empty());
        when(broadcast.broadcastSample(any())).thenReturn(Mono.empty());
        when(broadcast.broadcastWindow(any())).thenReturn(Mono.empty());
        wiring = new TelemetryPipelineWiring(
                validated, sequenced, backfills, windows, sequence, record, broadcast);
    }

    @AfterEach
    void tearDown() {
        wiring.stop();
    }

    @Test
    void isRunning_beforeStart_isFalse() {
        assertThat(wiring.isRunning()).isFalse();
    }

    @Test
    void start_marksWiringAsRunning() {
        wiring.start();

        assertThat(wiring.isRunning()).isTrue();
    }

    @Test
    void start_validatedSample_isForwardedToSequencing() {
        TelemetrySampleEvent sample = mock(TelemetrySampleEvent.class);
        wiring.start();

        validated.publish(sample).block();

        verify(sequence).onSampleReceived(sample);
        verify(record, never()).recordSequenced(any());
        verify(broadcast, never()).broadcastSample(any());
    }

    @Test
    void start_sequencedSample_isForwardedToLedgerAndBroadcastIndependently() {
        TelemetrySampleEvent sample = mock(TelemetrySampleEvent.class);
        wiring.start();

        sequenced.publish(sample).block();

        verify(record).recordSequenced(sample);
        verify(broadcast).broadcastSample(sample);
        verify(sequence, never()).onSampleReceived(any());
    }

    @Test
    void start_backfillDetection_isForwardedToLedger() {
        TelemetryBackfillDetectedEvent event = mock(TelemetryBackfillDetectedEvent.class);
        wiring.start();

        backfills.publish(event).block();

        verify(record).recordBackfill(event);
    }

    @Test
    void start_closedWindow_isForwardedToBroadcast() {
        TelemetryWindowClosedEvent window = mock(TelemetryWindowClosedEvent.class);
        wiring.start();

        windows.publish(window).block();

        verify(broadcast).broadcastWindow(window);
    }

    @Test
    void start_samplesInOrder_areProcessedInPublicationOrder() {
        TelemetrySampleEvent first = mock(TelemetrySampleEvent.class);
        TelemetrySampleEvent second = mock(TelemetrySampleEvent.class);
        wiring.start();

        validated.publish(first).block();
        validated.publish(second).block();

        org.mockito.InOrder inOrder = org.mockito.Mockito.inOrder(sequence);
        inOrder.verify(sequence).onSampleReceived(first);
        inOrder.verify(sequence).onSampleReceived(second);
    }

    @Test
    void start_sequencingFailure_doesNotKillSubscription() {
        TelemetrySampleEvent bad = mock(TelemetrySampleEvent.class);
        TelemetrySampleEvent good = mock(TelemetrySampleEvent.class);
        when(sequence.onSampleReceived(bad)).thenReturn(Mono.error(new IllegalStateException("boom")));
        wiring.start();

        validated.publish(bad).block();
        validated.publish(good).block();

        verify(sequence).onSampleReceived(good);
    }

    @Test
    void start_synchronousUseCaseException_doesNotKillSubscription() {
        TelemetryWindowClosedEvent bad = mock(TelemetryWindowClosedEvent.class);
        TelemetryWindowClosedEvent good = mock(TelemetryWindowClosedEvent.class);
        when(broadcast.broadcastWindow(bad)).thenThrow(new IllegalStateException("boom"));
        wiring.start();

        windows.publish(bad).block();
        windows.publish(good).block();

        verify(broadcast).broadcastWindow(good);
    }

    @Test
    void start_ledgerFailure_doesNotAffectBroadcastConsumer() {
        TelemetrySampleEvent sample = mock(TelemetrySampleEvent.class);
        when(record.recordSequenced(sample)).thenReturn(Mono.error(new IllegalStateException("boom")));
        wiring.start();

        sequenced.publish(sample).block();

        verify(broadcast).broadcastSample(sample);
    }

    @Test
    void stop_afterStart_marksNotRunningAndFlushesSequencingOnce() {
        wiring.start();

        wiring.stop();

        assertThat(wiring.isRunning()).isFalse();
        verify(sequence, times(1)).flush();
    }

    @Test
    void stop_afterStart_disposesSubscriptions() {
        TelemetrySampleEvent sample = mock(TelemetrySampleEvent.class);
        TelemetryBackfillDetectedEvent backfill = mock(TelemetryBackfillDetectedEvent.class);
        TelemetryWindowClosedEvent window = mock(TelemetryWindowClosedEvent.class);
        wiring.start();
        wiring.stop();

        validated.publish(sample).block();
        sequenced.publish(sample).block();
        backfills.publish(backfill).block();
        windows.publish(window).block();

        verify(sequence, never()).onSampleReceived(any());
        verify(record, never()).recordSequenced(any());
        verify(record, never()).recordBackfill(any());
        verify(broadcast, never()).broadcastSample(any());
        verify(broadcast, never()).broadcastWindow(any());
    }
}
