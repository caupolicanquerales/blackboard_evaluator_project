package com.blackboard.telemetry.shared.observability;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.blackboard.telemetry.history.domain.RevisionReason;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.SourceKind;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Duration;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class TelemetryMetersTest {

    private SimpleMeterRegistry registry;
    private TelemetryMeters meters;

    @BeforeEach
    void setUp() {
        registry = new SimpleMeterRegistry();
        meters = new TelemetryMeters(registry);
    }

    @Test
    void packetReceived_sourceKind_incrementsCounterTaggedBySourceKind() {
        SourceKind kind = SourceKind.values()[0];

        meters.packetReceived(kind);

        assertThat(registry.get("telemetry.packets.received").tag("source_kind", kind.name())
                .counter().count()).isEqualTo(1.0);
    }

    @Test
    void sampleValidated_metricAndStatus_incrementsCounterWithBothTags() {
        MetricKind metric = MetricKind.values()[0];
        ValidationStatus status = ValidationStatus.values()[0];

        meters.sampleValidated(metric, status);
        meters.sampleValidated(metric, status);

        assertThat(registry.get("telemetry.samples.validated")
                .tag("metric", metric.name()).tag("status", status.name())
                .counter().count()).isEqualTo(2.0);
    }

    @Test
    void sampleReordered_metric_incrementsCounterTaggedByMetric() {
        MetricKind metric = MetricKind.values()[0];

        meters.sampleReordered(metric);

        assertThat(registry.get("telemetry.samples.reordered").tag("metric", metric.name())
                .counter().count()).isEqualTo(1.0);
    }

    @Test
    void revisionAppended_reason_incrementsCounterTaggedByReason() {
        RevisionReason reason = RevisionReason.values()[0];

        meters.revisionAppended(reason);

        assertThat(registry.get("telemetry.revisions.appended").tag("reason", reason.name())
                .counter().count()).isEqualTo(1.0);
    }

    @Test
    void recordLatency_validateStage_recordsTimerWithStageTag() {
        meters.recordLatency("validate", Duration.ofMillis(5));

        assertThat(registry.get("telemetry.pipeline.latency").tag("stage", "validate")
                .timer().count()).isEqualTo(1L);
    }

    @Test
    void recordLatency_historyStage_recordsTimerWithStageTag() {
        meters.recordLatency("history", Duration.ofMillis(7));

        assertThat(registry.get("telemetry.pipeline.latency").tag("stage", "history")
                .timer().totalTime(java.util.concurrent.TimeUnit.MILLISECONDS)).isEqualTo(7.0);
    }

    @Test
    void recordLatency_unknownStage_throwsIllegalArgument() {
        assertThatThrownBy(() -> meters.recordLatency("other", Duration.ofMillis(1)))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
