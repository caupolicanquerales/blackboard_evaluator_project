package com.pulsestream.telemetry.ledger.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import com.pulsestream.telemetry.shared.events.TelemetryRevisionAppendedEvent;
import com.pulsestream.telemetry.ledger.application.port.out.TelemetryLedgerRepository;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetryBackfillDetectedEvent;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.intake.domain.ValidationStatus;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class RecordTelemetryServiceTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:05Z");

    @Mock
    private TelemetryLedgerRepository repository;

    @Mock
    private BoundedEventChannel<TelemetryRevisionAppendedEvent> revisionsAppended;

    private RecordTelemetryService service;

    @BeforeEach
    void setUp() {
        service = new RecordTelemetryService(repository, revisionsAppended);
    }

    private static TelemetrySample sample(double value) {
        return new TelemetrySample("dev-1", "temp", value, T_DEVICE, T_INGRESS, ValidationStatus.VALID);
    }

    private static TelemetryRecord existing(double value) {
        return TelemetryRecord.original("dev-1", "temp", value, T_DEVICE, T_INGRESS, "VALID");
    }

    private void stubLatest(TelemetryRecord latest) {
        when(repository.findLatestRevision("dev-1", "temp", T_DEVICE)).thenReturn(Mono.justOrEmpty(latest));
    }

    private void stubAppendEchoes() {
        when(repository.append(any(TelemetryRecord.class))).thenAnswer(i -> Mono.just(i.getArgument(0)));
    }

    private TelemetryRecord captureAppended() {
        ArgumentCaptor<TelemetryRecord> captor = ArgumentCaptor.forClass(TelemetryRecord.class);
        verify(repository).append(captor.capture());
        return captor.getValue();
    }

    @Test
    void recordSequenced_noExistingRecord_appendsOriginalRevisionZeroWithoutPublishing() {
        stubLatest(null);
        stubAppendEchoes();

        StepVerifier.create(service.recordSequenced(sample(21.5)))
                .assertNext(r -> {
                    assertThat(r.revision()).isZero();
                    assertThat(r.value()).isEqualTo(21.5);
                    assertThat(r.deviceId()).isEqualTo("dev-1");
                })
                .verifyComplete();

        assertThat(captureAppended().revision()).isZero();
        verify(revisionsAppended, never()).offer(any());
    }

    @Test
    void recordSequenced_identicalValueAndStatus_returnsLatestWithoutAppending() {
        TelemetryRecord latest = existing(21.5);
        stubLatest(latest);

        StepVerifier.create(service.recordSequenced(sample(21.5)))
                .expectNext(latest)
                .verifyComplete();

        verify(repository, never()).append(any());
        verify(revisionsAppended, never()).offer(any());
    }

    @Test
    void recordSequenced_differentValue_appendsRevisionSupersedingLatest() {
        TelemetryRecord latest = existing(21.5);
        stubLatest(latest);
        stubAppendEchoes();

        StepVerifier.create(service.recordSequenced(sample(30.0)))
                .assertNext(r -> {
                    assertThat(r.revision()).isEqualTo(1);
                    assertThat(r.value()).isEqualTo(30.0);
                    assertThat(r.supersedesId()).isEqualTo(latest.id());
                })
                .verifyComplete();

        assertThat(captureAppended().revision()).isEqualTo(1);
    }

    @Test
    void recordSequenced_differentStatus_appendsRevision() {
        TelemetryRecord latest = existing(21.5);
        stubLatest(latest);
        stubAppendEchoes();
        TelemetrySample failed = new TelemetrySample(
                "dev-1", "temp", 21.5, T_DEVICE, T_INGRESS, ValidationStatus.VALIDATION_FAILED);

        StepVerifier.create(service.recordSequenced(failed))
                .assertNext(r -> assertThat(r.revision()).isEqualTo(1))
                .verifyComplete();
    }

    @Test
    void recordSequenced_revisionAppended_publishesEventForAppendedRecord() {
        stubLatest(existing(21.5));
        stubAppendEchoes();

        TelemetryRecord appended = service.recordSequenced(sample(30.0)).block();

        ArgumentCaptor<TelemetryRevisionAppendedEvent> captor =
                ArgumentCaptor.forClass(TelemetryRevisionAppendedEvent.class);
        verify(revisionsAppended).offer(captor.capture());
        assertThat(captor.getValue())
                .isEqualTo(new TelemetryRevisionAppendedEvent(
                        appended.id(), "dev-1", "temp", T_DEVICE, appended.revision()));
    }

    @Test
    void recordBackfill_noExistingRecord_appendsOriginalRevisionZero() {
        stubLatest(null);
        stubAppendEchoes();

        StepVerifier.create(service.recordBackfill(new TelemetryBackfillDetectedEvent(sample(21.5), false)))
                .assertNext(r -> assertThat(r.revision()).isZero())
                .verifyComplete();

        verify(revisionsAppended, never()).offer(any());
    }

    @Test
    void recordBackfill_identicalSample_returnsLatestUnchanged() {
        TelemetryRecord latest = existing(21.5);
        stubLatest(latest);

        StepVerifier.create(service.recordBackfill(new TelemetryBackfillDetectedEvent(sample(21.5), true)))
                .expectNext(latest)
                .verifyComplete();

        verify(repository, never()).append(any());
    }

    @Test
    void recordBackfill_differentValue_appendsRevisionAndPublishes() {
        TelemetryRecord latest = existing(21.5);
        stubLatest(latest);
        stubAppendEchoes();

        StepVerifier.create(service.recordBackfill(new TelemetryBackfillDetectedEvent(sample(99.0), true)))
                .assertNext(r -> {
                    assertThat(r.revision()).isEqualTo(1);
                    assertThat(r.supersedesId()).isEqualTo(latest.id());
                })
                .verifyComplete();

        verify(revisionsAppended).offer(any(TelemetryRevisionAppendedEvent.class));
        assertThat(latest.value()).isEqualTo(21.5);
    }

    @Test
    void recordSequenced_anyOutcome_usesOnlyFindLatestAndAppendOnRepository() {
        stubLatest(existing(21.5));
        stubAppendEchoes();

        service.recordSequenced(sample(30.0)).block();

        verify(repository).findLatestRevision("dev-1", "temp", T_DEVICE);
        verify(repository).append(any(TelemetryRecord.class));
        verifyNoMoreInteractions(repository);
    }
}
