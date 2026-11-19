package com.pulsestream.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class TelemetrySampleTest {

    private static final Instant T_DEVICE = Instant.parse("2025-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2025-01-01T00:00:01Z");

    private static TelemetrySample sample(String device, double value) {
        return new TelemetrySample(device, "temp", T_DEVICE, T_INGRESS, value,
                ValidationStatus.VALIDATED, "{}");
    }

    @Test
    void accessors_afterConstruction_returnConstructorValues() {
        TelemetrySample s = sample("dev-1", 21.5);

        assertThat(s.deviceId()).isEqualTo("dev-1");
        assertThat(s.metric()).isEqualTo("temp");
        assertThat(s.tDevice()).isEqualTo(T_DEVICE);
        assertThat(s.tIngress()).isEqualTo(T_INGRESS);
        assertThat(s.value()).isEqualTo(21.5);
        assertThat(s.status()).isEqualTo(ValidationStatus.VALIDATED);
        assertThat(s.payload()).isEqualTo("{}");
    }

    @Test
    void equals_sameComponents_areEqualWithSameHashCode() {
        assertThat(sample("dev-1", 1.0)).isEqualTo(sample("dev-1", 1.0))
                .hasSameHashCodeAs(sample("dev-1", 1.0));
    }

    @Test
    void equals_differentDevice_areNotEqual() {
        assertThat(sample("dev-1", 1.0)).isNotEqualTo(sample("dev-2", 1.0));
    }

    @Test
    void equals_differentValue_areNotEqual() {
        assertThat(sample("dev-1", 1.0)).isNotEqualTo(sample("dev-1", 2.0));
    }

    @Test
    void equals_differentStatus_areNotEqual() {
        TelemetrySample other = new TelemetrySample("dev-1", "temp", T_DEVICE, T_INGRESS, 1.0,
                ValidationStatus.VALIDATION_FAILED, "{}");

        assertThat(sample("dev-1", 1.0)).isNotEqualTo(other);
    }
}
