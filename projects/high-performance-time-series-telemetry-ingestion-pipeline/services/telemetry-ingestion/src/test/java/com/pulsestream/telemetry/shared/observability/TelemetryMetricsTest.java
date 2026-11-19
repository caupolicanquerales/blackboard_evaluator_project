package com.pulsestream.telemetry.shared.observability;

import static org.assertj.core.api.Assertions.assertThat;

import io.micrometer.core.instrument.Tag;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.Test;

class TelemetryMetricsTest {

    private final SimpleMeterRegistry registry = new SimpleMeterRegistry();
    private final TelemetryMetrics metrics = new TelemetryMetrics(registry);

    @Test
    void samplesIngested_knownStatus_incrementsTaggedCounter() {
        metrics.samplesIngested("accepted");

        assertThat(registry.get("telemetry.samples.ingested").tag("status", "accepted").counter().count()).isEqualTo(1.0);
    }

    @Test
    void samplesIngested_unknownStatus_tagsOther() {
        metrics.samplesIngested("sensor-9f8e7d");

        assertThat(registry.get("telemetry.samples.ingested").tag("status", "other").counter().count()).isEqualTo(1.0);
    }

    @Test
    void samplesIngested_nullStatus_tagsOther() {
        metrics.samplesIngested(null);

        assertThat(registry.get("telemetry.samples.ingested").tag("status", "other").counter().count()).isEqualTo(1.0);
    }

    @Test
    void validationFailed_knownMetric_incrementsTaggedCounter() {
        metrics.validationFailed("temperature");

        assertThat(registry.get("telemetry.validation.failed").tag("metric", "temperature").counter().count()).isEqualTo(1.0);
    }

    @Test
    void validationFailed_unknownMetric_tagsOther() {
        metrics.validationFailed("device-123");

        assertThat(registry.get("telemetry.validation.failed").tag("metric", "other").counter().count()).isEqualTo(1.0);
    }

    @Test
    void backfillReordered_called_incrementsCounter() {
        metrics.backfillReordered();
        metrics.backfillReordered();

        assertThat(registry.get("telemetry.backfill.reordered").counter().count()).isEqualTo(2.0);
    }

    @Test
    void revisionAppended_knownReason_incrementsTaggedCounter() {
        metrics.revisionAppended("backfill");

        assertThat(registry.get("telemetry.revision.appended").tag("reason", "backfill").counter().count()).isEqualTo(1.0);
    }

    @Test
    void revisionAppended_unknownReason_tagsOther() {
        metrics.revisionAppended("tenant-42");

        assertThat(registry.get("telemetry.revision.appended").tag("reason", "other").counter().count()).isEqualTo(1.0);
    }

    @Test
    void windowBroadcast_knownOutcome_incrementsTaggedCounter() {
        metrics.windowBroadcast("success");

        assertThat(registry.get("telemetry.window.broadcast").tag("outcome", "success").counter().count()).isEqualTo(1.0);
    }

    @Test
    void windowBroadcast_unknownOutcome_tagsOther() {
        metrics.windowBroadcast("window-77");

        assertThat(registry.get("telemetry.window.broadcast").tag("outcome", "other").counter().count()).isEqualTo(1.0);
    }

    @Test
    void broadcastDropped_knownReason_incrementsTaggedCounter() {
        metrics.broadcastDropped("overflow");

        assertThat(registry.get("telemetry.broadcast.dropped").tag("reason", "overflow").counter().count()).isEqualTo(1.0);
    }

    @Test
    void broadcastDropped_unknownReason_tagsOther() {
        metrics.broadcastDropped("subscriber-abc");

        assertThat(registry.get("telemetry.broadcast.dropped").tag("reason", "other").counter().count()).isEqualTo(1.0);
    }

    @Test
    void ingestDuration_knownOutcome_recordsTimer() {
        metrics.ingestDuration("success", Duration.ofMillis(50));

        var timer = registry.get("telemetry.ingest.duration").tag("outcome", "success").timer();
        assertThat(timer.count()).isEqualTo(1L);
        assertThat(timer.totalTime(java.util.concurrent.TimeUnit.MILLISECONDS)).isEqualTo(50.0);
    }

    @Test
    void ingestDuration_unknownOutcome_tagsOther() {
        metrics.ingestDuration("sensor-1", Duration.ofMillis(5));

        assertThat(registry.get("telemetry.ingest.duration").tag("outcome", "other").timer().count()).isEqualTo(1L);
    }

    @Test
    void anyMethod_identifierLikeValue_neverAppearsAsTagValue() {
        metrics.samplesIngested("sensor-9f8e7d");
        metrics.validationFailed("device-123");
        metrics.revisionAppended("tenant-42");
        metrics.windowBroadcast("window-77");
        metrics.broadcastDropped("subscriber-abc");
        metrics.ingestDuration("sensor-1", Duration.ofMillis(1));

        List<Tag> tags = registry.getMeters().stream()
                .map(m -> m.getId())
                .flatMap(id -> id.getTags().stream())
                .toList();
        assertThat(tags).extracting(Tag::getValue).containsOnly("other");
    }
}
