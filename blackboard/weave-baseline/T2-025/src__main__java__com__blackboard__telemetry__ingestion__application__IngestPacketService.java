package com.blackboard.telemetry.ingestion.application;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Objects;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import com.blackboard.telemetry.ingestion.domain.IngressPacket;
import com.blackboard.telemetry.ingestion.domain.ValidatedSampleEvent;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import com.blackboard.telemetry.shared.config.TelemetryProperties;
import com.blackboard.telemetry.shared.observability.CorrelationContext;
import com.blackboard.telemetry.shared.observability.TelemetryMeters;
import com.blackboard.telemetry.shared.audit.AuditAction;
import com.blackboard.telemetry.shared.audit.AuditEntry;
import com.blackboard.telemetry.shared.audit.AuditTrail;

public class IngestPacketService {

    private static final Logger LOGGER = LoggerFactory.getLogger(IngestPacketService.class);

    private final TelemetryProperties properties;

    private final ValidatedSampleStream stream;

    private final AuditTrail auditTrail;

    private final TelemetryMeters meters;

    private final Clock clock;

    public IngestPacketService(TelemetryProperties properties, ValidatedSampleStream stream, AuditTrail auditTrail, TelemetryMeters meters, Clock clock) {
        this.properties = Objects.requireNonNull(properties, "properties");
        this.stream = Objects.requireNonNull(stream, "stream");
        this.auditTrail = Objects.requireNonNull(auditTrail, "auditTrail");
        this.meters = Objects.requireNonNull(meters, "meters");
        this.clock = Objects.requireNonNull(clock, "clock");
    }

    public Mono<Void> ingest(IngressPacket packet) {
        return CorrelationContext.current().flatMap(requestId -> {
            LOGGER.info("packet received deviceId={} requestId={}", packet.deviceId(), requestId);
            meters.packetReceived(packet.sourceKind());
            Instant start = clock.instant();
            return Flux.fromIterable(packet.samples()).concatMap(sample -> {
                boolean accepted = properties.boundaries().stream().noneMatch(boundary -> boundary.enabled() && boundary.metric() == sample.metric() && !boundary.accepts(sample.value()));
                ValidationStatus status = accepted ? ValidationStatus.VALID : ValidationStatus.VALIDATION_FAILED;
                meters.sampleValidated(sample.metric(), status);
                if (accepted) {
                    LOGGER.info("sample validated metric={} requestId={}", sample.metric(), requestId);
                } else {
                    LOGGER.warn("sample tagged VALIDATION_FAILED metric={} requestId={}", sample.metric(), requestId);
                }
                return stream.publish(new ValidatedSampleEvent(sample.withStatus(status), requestId)).then(Mono.defer(() -> auditTrail.record(new AuditEntry(packet.deviceId(), AuditAction.VALIDATE_SAMPLE, "SUCCESS", clock.instant(), requestId))));
            }).then(Mono.defer(() -> auditTrail.record(new AuditEntry(packet.deviceId(), AuditAction.INGEST_PACKET, "SUCCESS", clock.instant(), requestId)))).onErrorResume(error -> auditTrail.record(new AuditEntry(packet.deviceId(), AuditAction.INGEST_PACKET, "FAILURE", clock.instant(), requestId)).then(Mono.<Void>error(error))).doFinally(signal -> meters.recordLatency("validate", Duration.between(start, clock.instant())));
        });
    }
}
