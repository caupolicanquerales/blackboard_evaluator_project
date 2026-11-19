package com.pulsestream.telemetry.shared.observability;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Meter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tag;
import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.config.MeterFilter;
import java.time.Duration;
import java.util.List;
import java.util.Set;

public class TelemetryMetrics {

    private static final String OTHER = "other";

    private static final Set<String> ALLOWED_TAG_KEYS = Set.of("status", "metric", "reason", "outcome");

    private static final Set<String> STATUSES = Set.of("VALIDATED", "VALIDATION_FAILED", "DUPLICATE", "REFUSED", "accepted");

    private static final Set<String> METRICS = Set.of("temperature", "humidity", "pressure", "voltage", "current", "vibration", "speed", "power", "flow", "level");

    private static final Set<String> REVISION_REASONS = Set.of("backfill", "correction", "late_arrival", "duplicate");

    private static final Set<String> BROADCAST_OUTCOMES = Set.of("buffered", "broadcast", "success");

    private static final Set<String> DROP_REASONS = Set.of("overflow", "expired", "slow_consumer", "closed");

    private static final Set<String> INGEST_OUTCOMES = Set.of("success", "failure", "refused", "duplicate");

    private final MeterRegistry registry;

    public void samplesIngested(String status) {
        counter("telemetry.samples.ingested", "status", closed(status, STATUSES)).increment();
    }

    public void validationFailed(String metric) {
        counter("telemetry.validation.failed", "metric", closed(metric, METRICS)).increment();
    }

    public void backfillReordered() {
        registry.counter("telemetry.backfill.reordered").increment();
    }

    public void revisionAppended(String reason) {
        counter("telemetry.revision.appended", "reason", closed(reason, REVISION_REASONS)).increment();
    }

    public void windowBroadcast(String outcome) {
        counter("telemetry.window.broadcast", "outcome", closed(outcome, BROADCAST_OUTCOMES)).increment();
    }

    public void broadcastDropped(String reason) {
        counter("telemetry.broadcast.dropped", "reason", closed(reason, DROP_REASONS)).increment();
    }

    public void ingestDuration(String outcome, Duration elapsed) {
        Timer.builder("telemetry.ingest.duration").tag("outcome", closed(outcome, INGEST_OUTCOMES)).register(registry).record(elapsed);
    }

    private Counter counter(String name, String tagKey, String tagValue) {
        return registry.counter(name, tagKey, tagValue);
    }

    private static String closed(String value, Set<String> allowed) {
        return value != null && allowed.contains(value) ? value : OTHER;
    }

    public TelemetryMetrics(MeterRegistry registry) {
        this.registry = registry;
        this.registry.config().meterFilter(new MeterFilter() {

            @Override
            public Meter.Id map(Meter.Id id) {
                if (!id.getName().startsWith("telemetry.")) {
                    return id;
                }
                List<Tag> kept = id.getTags().stream().filter(tag -> ALLOWED_TAG_KEYS.contains(tag.getKey())).toList();
                return id.replaceTags(kept);
            }
        });
    }
}
