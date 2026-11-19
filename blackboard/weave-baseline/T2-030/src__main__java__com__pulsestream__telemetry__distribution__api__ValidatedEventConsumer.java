package com.pulsestream.telemetry.distribution.api;
import org.springframework.stereotype.Component;

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

@Component
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

    public Flux<TelemetryWindowBroadcast> buffer(Flux<TelemetryEvent> events) {
        return events.concatMap(event -> {
            if (policy.permits(event)) {
                return Mono.just(event);
            }
            metrics.broadcastDropped("untrusted-publisher");
            return auditTrail.record(new AuditEntry("telemetry-broadcast", "authorization-denied", "denied", Instant.now(), event.deviceId())).then(Mono.<TelemetryEvent>empty());
        }).windowTimeout(windowMaxEvents, windowDuration).concatMap(window -> window.collectList()).filter(batch -> !batch.isEmpty()).map(batch -> {
            Instant end = Instant.now();
            metrics.windowBroadcast("buffered");
            return new TelemetryWindowBroadcast(end.minus(windowDuration), end, List.copyOf(batch));
        });
    }
}
