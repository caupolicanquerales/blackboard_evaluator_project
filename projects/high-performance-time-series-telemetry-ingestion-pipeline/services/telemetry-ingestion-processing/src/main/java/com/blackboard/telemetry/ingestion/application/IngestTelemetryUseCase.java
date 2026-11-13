package com.blackboard.telemetry.ingestion.application;

import java.time.Instant;
import java.util.List;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import org.springframework.stereotype.Service;
import com.blackboard.telemetry.eventstore.application.TelemetryEventStore;
import com.blackboard.telemetry.eventstore.domain.TelemetryRecord;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.shared.observability.AuditEntry;
import com.blackboard.telemetry.shared.observability.AuditTrail;

@Service
public class IngestTelemetryUseCase {

    private final TelemetryEventStore store;

    private final AuditTrail auditTrail;

    private final MeterRegistry meterRegistry;

    public IngestTelemetryUseCase(TelemetryEventStore store, AuditTrail auditTrail, MeterRegistry meterRegistry) {
        this.store = store;
        this.auditTrail = auditTrail;
        this.meterRegistry = meterRegistry;
    }

    public Mono<Long> ingest(Flux<TelemetrySample> samples, String correlationId) {
        return Mono.defer(() -> {
            Timer.Sample timerSample = Timer.start(meterRegistry);
            return samples.collectList().flatMap(list -> {
                List<TelemetryRecord> records = list.stream().map(this::toRecord).toList();
                String actor = list.isEmpty() || list.get(0).deviceId() == null ? "system" : list.get(0).deviceId();
                AuditEntry entry = new AuditEntry(actor, "INGEST", "ACCEPTED", Instant.now(), correlationId);
                return Flux.fromIterable(records).concatMap(store::append).count().flatMap(count -> auditTrail.record(entry).thenReturn(count));
            }).doOnSuccess(count -> {
                meterRegistry.counter("telemetry.ingress.packets", "outcome", "accepted").increment();
                timerSample.stop(meterRegistry.timer("telemetry.ingest.latency", "outcome", "accepted"));
            });
        });
    }

    private TelemetryRecord toRecord(TelemetrySample sample) {
        String status = isValid(sample) ? "VALIDATED" : "VALIDATION_FAILED";
        String metricTag = sample.metric() == null ? "unknown" : sample.metric();
        meterRegistry.counter("telemetry.samples.validated", "metric", metricTag, "status", status).increment();
        return new TelemetryRecord(sample.deviceId(), sample.metric(), sample.tDevice(), sample.tIngress(), sample.value(), status, 1L);
    }

    private static boolean isValid(TelemetrySample sample) {
        return sample.deviceId() != null && !sample.deviceId().isBlank()
                && sample.metric() != null && !sample.metric().isBlank()
                && sample.tDevice() != null && Double.isFinite(sample.value());
    }
}
