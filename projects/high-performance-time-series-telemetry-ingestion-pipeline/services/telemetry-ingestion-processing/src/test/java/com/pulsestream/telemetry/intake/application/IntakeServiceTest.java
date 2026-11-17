package com.pulsestream.telemetry.intake.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.shared.observability.AuditEntry;
import com.pulsestream.telemetry.shared.observability.AuditTrail;
import com.pulsestream.telemetry.shared.observability.StepLog;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class IntakeServiceTest {

    private AuditTrail auditTrail;
    private StepLog stepLog;
    private SimpleMeterRegistry meters;

    @BeforeEach
    void setUp() {
        auditTrail = mock(AuditTrail.class);
        when(auditTrail.record(any())).thenReturn(Mono.empty());
        stepLog = mock(StepLog.class);
        meters = new SimpleMeterRegistry();
    }

    private IntakeService service(int capacity) {
        var props = new TelemetryProperties(60, capacity, 30, 240, 0, 2500, 0, 220, 45);
        return new IntakeService(props, auditTrail, stepLog, meters);
    }

    private static TelemetrySample sample(String corr) {
        return new TelemetrySample("dev-1", "heart_rate", Instant.parse("2025-01-01T10:00:00Z"),
                Instant.EPOCH, 80.0, "PENDING", corr);
    }

    @Test
    void receive_samples_returnsAcceptedCount() {
        StepVerifier.create(service(8).receive(List.of(sample("c1"), sample("c1"))))
                .expectNext(2).verifyComplete();
    }

    @Test
    void receive_emptyList_returnsZero() {
        StepVerifier.create(service(8).receive(List.of())).expectNext(0).verifyComplete();
    }

    @Test
    void receive_samples_stampsTIngressOnStreamedSamples() {
        IntakeService service = service(8);
        Instant before = Instant.now();
        var received = service.stream().take(1).collectList();

        var verifier = StepVerifier.create(received).expectSubscription();
        service.receive(List.of(sample("c1"))).block();
        verifier.assertNext(list -> assertThat(list.get(0).tIngress()).isAfterOrEqualTo(before)
                .isNotEqualTo(Instant.EPOCH)).verifyComplete();
    }

    @Test
    void stream_afterReceive_emitsOfferedSamples() {
        IntakeService service = service(8);
        var verifier = StepVerifier.create(service.stream().take(2).map(TelemetrySample::deviceId))
                .expectSubscription();
        service.receive(List.of(sample("c1"), sample("c1"))).block();
        verifier.expectNext("dev-1", "dev-1").verifyComplete();
    }

    @Test
    void receive_allAccepted_countsPacketOutcomeAccepted() {
        service(8).receive(List.of(sample("c1"))).block();

        assertThat(meters.get("telemetry.intake.packets").tag("outcome", "accepted").counter().count())
                .isEqualTo(1.0);
    }

    @Test
    void receive_capacityExhausted_countsOverflowAndDroppedAtIntake() {
        IntakeService service = service(1);
        service.stream().subscribe(s -> { }, e -> { }).dispose();
        Integer accepted = service.receive(List.of(sample("c1"), sample("c1"), sample("c1"))).block();

        assertThat(accepted).isLessThan(3);
        assertThat(meters.get("telemetry.intake.packets").tag("outcome", "overflow").counter().count())
                .isEqualTo(1.0);
        assertThat(meters.get("telemetry.pipeline.dropped").tag("stage", "intake").counter().count())
                .isGreaterThanOrEqualTo(1.0);
    }

    @Test
    void receive_samples_recordsAuditEntryWithFirstCorrelationId() {
        service(8).receive(List.of(sample("first"), sample("second"))).block();

        ArgumentCaptor<AuditEntry> captor = ArgumentCaptor.forClass(AuditEntry.class);
        verify(auditTrail).record(captor.capture());
        AuditEntry entry = captor.getValue();
        assertThat(entry.actor()).isEqualTo("device");
        assertThat(entry.action()).isEqualTo("ingest");
        assertThat(entry.outcome()).isEqualTo("accepted");
        assertThat(entry.timestamp()).isNotNull();
        assertThat(entry.correlationId()).isEqualTo("first");
    }

    @Test
    void receive_packet_emitsPacketReceivedStepOnce() {
        service(8).receive(List.of(sample("c9"), sample("c9"))).block();

        verify(stepLog).emit("intake.packet.received", "c9");
    }
}
