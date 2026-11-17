package com.pulsestream.telemetry.intake.application;

import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import com.pulsestream.telemetry.shared.observability.AuditEntry;
import com.pulsestream.telemetry.shared.observability.AuditTrail;
import com.pulsestream.telemetry.shared.observability.StepLog;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.Instant;
import java.util.List;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

public class IntakeService {

    private final Sinks.Many<TelemetrySample> sink;

    private final AuditTrail auditTrail;

    private final StepLog stepLog;

    private final MeterRegistry meterRegistry;

    public IntakeService(TelemetryProperties properties, AuditTrail auditTrail, StepLog stepLog, MeterRegistry meterRegistry) {
        this.sink = Sinks.many().multicast().onBackpressureBuffer(properties.bufferCapacity(), false);
        this.auditTrail = auditTrail;
        this.stepLog = stepLog;
        this.meterRegistry = meterRegistry;
    }

    public Flux<TelemetrySample> stream() {
        return sink.asFlux();
    }

    public Mono<Integer> receive(List<TelemetrySample> samples) {
        return Mono.defer(() -> {
            Instant now = Instant.now();
            int accepted = 0;
            for (TelemetrySample sample : samples) {
                if (sink.tryEmitNext(sample.withIngress(now)) == Sinks.EmitResult.OK) {
                    accepted++;
                } else {
                    meterRegistry.counter("telemetry.pipeline.dropped", "stage", "intake").increment();
                }
            }
            String outcome = accepted == samples.size() ? "accepted" : "overflow";
            String correlationId = samples.isEmpty() ? "unknown" : samples.get(0).correlationId();
            meterRegistry.counter("telemetry.intake.packets", "outcome", outcome).increment();
            stepLog.emit("intake.packet.received", correlationId);
            return auditTrail.record(new AuditEntry("device", "ingest", outcome, now, correlationId)).thenReturn(accepted);
        });
    }
}
