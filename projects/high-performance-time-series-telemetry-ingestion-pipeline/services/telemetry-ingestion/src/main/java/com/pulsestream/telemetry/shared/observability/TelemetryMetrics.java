package com.pulsestream.telemetry.shared.observability;

import io.micrometer.core.instrument.Meter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tag;
import io.micrometer.core.instrument.Tags;
import io.micrometer.core.instrument.config.MeterFilter;
import java.time.Duration;
import java.util.Arrays;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class TelemetryMetrics {

    private static final String OTHER = "other";
    private static final String METER_PREFIX = "telemetry.";
    private static final List<String> ALLOWED_TAG_KEYS = List.of("status", "metric", "reason", "outcome");

    private final MeterRegistry registry;

    private static String closed(String value, String... allowed) {
        return value != null && Arrays.asList(allowed).contains(value) ? value : OTHER;
    }

    public void samplesIngested(String status) {
        registry.counter("telemetry.samples.ingested", "status", closed(status, "accepted", "VALIDATED", "VALIDATION_FAILED", "DUPLICATE", "REFUSED")).increment();
    }

    public void validationFailed(String metric) {
        registry.counter("telemetry.validation.failed", "metric", closed(metric, "temperature", "humidity", "pressure", "voltage", "current", "vibration")).increment();
    }

    public void backfillReordered() {
        registry.counter("telemetry.backfill.reordered").increment();
    }

    public void revisionAppended(String reason) {
        registry.counter("telemetry.revision.appended", "reason", closed(reason, "backfill", "correction", "late")).increment();
    }

    public void windowBroadcast(String outcome) {
        registry.counter("telemetry.window.broadcast", "outcome", closed(outcome, "buffered", "broadcast", "success")).increment();
    }

    public void broadcastDropped(String reason) {
        registry.counter("telemetry.broadcast.dropped", "reason", closed(reason, "overflow", "slow_consumer", "timeout")).increment();
    }

    public void ingestDuration(String outcome, Duration elapsed) {
        registry.timer("telemetry.ingest.duration", "outcome", closed(outcome, "success", "failure", "refused")).record(elapsed);
    }

    public TelemetryMetrics(MeterRegistry registry) {
        this.registry = registry;
        registry.config().meterFilter(new MeterFilter() {

            @Override
            public Meter.Id map(Meter.Id id) {
                if (!id.getName().startsWith(METER_PREFIX)) {
                    return id;
                }
                List<Tag> kept = id.getTags().stream().filter(tag -> ALLOWED_TAG_KEYS.contains(tag.getKey())).toList();
                return id.replaceTags(Tags.of(kept));
            }
        });
    }
}
