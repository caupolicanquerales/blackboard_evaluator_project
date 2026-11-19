package com.pulsestream.telemetry.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ingestion.domain.SensorMetricBoundary;
import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;
import com.pulsestream.telemetry.ingestion.domain.TelemetryRevision;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class IngestPacketUseCaseTest {

    private static final Instant NOW = Instant.parse("2025-01-01T12:00:00Z");
    private static final Instant T_DEVICE = Instant.parse("2025-01-01T11:59:00Z");

    @Mock TelemetryRecordRepository repository;
    @Mock EventPublisher publisher;
    @Mock AuditTrail auditTrail;
    @Mock SensorMetricBoundary boundary;
    @Mock BackfillReorderer reorderer;
    @Mock RedactionPort redaction;

    private SimpleMeterRegistry registry;
    private IngestPacketUseCase useCase;

    @BeforeEach
    void setUp() {
        registry = new SimpleMeterRegistry();
        useCase = new IngestPacketUseCase(repository, publisher, auditTrail, boundary, reorderer, redaction,
                new TelemetryMetrics(registry), Clock.fixed(NOW, ZoneOffset.UTC), Duration.ofMinutes(5), "pub-1");
        lenient().when(reorderer.reorder(any())).thenAnswer(i -> i.getArgument(0));
        lenient().when(redaction.mask(any())).thenReturn("***");
        lenient().when(auditTrail.record(any())).thenReturn(Mono.empty());
        lenient().when(boundary.check(any(), org.mockito.ArgumentMatchers.anyDouble()))
                .thenReturn(ValidationStatus.values()[0]);
        lenient().when(repository.appendRecord(any())).thenReturn(Mono.just(true));
        lenient().when(repository.appendRevision(any())).thenReturn(Mono.empty());
        lenient().when(repository.findLatestRevision(any(), any(), any())).thenReturn(Mono.empty());
        lenient().when(publisher.publish(any())).thenReturn(Mono.just(true));
    }

    private static TelemetrySample sample(String device, String metric, Instant t, double value) {
        return new TelemetrySample(device, metric, t, Instant.EPOCH, value, ValidationStatus.values()[0], "{}");
    }

    private IngestSummary ingest(String owner, TelemetrySample... samples) {
        return useCase.ingest(owner, Flux.just(samples)).block(Duration.ofSeconds(5));
    }

    @Test
    void ingest_ownerMatches_storesSample() {
        StepVerifier.create(useCase.ingest("dev-1", Flux.just(sample("dev-1", "heart_rate", T_DEVICE, 60))))
                .assertNext(s -> {
                    assertThat(s.appended()).isEqualTo(1);
                    assertThat(s.refused()).isFalse();
                })
                .verifyComplete();
    }

    @Test
    void ingest_crossOwner_refusedAndNothingStored() {
        IngestSummary summary = ingest("dev-2", sample("dev-1", "heart_rate", T_DEVICE, 60));

        assertThat(summary.refused()).isTrue();
        verify(repository, never()).appendRecord(any());
    }

    @Test
    void ingest_swimPaceOutOfBounds_storedAsValidationFailed() {
        when(boundary.check("swim_pace", 45.0)).thenReturn(ValidationStatus.VALIDATION_FAILED);

        IngestSummary summary = ingest("dev-1", sample("dev-1", "swim_pace", T_DEVICE, 45));

        ArgumentCaptor<TelemetrySample> captor = ArgumentCaptor.forClass(TelemetrySample.class);
        verify(repository).appendRecord(captor.capture());
        assertThat(captor.getValue().status()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
        assertThat(summary.rejectedValidation()).isEqualTo(1);
        assertThat(registry.get("telemetry.samples.validation_failed").counter().count()).isEqualTo(1.0);
    }

    @Test
    void ingest_samePacketResent_countsDuplicateWithoutRevision() {
        when(repository.appendRecord(any())).thenReturn(Mono.just(false));
        when(repository.findLatestRevision("dev-1", "heart_rate", T_DEVICE))
                .thenReturn(Mono.just(new TelemetryRevision("dev-1", "heart_rate", T_DEVICE, 1, 60.0, "ORIGINAL")));

        IngestSummary summary = ingest("dev-1", sample("dev-1", "heart_rate", T_DEVICE, 60));

        assertThat(summary.duplicates()).isEqualTo(1);
        assertThat(summary.revisions()).isZero();
        verify(repository, never()).appendRevision(any());
    }

    @Test
    void ingest_sameIdentityNewValue_appendsRevisionTwoCorrection() {
        when(repository.appendRecord(any())).thenReturn(Mono.just(false));
        when(repository.findLatestRevision("dev-1", "heart_rate", T_DEVICE))
                .thenReturn(Mono.just(new TelemetryRevision("dev-1", "heart_rate", T_DEVICE, 1, 60.0, "ORIGINAL")));

        IngestSummary summary = ingest("dev-1", sample("dev-1", "heart_rate", T_DEVICE, 61));

        ArgumentCaptor<TelemetryRevision> captor = ArgumentCaptor.forClass(TelemetryRevision.class);
        verify(repository).appendRevision(captor.capture());
        assertThat(captor.getValue().revisionNumber()).isEqualTo(2);
        assertThat(captor.getValue().reason()).isEqualTo("CORRECTION");
        assertThat(summary.revisions()).isEqualTo(1);
        assertThat(registry.get("telemetry.revisions.appended").counter().count()).isEqualTo(1.0);
    }

    @Test
    void ingest_beyondLateWindow_storedAsLate() {
        Instant old = NOW.minus(Duration.ofHours(1));

        ingest("dev-1", sample("dev-1", "heart_rate", old, 60));

        ArgumentCaptor<TelemetrySample> captor = ArgumentCaptor.forClass(TelemetrySample.class);
        verify(repository).appendRecord(captor.capture());
        assertThat(captor.getValue().status()).isEqualTo(ValidationStatus.LATE);
    }

    @Test
    void ingest_publishAccepted_publishesEventAndNoDrop() {
        ingest("dev-1", sample("dev-1", "heart_rate", T_DEVICE, 60));

        ArgumentCaptor<TelemetryEvent> captor = ArgumentCaptor.forClass(TelemetryEvent.class);
        verify(publisher).publish(captor.capture());
        assertThat(captor.getValue().deviceId()).isEqualTo("dev-1");
        assertThat(registry.find("telemetry.broadcast.dropped").counter()).isNull();
    }

    @Test
    void ingest_publishOverflow_countsBroadcastDropped() {
        when(publisher.publish(any())).thenReturn(Mono.just(false));

        ingest("dev-1", sample("dev-1", "heart_rate", T_DEVICE, 60));

        assertThat(registry.get("telemetry.broadcast.dropped").counter().count()).isEqualTo(1.0);
    }

    @Test
    void ingest_appendRecordFalse_doesNotCountAppended() {
        when(repository.appendRecord(any())).thenReturn(Mono.just(false));
        when(repository.findLatestRevision(any(), any(), any())).thenReturn(Mono.empty());

        IngestSummary summary = ingest("dev-1", sample("dev-1", "heart_rate", T_DEVICE, 60));

        assertThat(summary.appended()).isZero();
    }

    @Test
    void ingest_processedPacket_recordsAuditEntryAndDurationMeter() {
        ingest("dev-1", sample("dev-1", "heart_rate", T_DEVICE, 60));

        verify(auditTrail, org.mockito.Mockito.atLeastOnce()).record(any());
        assertThat(registry.get("telemetry.ingest.duration").timer().count()).isEqualTo(1L);
        assertThat(registry.get("telemetry.samples.ingested").counter().count()).isEqualTo(1.0);
    }
}
