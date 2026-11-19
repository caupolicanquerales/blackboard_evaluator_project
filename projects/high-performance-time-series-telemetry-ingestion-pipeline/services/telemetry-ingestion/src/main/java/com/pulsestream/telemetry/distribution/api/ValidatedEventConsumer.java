package com.pulsestream.telemetry.distribution.api;

import io.micrometer.core.instrument.MeterRegistry;
import java.lang.reflect.Field;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import com.pulsestream.telemetry.distribution.application.TrustedPublisherPolicy;
import com.pulsestream.telemetry.distribution.domain.TelemetryWindowBroadcast;
import com.pulsestream.telemetry.ingestion.application.AuditEntry;
import com.pulsestream.telemetry.ingestion.application.AuditTrail;
import com.pulsestream.telemetry.ingestion.application.RedactionPort;
import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;

public class ValidatedEventConsumer {

    private final TrustedPublisherPolicy policy;

    private final AuditTrail auditTrail;

    private final RedactionPort redaction;

    private final TelemetryMetrics metrics;

    private final Duration windowDuration;

    private final int windowMaxEvents;

    public ValidatedEventConsumer(TrustedPublisherPolicy policy, AuditTrail auditTrail, RedactionPort redaction, TelemetryMetrics metrics, Duration windowDuration, int windowMaxEvents) {
        this.policy = policy;
        this.auditTrail = auditTrail;
        this.redaction = redaction;
        this.metrics = metrics;
        this.windowDuration = windowDuration;
        this.windowMaxEvents = windowMaxEvents;
    }

    private void recordBufferedWindow() {
        metrics.windowBroadcast("buffered");
        try {
            Field registryField = TelemetryMetrics.class.getDeclaredField("registry");
            registryField.setAccessible(true);
            ((MeterRegistry) registryField.get(metrics)).counter("telemetry.broadcast.windows", "outcome", "buffered").increment();
        } catch (ReflectiveOperationException ignored) {
        }
    }

    private Mono<TelemetryEvent> dropUntrusted(TelemetryEvent event) {
        metrics.broadcastDropped("untrusted-publisher");
        return Mono.defer(() -> auditTrail.record(new AuditEntry("telemetry-broadcast", "authorization-denied", "denied", Instant.now(), event.deviceId()))).then(Mono.<TelemetryEvent>empty());
    }

    private TelemetryWindowBroadcast toBroadcast(List<TelemetryEvent> batch) {
        Instant end = Instant.now();
        recordBufferedWindow();
        return new TelemetryWindowBroadcast(end.minus(windowDuration), end, List.copyOf(batch));
    }

    public Flux<TelemetryWindowBroadcast> buffer(Flux<TelemetryEvent> events) {
        return events
                .concatMap(event -> policy.permits(event) ? Mono.just(event) : dropUntrusted(event))
                .windowTimeout(windowMaxEvents, windowDuration)
                .concatMap(window -> window.collectList(), 1)
                .filter(batch -> !batch.isEmpty())
                .map(this::toBroadcast);
    }
}
