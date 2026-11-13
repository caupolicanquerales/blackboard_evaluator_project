package com.blackboard.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class TelemetrySampleTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:05Z");

    @Test
    void accessors_constructedValues_returnConstructorValues() {
        TelemetrySample sample = new TelemetrySample("dev-1", "temp", T_DEVICE, T_INGRESS, 21.5);

        assertThat(sample.deviceId()).isEqualTo("dev-1");
        assertThat(sample.metric()).isEqualTo("temp");
        assertThat(sample.tDevice()).isEqualTo(T_DEVICE);
        assertThat(sample.tIngress()).isEqualTo(T_INGRESS);
        assertThat(sample.value()).isEqualTo(21.5);
    }

    @Test
    void equals_sameValues_areEqualWithSameHashCode() {
        TelemetrySample a = new TelemetrySample("dev-1", "temp", T_DEVICE, T_INGRESS, 21.5);
        TelemetrySample b = new TelemetrySample("dev-1", "temp", T_DEVICE, T_INGRESS, 21.5);

        assertThat(a).isEqualTo(b);
        assertThat(a.hashCode()).isEqualTo(b.hashCode());
    }

    @Test
    void equals_differentValue_areNotEqual() {
        TelemetrySample a = new TelemetrySample("dev-1", "temp", T_DEVICE, T_INGRESS, 21.5);
        TelemetrySample b = new TelemetrySample("dev-1", "temp", T_DEVICE, T_INGRESS, 22.0);

        assertThat(a).isNotEqualTo(b);
    }

    @Test
    void constructor_nullAndNegativeInputs_doesNotValidate() {
        TelemetrySample sample = new TelemetrySample(null, "", null, null, -1.0);

        assertThat(sample.deviceId()).isNull();
        assertThat(sample.value()).isEqualTo(-1.0);
    }
}
