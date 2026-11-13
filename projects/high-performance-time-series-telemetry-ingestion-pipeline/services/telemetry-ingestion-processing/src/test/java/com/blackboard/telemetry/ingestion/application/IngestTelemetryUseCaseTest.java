package com.blackboard.telemetry.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.blackboard.telemetry.eventstore.application.TelemetryEventStore;
import com.blackboard.telemetry.eventstore.domain.TelemetryRecord;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.shared.observability.AuditEntry;
import com.blackboard.telemetry.shared.observability.AuditTrail;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Instant;
import java.util.List;
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
class IngestTelemetryUseCaseTest {

    private static final Instant T = Instant.parse("2024-01-01T00:00:00Z");

    @Mock
    private TelemetryEventStore store;

    @Mock
    private AuditTrail auditTrail;

    private SimpleMeterRegistry registry;
    private IngestTelemetryUseCase useCase;

    @BeforeEach
    void setUp() {
        registry = new SimpleMeterRegistry();
        useCase = new IngestTelemetryUseCase(store, auditTrail, registry);
    }

    private void stubPorts() {
        when(store.append(any())).thenAnswer(i -> Mono.just(i.getArgument(0)));
        when(auditTrail.record(any())).thenReturn(Mono.empty());
    }

    private List<TelemetryRecord> appended(int times) {
        ArgumentCaptor<TelemetryRecord> captor = ArgumentCaptor.forClass(TelemetryRecord.class);
        verify(store, times(times)).append(captor.capture());
        return captor.getAllValues();
    }

    private AuditEntry audited() {
        ArgumentCaptor<AuditEntry> captor = ArgumentCaptor.forClass(AuditEntry.class);
        verify(auditTrail, times(1)).record(captor.capture());
        return captor.getValue();
    }

    @Test
    void ingest_validSamples_appendsRevisionOneValidatedAndEmitsCount() {
        stubPorts();
        Flux<TelemetrySample> samples = Flux.just(
                new TelemetrySample("dev-1", "temp", T, T, 1.5),
                new TelemetrySample("dev-1", "hum", T, T, 2.5));

        StepVerifier.create(useCase.ingest(samples, "corr-1")).expectNext(2L).verifyComplete();

        assertThat(appended(2)).extracting(TelemetryRecord::revision, TelemetryRecord::status)
                .containsExactly(org.assertj.core.groups.Tuple.tuple(1L, "VALIDATED"),
                        org.assertj.core.groups.Tuple.tuple(1L, "VALIDATED"));
    }

    @Test
    void ingest_blankDeviceId_appendsValidationFailed() {
        stubPorts();

        StepVerifier.create(useCase.ingest(Flux.just(new TelemetrySample(" ", "temp", T, T, 1.0)), "c"))
                .expectNext(1L).verifyComplete();

        assertThat(appended(1).get(0).status()).isEqualTo("VALIDATION_FAILED");
    }

    @Test
    void ingest_blankMetric_appendsValidationFailed() {
        stubPorts();

        StepVerifier.create(useCase.ingest(Flux.just(new TelemetrySample("dev-1", "", T, T, 1.0)), "c"))
                .expectNext(1L).verifyComplete();

        assertThat(appended(1).get(0).status()).isEqualTo("VALIDATION_FAILED");
    }

    @Test
    void ingest_nullTDevice_appendsValidationFailed() {
        stubPorts();

        StepVerifier.create(useCase.ingest(Flux.just(new TelemetrySample("dev-1", "temp", null, T, 1.0)), "c"))
                .expectNext(1L).verifyComplete();

        assertThat(appended(1).get(0).status()).isEqualTo("VALIDATION_FAILED");
    }

    @Test
    void ingest_nonFiniteValue_appendsValidationFailed() {
        stubPorts();

        StepVerifier.create(useCase.ingest(
                Flux.just(new TelemetrySample("dev-1", "temp", T, T, Double.POSITIVE_INFINITY)), "c"))
                .expectNext(1L).verifyComplete();

        assertThat(appended(1).get(0).status()).isEqualTo("VALIDATION_FAILED");
    }

    @Test
    void ingest_samples_recordsMetricsWithTags() {
        stubPorts();
        Flux<TelemetrySample> samples = Flux.just(
                new TelemetrySample("dev-1", "temp", T, T, 1.0),
                new TelemetrySample("dev-1", "temp", T, T, Double.NaN));

        useCase.ingest(samples, "c").block();

        assertThat(registry.get("telemetry.ingress.packets").tag("outcome", "accepted").counter().count())
                .isEqualTo(1.0);
        assertThat(registry.get("telemetry.samples.validated").tag("metric", "temp")
                .tag("status", "VALIDATED").counter().count()).isEqualTo(1.0);
        assertThat(registry.get("telemetry.samples.validated").tag("metric", "temp")
                .tag("status", "VALIDATION_FAILED").counter().count()).isEqualTo(1.0);
        assertThat(registry.get("telemetry.ingest.latency").timer().count()).isEqualTo(1L);
    }

    @Test
    void ingest_samples_recordsOneAuditEntryWithFirstDeviceAsActor() {
        stubPorts();
        Flux<TelemetrySample> samples = Flux.just(
                new TelemetrySample("dev-9", "temp", T, T, 1.0),
                new TelemetrySample("dev-2", "temp", T, T, 1.0));

        useCase.ingest(samples, "corr-7").block();

        AuditEntry entry = audited();
        assertThat(entry.actor()).isEqualTo("dev-9");
        assertThat(entry.action()).isEqualTo("INGEST");
        assertThat(entry.outcome()).isEqualTo("ACCEPTED");
        assertThat(entry.timestamp()).isNotNull();
        assertThat(entry.correlationId()).isEqualTo("corr-7");
    }

    @Test
    void ingest_emptySamples_emitsZeroAndAuditsSystemActor() {
        when(auditTrail.record(any())).thenReturn(Mono.empty());

        StepVerifier.create(useCase.ingest(Flux.empty(), "corr-0")).expectNext(0L).verifyComplete();

        verify(store, never()).append(any());
        assertThat(audited().actor()).isEqualTo("system");
    }
}
