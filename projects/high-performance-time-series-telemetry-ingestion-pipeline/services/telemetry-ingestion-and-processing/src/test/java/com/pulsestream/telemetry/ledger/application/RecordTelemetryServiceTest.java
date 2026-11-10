package com.pulsestream.telemetry.ledger.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.ledger.domain.EventRevision;
import com.pulsestream.telemetry.ledger.domain.EventRevision.RevisionReason;
import com.pulsestream.telemetry.shared.event.TelemetryEvent;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class RecordTelemetryServiceTest {

    private static final Instant NOW = Instant.parse("2024-01-01T12:00:00Z");
    private static final Instant DEVICE_TS = Instant.parse("2024-01-01T11:59:00Z");
    private static final Instant INGRESS_TS = Instant.parse("2024-01-01T11:59:30Z");

    @Mock
    private TelemetryLedgerRepository repository;

    private RecordTelemetryService service;

    @BeforeEach
    void setUp() {
        service = new RecordTelemetryService(repository, Clock.fixed(NOW, ZoneOffset.UTC));
    }

    private static TelemetrySample sample(double value, TelemetrySample.ValidationStatus status) {
        UUID id = TelemetrySample.recordIdFor("dev-1", TelemetrySample.MetricType.HEART_RATE, DEVICE_TS);
        return new TelemetrySample(id, "dev-1", TelemetrySample.MetricType.HEART_RATE, value,
                DEVICE_TS, INGRESS_TS, status);
    }

    private static TelemetryEvent validated(TelemetrySample s) {
        return new TelemetryEvent.TelemetrySampleValidated(s, NOW);
    }

    private void stubAppendEchoes() {
        when(repository.append(any(EventRevision.class)))
                .thenAnswer(inv -> Mono.just(inv.getArgument(0, EventRevision.class)));
    }

    @Test
    void record_validatedWithNoRevision_appendsOriginalRevisionOne() {
        TelemetrySample s = sample(120, TelemetrySample.ValidationStatus.VALID);
        when(repository.findLatest(s.recordId())).thenReturn(Mono.empty());
        stubAppendEchoes();

        StepVerifier.create(service.record(validated(s)))
                .assertNext(r -> {
                    assertThat(r.revisionNumber()).isEqualTo(1);
                    assertThat(r.reason()).isEqualTo(RevisionReason.ORIGINAL);
                    assertThat(r.recordId()).isEqualTo(s.recordId());
                    assertThat(r.recordedAt()).isEqualTo(NOW);
                })
                .verifyComplete();
    }

    @Test
    void record_validationFailedWithNoRevision_appendsOriginalRetainingPayload() {
        TelemetrySample s = sample(999, TelemetrySample.ValidationStatus.VALIDATION_FAILED);
        when(repository.findLatest(s.recordId())).thenReturn(Mono.empty());
        stubAppendEchoes();

        StepVerifier.create(service.record(new TelemetryEvent.TelemetrySampleValidationFailed(s, NOW)))
                .assertNext(r -> {
                    assertThat(r.revisionNumber()).isEqualTo(1);
                    assertThat(r.reason()).isEqualTo(RevisionReason.ORIGINAL);
                    assertThat(r.value()).isEqualTo(999);
                    assertThat(r.validationStatus()).isEqualTo(TelemetrySample.ValidationStatus.VALIDATION_FAILED);
                })
                .verifyComplete();
    }

    @Test
    void record_existingRevisionWithDifferentValue_appendsCorrection() {
        TelemetrySample old = sample(120, TelemetrySample.ValidationStatus.VALID);
        EventRevision latest = EventRevision.original(old, NOW.minusSeconds(60));
        when(repository.findLatest(old.recordId())).thenReturn(Mono.just(latest));
        stubAppendEchoes();

        StepVerifier.create(service.record(validated(sample(125, TelemetrySample.ValidationStatus.VALID))))
                .assertNext(r -> {
                    assertThat(r.revisionNumber()).isEqualTo(2);
                    assertThat(r.reason()).isEqualTo(RevisionReason.CORRECTION);
                    assertThat(r.value()).isEqualTo(125);
                })
                .verifyComplete();
    }

    @Test
    void record_existingRevisionWithDifferentStatus_appendsCorrection() {
        TelemetrySample old = sample(120, TelemetrySample.ValidationStatus.VALIDATION_FAILED);
        EventRevision latest = EventRevision.original(old, NOW.minusSeconds(60));
        when(repository.findLatest(old.recordId())).thenReturn(Mono.just(latest));
        stubAppendEchoes();

        StepVerifier.create(service.record(validated(sample(120, TelemetrySample.ValidationStatus.VALID))))
                .assertNext(r -> {
                    assertThat(r.reason()).isEqualTo(RevisionReason.CORRECTION);
                    assertThat(r.validationStatus()).isEqualTo(TelemetrySample.ValidationStatus.VALID);
                })
                .verifyComplete();
    }

    @Test
    void record_identicalReplay_returnsLatestWithoutAppending() {
        TelemetrySample s = sample(120, TelemetrySample.ValidationStatus.VALID);
        EventRevision latest = EventRevision.original(s, NOW.minusSeconds(60));
        when(repository.findLatest(s.recordId())).thenReturn(Mono.just(latest));

        StepVerifier.create(service.record(validated(s)))
                .expectNext(latest)
                .verifyComplete();

        verify(repository, never()).append(any());
    }

    @Test
    void record_backfillWithExistingRevision_appendsBackfillAsNext() {
        TelemetrySample old = sample(120, TelemetrySample.ValidationStatus.VALID);
        EventRevision latest = EventRevision.original(old, NOW.minusSeconds(60));
        when(repository.findLatest(old.recordId())).thenReturn(Mono.just(latest));
        stubAppendEchoes();

        StepVerifier.create(service.record(new TelemetryEvent.TelemetryBackfillReordered(old, NOW)))
                .assertNext(r -> {
                    assertThat(r.revisionNumber()).isEqualTo(2);
                    assertThat(r.reason()).isEqualTo(RevisionReason.BACKFILL);
                })
                .verifyComplete();
    }

    @Test
    void record_backfillWithNoRevision_appendsOriginal() {
        TelemetrySample s = sample(120, TelemetrySample.ValidationStatus.VALID);
        when(repository.findLatest(s.recordId())).thenReturn(Mono.empty());
        stubAppendEchoes();

        StepVerifier.create(service.record(new TelemetryEvent.TelemetryBackfillReordered(s, NOW)))
                .assertNext(r -> {
                    assertThat(r.revisionNumber()).isEqualTo(1);
                    assertThat(r.reason()).isEqualTo(RevisionReason.ORIGINAL);
                })
                .verifyComplete();
    }

    @Test
    void record_windowBuffered_returnsEmptyWithoutAppending() {
        TelemetryEvent event = new TelemetryEvent.TelemetryWindowBuffered(
                List.of(sample(120, TelemetrySample.ValidationStatus.VALID)), DEVICE_TS, NOW, NOW);

        StepVerifier.create(service.record(event)).verifyComplete();

        verify(repository, never()).append(any());
    }

    @Test
    void record_revisionAppended_returnsEmptyWithoutAppending() {
        TelemetryEvent event = new TelemetryEvent.TelemetryRevisionAppended(UUID.fromString(
                "00000000-0000-0000-0000-000000000001"), 2, NOW);

        StepVerifier.create(service.record(event)).verifyComplete();

        verify(repository, never()).append(any());
    }
}
