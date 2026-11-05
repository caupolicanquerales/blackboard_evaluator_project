package com.blackboard.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class SensorMetricBoundaryTest {

    private static final String DEVICE = "device-1";
    private static final Instant T_DEVICE = Instant.parse("2026-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2026-01-01T10:00:05Z");

    private final SensorMetricBoundary boundary = new SensorMetricBoundary();

    private static TelemetrySample sample(String metric, double value) {
        return new TelemetrySample(DEVICE, T_DEVICE, T_INGRESS, metric, value);
    }

    @ParameterizedTest
    @CsvSource({
        "heart_rate, 30.0", "heart_rate, 30.1", "heart_rate, 150.0", "heart_rate, 239.9", "heart_rate, 240.0",
        "power, 0.0", "power, 0.1", "power, 1200.0", "power, 2499.9", "power, 2500.0",
        "cadence, 0.0", "cadence, 0.1", "cadence, 90.0", "cadence, 219.9", "cadence, 220.0",
        "swim_pace, 45.1", "swim_pace, 46.0", "swim_pace, 90.0", "swim_pace, 600.0"
    })
    void validate_valueWithinInclusiveLimits_isFlaggedValid(String metric, double value) {
        TelemetrySample result = boundary.validate(sample(metric, value));

        assertThat(result.status()).isEqualTo(ValidationStatus.VALID);
    }

    @ParameterizedTest
    @CsvSource({
        "heart_rate, 29.9", "heart_rate, 0.0", "heart_rate, -1.0", "heart_rate, 240.1", "heart_rate, 400.0",
        "power, -0.1", "power, -50.0", "power, 2500.1", "power, 5000.0",
        "cadence, -0.1", "cadence, -10.0", "cadence, 220.1", "cadence, 400.0",
        "swim_pace, 45.0", "swim_pace, 44.9", "swim_pace, 0.0", "swim_pace, -5.0"
    })
    void validate_valueOutsideLimits_isFlaggedValidationFailed(String metric, double value) {
        TelemetrySample result = boundary.validate(sample(metric, value));

        assertThat(result.status()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @ParameterizedTest
    @CsvSource({"heart_rate, 150.0", "power, 2501.0", "swim_pace, 30.0"})
    void validate_anyOutcome_keepsPayloadAndIngressTime(String metric, double value) {
        TelemetrySample result = boundary.validate(sample(metric, value));

        assertThat(result.deviceId()).isEqualTo(DEVICE);
        assertThat(result.tDevice()).isEqualTo(T_DEVICE);
        assertThat(result.tIngress()).isEqualTo(T_INGRESS);
        assertThat(result.metric()).isEqualTo(metric);
        assertThat(result.value()).isEqualTo(value);
    }

    @Test
    void validate_violatingSample_isReturnedNotDropped() {
        TelemetrySample result = boundary.validate(sample("heart_rate", 400.0));

        assertThat(result).isNotNull();
        assertThat(result.value()).isEqualTo(400.0);
    }

    @Test
    void validate_unknownMetric_isRejectedExplicitly() {
        assertThatThrownBy(() -> boundary.validate(sample("blood_oxygen", 98.0)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("blood_oxygen");
    }

    @Test
    void validate_nullSample_throwsNullPointerException() {
        assertThatThrownBy(() -> boundary.validate(null)).isInstanceOf(NullPointerException.class);
    }
}
