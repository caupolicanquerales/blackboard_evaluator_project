package com.blackboard.telemetry.eventstore.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class TelemetryRecordTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:01Z");

    private TelemetryRecord record(long revision) {
        return new TelemetryRecord("dev-1", "temp", T_DEVICE, T_INGRESS, 21.5, "VALIDATED", revision);
    }

    @Test
    void accessors_constructedRecord_returnConstructorValues() {
        TelemetryRecord record = record(1L);

        assertThat(record.deviceId()).isEqualTo("dev-1");
        assertThat(record.metric()).isEqualTo("temp");
        assertThat(record.tDevice()).isEqualTo(T_DEVICE);
        assertThat(record.tIngress()).isEqualTo(T_INGRESS);
        assertThat(record.value()).isEqualTo(21.5);
        assertThat(record.status()).isEqualTo("VALIDATED");
        assertThat(record.revision()).isEqualTo(1L);
    }

    @Test
    void equals_sameComponents_areEqualWithSameHashCode() {
        assertThat(record(1L)).isEqualTo(record(1L)).hasSameHashCodeAs(record(1L));
    }

    @Test
    void equals_differentRevision_areNotEqual() {
        assertThat(record(1L)).isNotEqualTo(record(2L));
    }

    @Test
    void accessors_validationFailedStatus_returnsStatus() {
        TelemetryRecord failed = new TelemetryRecord("dev-1", "temp", T_DEVICE, T_INGRESS, Double.NaN,
                "VALIDATION_FAILED", 1L);

        assertThat(failed.status()).isEqualTo("VALIDATION_FAILED");
    }
}
