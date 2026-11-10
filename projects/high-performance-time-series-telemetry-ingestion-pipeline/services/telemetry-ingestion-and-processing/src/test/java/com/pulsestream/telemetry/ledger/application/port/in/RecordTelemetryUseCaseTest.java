package com.pulsestream.telemetry.ledger.application.port.in;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import com.pulsestream.telemetry.shared.events.TelemetryBackfillDetectedEvent;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class RecordTelemetryUseCaseTest {

    @Mock
    private RecordTelemetryUseCase useCase;
    @Mock
    private TelemetrySampleEvent sample;
    @Mock
    private TelemetryBackfillDetectedEvent backfill;
    @Mock
    private TelemetryRecord appended;
    @Mock
    private TelemetryRecord existing;

    @Test
    void recordSequenced_newSample_emitsAppendedRecord() {
        when(useCase.recordSequenced(sample)).thenReturn(Mono.just(appended));

        StepVerifier.create(useCase.recordSequenced(sample))
                .expectNext(appended)
                .verifyComplete();

        verify(useCase).recordSequenced(sample);
        verifyNoMoreInteractions(useCase);
    }

    @Test
    void recordSequenced_idempotentReplay_emitsExistingRecord() {
        when(useCase.recordSequenced(sample)).thenReturn(Mono.just(existing));

        StepVerifier.create(useCase.recordSequenced(sample))
                .expectNext(existing)
                .verifyComplete();
    }

    @Test
    void recordSequenced_failure_propagatesErrorSignal() {
        when(useCase.recordSequenced(sample))
                .thenReturn(Mono.error(new IllegalStateException("ledger unavailable")));

        StepVerifier.create(useCase.recordSequenced(sample))
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void recordBackfill_newBackfill_emitsAppendedRecord() {
        when(useCase.recordBackfill(backfill)).thenReturn(Mono.just(appended));

        StepVerifier.create(useCase.recordBackfill(backfill))
                .expectNext(appended)
                .verifyComplete();

        verify(useCase).recordBackfill(backfill);
        verifyNoMoreInteractions(useCase);
    }

    @Test
    void recordBackfill_idempotentReplay_emitsExistingRecord() {
        when(useCase.recordBackfill(backfill)).thenReturn(Mono.just(existing));

        StepVerifier.create(useCase.recordBackfill(backfill))
                .expectNext(existing)
                .verifyComplete();
    }

    @Test
    void recordBackfill_failure_propagatesErrorSignal() {
        when(useCase.recordBackfill(backfill))
                .thenReturn(Mono.error(new IllegalStateException("ledger unavailable")));

        StepVerifier.create(useCase.recordBackfill(backfill))
                .expectError(IllegalStateException.class)
                .verify();
    }
}
