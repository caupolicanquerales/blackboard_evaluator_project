package com.blackboard.telemetry.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.blackboard.telemetry.ingestion.domain.IngressPacket;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.SensorMetricBoundary;
import com.blackboard.telemetry.ingestion.domain.SourceKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidatedSampleEvent;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import com.blackboard.telemetry.shared.audit.AuditEntry;
import com.blackboard.telemetry.shared.audit.AuditTrail;
import com.blackboard.telemetry.shared.config.TelemetryProperties;
import com.blackboard.telemetry.shared.observability.CorrelationContext;
import com.blackboard.telemetry.shared.observability.TelemetryMeters;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class IngestPacketServiceTest {

    private static final Instant NOW = Instant.parse("2026-01-01T00:00:00Z");
    private static final String REQUEST_ID = "req-1";

    private ValidatedSampleStream stream;
    private AuditTrail auditTrail;
    private SimpleMeterRegistry registry;
    private ListAppender<ILoggingEvent> logs;
    private Logger logger;

    @BeforeEach
    void setUp() {
        stream = mock(ValidatedSampleStream.class);
        auditTrail = mock(AuditTrail.class);
        registry = new SimpleMeterRegistry();
        when(auditTrail.record(any())).thenReturn(Mono.empty());
        when(stream.publish(any())).thenReturn(Mono.empty());
        logger = (Logger) LoggerFactory.getLogger(IngestPacketService.class);
        logs = new ListAppender<>();
        logs.start();
        logger.addAppender(logs);
    }

    @AfterEach
    void tearDown() {
        logger.detachAppender(logs);
    }

    private IngestPacketService service(SensorMetricBoundary... boundaries) {
        TelemetryProperties properties = new TelemetryProperties(Duration.ofSeconds(1), 10, 10, 10,
                Duration.ofSeconds(1), List.of(boundaries));
        return new IngestPacketService(properties, stream, auditTrail, new TelemetryMeters(registry),
                Clock.fixed(NOW, ZoneOffset.UTC));
    }

    private static SensorMetricBoundary heartRate(boolean enabled) {
        return new SensorMetricBoundary(MetricKind.HEART_RATE, 30.0, 220.0, false, enabled);
    }

    private static SensorMetricBoundary swimPace() {
        return new SensorMetricBoundary(MetricKind.SWIM_PACE, 10.0, 200.0, true, true);
    }

    private static TelemetrySample sample(MetricKind metric, double value) {
        return new TelemetrySample("dev-1", metric, NOW, NOW, value, ValidationStatus.UNVALIDATED);
    }

    private static IngressPacket packet(TelemetrySample... samples) {
        return new IngressPacket("dev-1", SourceKind.values()[0], List.of(samples));
    }

    private Mono<Void> ingest(IngestPacketService service, IngressPacket packet) {
        return service.ingest(packet)
                .contextWrite(ctx -> ctx.put(CorrelationContext.contextKey(), REQUEST_ID));
    }

    private List<ValidatedSampleEvent> published() {
        ArgumentCaptor<ValidatedSampleEvent> captor = ArgumentCaptor.forClass(ValidatedSampleEvent.class);
        verify(stream, org.mockito.Mockito.atLeast(0)).publish(captor.capture());
        return new ArrayList<>(captor.getAllValues());
    }

    private List<AuditEntry> audited() {
        ArgumentCaptor<AuditEntry> captor = ArgumentCaptor.forClass(AuditEntry.class);
        verify(auditTrail, org.mockito.Mockito.atLeast(0)).record(captor.capture());
        return captor.getAllValues();
    }

    private List<String> logMessages() {
        return logs.list.stream().map(ILoggingEvent::getMessage).toList();
    }

    @Test
    void ingest_inBoundarySample_publishesValid() {
        StepVerifier.create(ingest(service(heartRate(true)), packet(sample(MetricKind.HEART_RATE, 150.0))))
                .verifyComplete();

        assertThat(published()).hasSize(1);
        assertThat(published().get(0).sample().status()).isEqualTo(ValidationStatus.VALID);
        assertThat(published().get(0).correlationId()).isEqualTo(REQUEST_ID);
    }

    @Test
    void ingest_outOfBoundarySample_publishesValidationFailedAndDoesNotDrop() {
        StepVerifier.create(ingest(service(heartRate(true)), packet(sample(MetricKind.HEART_RATE, 300.0))))
                .verifyComplete();

        assertThat(published()).hasSize(1);
        assertThat(published().get(0).sample().status()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
        assertThat(published().get(0).sample().value()).isEqualTo(300.0);
    }

    @Test
    void ingest_swimPaceBelowExclusiveMinimum_publishesValidationFailed() {
        StepVerifier.create(ingest(service(swimPace()), packet(sample(MetricKind.SWIM_PACE, 5.0))))
                .verifyComplete();

        assertThat(published().get(0).sample().status()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void ingest_metricWithoutBoundary_publishesValid() {
        StepVerifier.create(ingest(service(), packet(sample(MetricKind.POWER, 99999.0)))).verifyComplete();

        assertThat(published().get(0).sample().status()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void ingest_disabledBoundary_publishesValid() {
        StepVerifier.create(ingest(service(heartRate(false)), packet(sample(MetricKind.HEART_RATE, 999.0))))
                .verifyComplete();

        assertThat(published().get(0).sample().status()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void ingest_multipleSamples_publishesInPacketOrder() {
        IngressPacket packet = packet(sample(MetricKind.HEART_RATE, 150.0), sample(MetricKind.HEART_RATE, 300.0));

        StepVerifier.create(ingest(service(heartRate(true)), packet)).verifyComplete();

        assertThat(published()).extracting(e -> e.sample().status())
                .containsExactly(ValidationStatus.VALID, ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void ingest_validAndInvalidSamples_auditsEachSampleThenPacketSuccess() {
        IngressPacket packet = packet(sample(MetricKind.HEART_RATE, 150.0), sample(MetricKind.HEART_RATE, 300.0));

        StepVerifier.create(ingest(service(heartRate(true)), packet)).verifyComplete();

        List<AuditEntry> entries = audited();
        assertThat(entries).extracting(e -> e.action().toString())
                .containsExactly("VALIDATE_SAMPLE", "VALIDATE_SAMPLE", "INGEST_PACKET");
        assertThat(entries).extracting(e -> e.outcome().toString()).containsOnly("SUCCESS");
        assertThat(entries).extracting(AuditEntry::actor).containsOnly("dev-1");
        assertThat(entries).extracting(AuditEntry::timestamp).containsOnly(NOW);
        assertThat(entries).extracting(AuditEntry::correlationId).containsOnly(REQUEST_ID);
    }

    @Test
    void ingest_publishOverflow_propagatesErrorAndAuditsFailure() {
        when(stream.publish(any())).thenReturn(Mono.error(new IllegalStateException("overflow")));

        StepVerifier.create(ingest(service(heartRate(true)), packet(sample(MetricKind.HEART_RATE, 150.0))))
                .expectError(IllegalStateException.class).verify();

        AuditEntry last = audited().get(audited().size() - 1);
        assertThat(last.action().toString()).isEqualTo("INGEST_PACKET");
        assertThat(last.outcome().toString()).isEqualTo("FAILURE");
        assertThat(last.actor()).isEqualTo("dev-1");
    }

    @Test
    void ingest_publishOverflow_stopsAfterFirstFailedSample() {
        when(stream.publish(any())).thenReturn(Mono.error(new IllegalStateException("overflow")));
        IngressPacket packet = packet(sample(MetricKind.HEART_RATE, 150.0), sample(MetricKind.HEART_RATE, 160.0));

        StepVerifier.create(ingest(service(heartRate(true)), packet)).expectError().verify();

        verify(stream, org.mockito.Mockito.times(1)).publish(any());
    }

    @Test
    void ingest_noCorrelationKey_usesUncorrelated() {
        StepVerifier.create(service().ingest(packet(sample(MetricKind.POWER, 1.0)))).verifyComplete();

        assertThat(published().get(0).correlationId()).isEqualTo("UNCORRELATED");
    }

    @Test
    void ingest_samples_recordsMetersAndLatency() {
        IngressPacket packet = packet(sample(MetricKind.HEART_RATE, 150.0), sample(MetricKind.HEART_RATE, 300.0));

        StepVerifier.create(ingest(service(heartRate(true)), packet)).verifyComplete();

        assertThat(registry.get("telemetry.packets.received").counter().count()).isEqualTo(1.0);
        assertThat(registry.get("telemetry.samples.validated").tag("status", "VALID").counter().count())
                .isEqualTo(1.0);
        assertThat(registry.get("telemetry.samples.validated").tag("status", "VALIDATION_FAILED").counter()
                .count()).isEqualTo(1.0);
        assertThat(registry.get("telemetry.pipeline.latency").tag("stage", "validate").timer().count())
                .isPositive();
    }

    @Test
    void ingest_validAndInvalidSamples_emitsStepLogs() {
        IngressPacket packet = packet(sample(MetricKind.HEART_RATE, 150.0), sample(MetricKind.HEART_RATE, 300.0));

        StepVerifier.create(ingest(service(heartRate(true)), packet)).verifyComplete();

        assertThat(logMessages()).anyMatch(m -> m.contains("packet received"))
                .anyMatch(m -> m.contains("sample validated"))
                .anyMatch(m -> m.contains("sample tagged VALIDATION_FAILED"));
    }

    @Test
    void ingest_inBoundarySample_neverLogsTaggedFailure() {
        StepVerifier.create(ingest(service(heartRate(true)), packet(sample(MetricKind.HEART_RATE, 150.0))))
                .verifyComplete();

        assertThat(logMessages()).noneMatch(m -> m.contains("VALIDATION_FAILED"));
        verify(auditTrail, never()).record(org.mockito.ArgumentMatchers.argThat(
                e -> e != null && "FAILURE".equals(e.outcome().toString())));
    }
}
