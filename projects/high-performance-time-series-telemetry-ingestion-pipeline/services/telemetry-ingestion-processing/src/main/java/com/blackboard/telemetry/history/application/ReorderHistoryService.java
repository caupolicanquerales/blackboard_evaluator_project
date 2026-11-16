package com.blackboard.telemetry.history.application;

import com.blackboard.telemetry.history.domain.HistoryEvent;
import com.blackboard.telemetry.history.domain.HistoryEventType;
import com.blackboard.telemetry.history.domain.RevisionReason;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidatedSampleEvent;
import com.blackboard.telemetry.shared.audit.AuditAction;
import com.blackboard.telemetry.shared.audit.AuditEntry;
import com.blackboard.telemetry.shared.audit.AuditTrail;
import com.blackboard.telemetry.shared.config.TelemetryProperties;
import com.blackboard.telemetry.shared.observability.TelemetryMeters;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Mono;

public class ReorderHistoryService {

    private static final Logger log = LoggerFactory.getLogger(ReorderHistoryService.class);

    private static final String ACTOR = "history-service";

    private static final String SUCCESS = "SUCCESS";

    private static final String FAILURE = "FAILURE";

    private final TelemetryHistoryRepository repository;

    private final HistoryEventPublisher publisher;

    private final AuditTrail auditTrail;

    private final TelemetryMeters meters;

    private final TelemetryProperties properties;

    private final Clock clock;

    public ReorderHistoryService(TelemetryHistoryRepository repository, HistoryEventPublisher publisher, AuditTrail auditTrail, TelemetryMeters meters, TelemetryProperties properties, Clock clock) {
        this.repository = repository;
        this.publisher = publisher;
        this.auditTrail = auditTrail;
        this.meters = meters;
        this.properties = properties;
        this.clock = clock;
    }

    private Mono<Void> store(TelemetrySample sample, String correlationId, Optional<Instant> latest) {
        return repository.appendSample(sample).flatMap(id -> stage(id, sample, correlationId, latest).then(Mono.defer(() -> bufferWindow(sample, correlationId))));
    }

    private Mono<Void> stage(long id, TelemetrySample sample, String correlationId, Optional<Instant> latest) {
        Duration lateness = Duration.between(sample.tDevice(), sample.tIngress());
        if (lateness.compareTo(properties.reorderWindow()) > 0) {
            return repository.appendRevision(id, RevisionReason.BACKFILL, sample.value(), sample.tIngress()).flatMap(revisionNo -> {
                meters.revisionAppended(RevisionReason.BACKFILL);
                log.info("revision appended");
                return audit(AuditAction.APPEND_REVISION, SUCCESS, correlationId).then(publisher.publish(new HistoryEvent(HistoryEventType.REVISION_APPENDED, sample, revisionNo, 0, correlationId)));
            }).onErrorResume(error -> failed(AuditAction.APPEND_REVISION, correlationId, error));
        }
        if (latest.isPresent() && latest.get().isAfter(sample.tDevice())) {
            return Mono.defer(() -> {
                meters.sampleReordered(sample.metric());
                log.info("sample reordered within backfill window");
                return publisher.publish(new HistoryEvent(HistoryEventType.SAMPLE_BACKFILLED, sample, 0, 0, correlationId));
            }).onErrorResume(error -> failed(AuditAction.BROADCAST_WINDOW, correlationId, error));
        }
        return Mono.empty();
    }

    private Mono<Void> bufferWindow(TelemetrySample sample, String correlationId) {
        Instant from = sample.tDevice().minus(properties.reorderWindow());
        return repository.findWindow(sample.deviceId(), sample.metric(), from, sample.tDevice(), properties.reorderBufferCapacity()).count().flatMap(size -> {
            log.info("window buffered");
            return publisher.publish(new HistoryEvent(HistoryEventType.WINDOW_BUFFERED, sample, 0, size.intValue(), correlationId)).then(audit(AuditAction.BROADCAST_WINDOW, SUCCESS, correlationId));
        }).onErrorResume(error -> failed(AuditAction.BROADCAST_WINDOW, correlationId, error));
    }

    private Mono<Void> audit(AuditAction action, String outcome, String correlationId) {
        return Mono.defer(() -> auditTrail.record(new AuditEntry(ACTOR, action, outcome, clock.instant(), correlationId)));
    }

    private Mono<Void> failed(AuditAction action, String correlationId, Throwable error) {
        return audit(action, FAILURE, correlationId).onErrorResume(auditError -> Mono.empty()).then(Mono.<Void>error(error));
    }

    public Mono<Void> handle(ValidatedSampleEvent event) {
        Instant started = clock.instant();
        TelemetrySample sample = event.sample();
        return repository.findLatestTDevice(sample.deviceId(), sample.metric()).map(Optional::of).defaultIfEmpty(Optional.empty()).flatMap(latest -> store(sample, event.correlationId(), latest)).doFinally(signal -> meters.recordLatency("history", Duration.between(started, clock.instant())));
    }
}
