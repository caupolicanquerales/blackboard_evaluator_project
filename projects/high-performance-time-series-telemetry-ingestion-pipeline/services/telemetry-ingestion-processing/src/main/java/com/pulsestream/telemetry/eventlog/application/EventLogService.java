package com.pulsestream.telemetry.eventlog.application;

import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import com.pulsestream.telemetry.shared.observability.AuditEntry;
import com.pulsestream.telemetry.shared.observability.AuditTrail;
import com.pulsestream.telemetry.shared.observability.StepLog;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.Instant;
import reactor.core.publisher.Mono;
import org.springframework.stereotype.Service;

@Service
public class EventLogService {

    private final EventLogRepository repository;

    private final EventBroadcast broadcast;

    private final AuditTrail auditTrail;

    private final StepLog stepLog;

    private final MeterRegistry meterRegistry;

    public EventLogService(EventLogRepository repository, EventBroadcast broadcast, AuditTrail auditTrail, StepLog stepLog, MeterRegistry meterRegistry) {
        this.repository = repository;
        this.broadcast = broadcast;
        this.auditTrail = auditTrail;
        this.stepLog = stepLog;
        this.meterRegistry = meterRegistry;
    }

    public Mono<EventRecord> append(TelemetrySample sample) {
        return repository.append(sample).flatMap(record -> {
            boolean revision = EventRecord.KIND_REVISION.equals(record.kind());
            meterRegistry.counter("telemetry.eventlog.appended", "kind", revision ? "revision" : "record").increment();
            stepLog.emit(revision ? "eventlog.revision.appended" : "eventlog.record.appended", sample.correlationId());
            if (broadcast.publish(record)) {
                stepLog.emit("eventlog.broadcast.published", sample.correlationId());
            } else {
                meterRegistry.counter("telemetry.pipeline.dropped", "stage", "broadcast").increment();
            }
            return auditTrail.record(new AuditEntry("eventlog", "append", "success", Instant.now(), sample.correlationId())).thenReturn(record);
        }).onErrorResume(error -> {
            meterRegistry.counter("telemetry.pipeline.dropped", "stage", "eventlog").increment();
            return auditTrail.record(new AuditEntry("eventlog", "append", "failure", Instant.now(), sample.correlationId())).then(Mono.<EventRecord>empty());
        });
    }
}
