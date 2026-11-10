package com.pulsestream.telemetry.ledger.application;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.ledger.domain.EventRevision;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class TelemetryHistoryQueryServiceTest {

    private static final UUID RECORD_ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final String DEVICE_ID = "device-1";
    private static final Instant FROM = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant TO = Instant.parse("2024-01-02T00:00:00Z");

    @Mock
    private TelemetryLedgerRepository repository;

    @InjectMocks
    private TelemetryHistoryQueryService service;

    private static TelemetrySample.MetricType metric() {
        return TelemetrySample.MetricType.values()[0];
    }

    @Test
    void history_validRange_delegatesToRepositoryHistory() {
        when(repository.findHistory(DEVICE_ID, metric(), FROM, TO)).thenReturn(Flux.empty());

        StepVerifier.create(service.history(DEVICE_ID, metric(), FROM, TO)).verifyComplete();

        verify(repository).findHistory(DEVICE_ID, metric(), FROM, TO);
    }

    @Test
    void history_equalBounds_isAccepted() {
        when(repository.findHistory(DEVICE_ID, metric(), FROM, FROM)).thenReturn(Flux.empty());

        StepVerifier.create(service.history(DEVICE_ID, metric(), FROM, FROM)).verifyComplete();

        verify(repository).findHistory(DEVICE_ID, metric(), FROM, FROM);
    }

    @Test
    void history_fromAfterTo_failsWithIllegalArgumentException() {
        StepVerifier.create(Flux.defer(() -> service.history(DEVICE_ID, metric(), TO, FROM)))
                .expectError(IllegalArgumentException.class)
                .verify();

        verify(repository, never()).findHistory(any(), any(), any(), any());
    }

    @Test
    void history_fromAfterTo_neverTouchesRepositoryOtherMethods() {
        StepVerifier.create(Flux.defer(() -> service.history(DEVICE_ID, metric(), TO, FROM)))
                .expectError(IllegalArgumentException.class)
                .verify();

        verifyNoInteractions(repository);
    }

    @Test
    void history_repositoryError_propagates() {
        when(repository.findHistory(DEVICE_ID, metric(), FROM, TO))
                .thenReturn(Flux.error(new IllegalStateException("boom")));

        StepVerifier.create(service.history(DEVICE_ID, metric(), FROM, TO))
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void revisions_recordId_delegatesToRepositoryRevisions() {
        when(repository.findRevisions(RECORD_ID)).thenReturn(Flux.empty());

        StepVerifier.create(service.revisions(RECORD_ID)).verifyComplete();

        verify(repository).findRevisions(RECORD_ID);
    }

    @Test
    void latest_recordId_delegatesToRepositoryLatest() {
        when(repository.findLatest(RECORD_ID)).thenReturn(Mono.empty());

        StepVerifier.create(service.latest(RECORD_ID)).verifyComplete();

        verify(repository).findLatest(RECORD_ID);
    }

    @Test
    void latest_repositoryError_propagates() {
        when(repository.findLatest(RECORD_ID)).thenReturn(Mono.<EventRevision>error(new IllegalStateException("boom")));

        StepVerifier.create(service.latest(RECORD_ID))
                .expectError(IllegalStateException.class)
                .verify();
    }
}
