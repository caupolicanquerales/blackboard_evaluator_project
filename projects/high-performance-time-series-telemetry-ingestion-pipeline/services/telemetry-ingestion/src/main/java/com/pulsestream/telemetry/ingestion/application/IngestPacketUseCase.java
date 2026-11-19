package com.pulsestream.telemetry.ingestion.application;

import com.pulsestream.telemetry.ingestion.domain.SensorMetricBoundary;
import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;
import com.pulsestream.telemetry.ingestion.domain.TelemetryRevision;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;
import com.pulsestream.telemetry.shared.observability.CorrelationWebFilter;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.function.BiFunction;
import java.util.function.Function;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public class IngestPacketUseCase {

    private static final Logger LOG = LoggerFactory.getLogger(IngestPacketUseCase.class);

    private final TelemetryRecordRepository repository;

    private final EventPublisher publisher;

    private final AuditTrail auditTrail;

    private final SensorMetricBoundary boundary;

    private final BackfillReorderer reorderer;

    private final RedactionPort redaction;

    private final TelemetryMetrics metrics;

    private final Clock clock;

    private final Duration lateAfter;

    private final String publisherId;

    public IngestPacketUseCase(TelemetryRecordRepository repository, EventPublisher publisher, AuditTrail auditTrail, SensorMetricBoundary boundary, BackfillReorderer reorderer, RedactionPort redaction, TelemetryMetrics metrics, Clock clock, Duration lateAfter, String publisherId) {
        this.repository = repository;
        this.publisher = publisher;
        this.auditTrail = auditTrail;
        this.boundary = boundary;
        this.reorderer = reorderer;
        this.redaction = redaction;
        this.metrics = metrics;
        this.clock = clock;
        this.lateAfter = lateAfter;
        this.publisherId = publisherId;
    }

    public Mono<IngestSummary> ingest(String authenticatedDeviceId, Flux<TelemetrySample> samples) {
        Instant started = clock.instant();
        BiFunction<String, String, Mono<Void>> audit = (action, outcome) -> Mono.deferContextual(ctx -> Mono.defer(() -> auditTrail.record(new AuditEntry(redaction.mask(authenticatedDeviceId), action, outcome, clock.instant(), String.valueOf(ctx.getOrDefault(CorrelationWebFilter.contextKey(), "unknown"))))).onErrorResume(error -> Mono.<Void>empty()));
        Function<TelemetryEvent, Mono<Void>> publishEvent = event -> Mono.defer(() -> publisher.publish(event)).flatMap(accepted -> {
            if (Boolean.TRUE.equals(accepted)) {
                return Mono.<Void>empty();
            }
            metrics.broadcastDropped("publish-rejected");
            return audit.apply("broadcast-dropped", "DROPPED");
        });
        Function<TelemetrySample, Mono<int[]>> process = sample -> {
            Instant now = clock.instant();
            ValidationStatus checked = boundary.check(sample.metric(), sample.value());
            boolean late = sample.tDevice().isBefore(now.minus(lateAfter));
            ValidationStatus status = checked == ValidationStatus.VALIDATION_FAILED || !late ? checked : ValidationStatus.LATE;
            TelemetrySample stored = new TelemetrySample(sample.deviceId(), sample.metric(), sample.tDevice(), now, sample.value(), status, sample.payload());
            boolean failed = status == ValidationStatus.VALIDATION_FAILED;
            if (failed) {
                LOG.info("sample-validation-failed device={} metric={}", redaction.mask(sample.deviceId()), sample.metric());
                metrics.validationFailed(sample.metric());
            } else {
                LOG.info("sample-validated device={} metric={}", redaction.mask(sample.deviceId()), sample.metric());
            }
            int rejected = failed ? 1 : 0;
            return Mono.defer(() -> repository.appendRecord(stored)).flatMap(appended -> {
                if (Boolean.TRUE.equals(appended)) {
                    metrics.samplesIngested(status.name());
                    TelemetryEvent event = new TelemetryEvent(1, failed ? TelemetryEvent.Type.SAMPLE_VALIDATION_FAILED : TelemetryEvent.Type.SAMPLE_VALIDATED, TelemetryEvent.keyOf(sample.deviceId(), sample.metric(), sample.tDevice(), 1), sample.deviceId(), sample.metric(), sample.tDevice(), 1, sample.value(), status, publisherId);
                    return publishEvent.apply(event).thenReturn(new int[] { 1 - rejected, rejected, 0, 0 });
                }
                return Mono.defer(() -> repository.findLatestRevision(sample.deviceId(), sample.metric(), sample.tDevice())).flatMap(latest -> {
                    if (Double.compare(latest.value(), sample.value()) == 0) {
                        return Mono.just(new int[] { 0, 0, 0, 1 });
                    }
                    int next = latest.revisionNumber() + 1;
                    TelemetryRevision revision = new TelemetryRevision(sample.deviceId(), sample.metric(), sample.tDevice(), next, sample.value(), "CORRECTION");
                    TelemetryEvent event = new TelemetryEvent(1, TelemetryEvent.Type.REVISION_APPENDED, TelemetryEvent.keyOf(sample.deviceId(), sample.metric(), sample.tDevice(), next), sample.deviceId(), sample.metric(), sample.tDevice(), next, sample.value(), status, publisherId);
                    return Mono.defer(() -> repository.appendRevision(revision)).then(Mono.fromRunnable(() -> {
                        metrics.revisionAppended("CORRECTION");
                        LOG.info("revision-appended device={} metric={} revision={}", redaction.mask(sample.deviceId()), sample.metric(), next);
                    })).then(publishEvent.apply(event)).thenReturn(new int[] { 0, 0, 1, 0 });
                }).switchIfEmpty(Mono.fromSupplier(() -> new int[] { 0, 0, 0, 1 }));
            });
        };
        return samples.collectList().flatMap(list -> {
            LOG.info("packet-received device={} samples={}", redaction.mask(authenticatedDeviceId), list.size());
            if (list.stream().anyMatch(sample -> !authenticatedDeviceId.equals(sample.deviceId()))) {
                return audit.apply("authorization-denied", "DENIED").then(Mono.fromRunnable(() -> {
                    metrics.samplesIngested("REFUSED");
                    metrics.ingestDuration("refused", Duration.between(started, clock.instant()));
                })).thenReturn(new IngestSummary(0, 0, 0, 0, true));
            }
            return reorderer.reorder(Flux.fromIterable(list)).concatMap(process).reduce(new int[4], (total, part) -> {
                for (int i = 0; i < total.length; i++) {
                    total[i] += part[i];
                }
                return total;
            }).defaultIfEmpty(new int[4]).flatMap(total -> audit.apply("packet-ingested", "SUCCESS").then(Mono.fromRunnable(() -> metrics.ingestDuration("success", Duration.between(started, clock.instant())))).thenReturn(new IngestSummary(total[0], total[1], total[2], total[3], false)));
        });
    }
}
