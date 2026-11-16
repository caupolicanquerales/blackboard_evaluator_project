package com.blackboard.telemetry.shared.observability;

import io.micrometer.core.instrument.MeterRegistry;
import java.time.Duration;
import java.util.Objects;
import com.blackboard.telemetry.ingestion.domain.SourceKind;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import com.blackboard.telemetry.history.domain.RevisionReason;

public class TelemetryMeters {

    private static final String STAGE_VALIDATE = "validate";
    private static final String STAGE_HISTORY = "history";

    private final MeterRegistry registry;

    public TelemetryMeters(MeterRegistry registry) {
        this.registry = Objects.requireNonNull(registry, "registry");
    }

    public void packetReceived(SourceKind sourceKind) {
        registry.counter("telemetry.packets.received", "source_kind", sourceKind.name()).increment();
    }

    public void sampleValidated(MetricKind metric, ValidationStatus status) {
        registry.counter("telemetry.samples.validated", "metric", metric.name(), "status", status.name()).increment();
    }

    public void sampleReordered(MetricKind metric) {
        registry.counter("telemetry.samples.reordered", "metric", metric.name()).increment();
    }

    public void revisionAppended(RevisionReason reason) {
        registry.counter("telemetry.revisions.appended", "reason", reason.name()).increment();
    }

    public void recordLatency(String stage, Duration elapsed) {
        if (!STAGE_VALIDATE.equals(stage) && !STAGE_HISTORY.equals(stage)) {
            throw new IllegalArgumentException("Unknown pipeline stage: " + stage);
        }
        registry.timer("telemetry.pipeline.latency", "stage", stage).record(elapsed);
    }
}
