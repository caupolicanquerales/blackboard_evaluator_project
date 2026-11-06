package com.pulsestream.telemetry.intake.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class MetricBoundaryPolicyTest {

    private static final Instant TS = Instant.parse("2024-01-01T00:00:00Z");

    private final MetricBoundaryPolicy policy =
            new MetricBoundaryPolicy(Map.of("temperature", new MetricBoundary(-10.0, 50.0)));

    private static TelemetrySample sample(String metric, double value) {
        return new TelemetrySample("device-1", metric, value, TS);
    }

    @Test
    void validate_valueWithinRange_returnsValid() {
        assertThat(policy.validate(sample("temperature", 20.0))).isEqualTo(ValidationStatus.VALID);
    }

    @ParameterizedTest
    @CsvSource({"-10.0", "50.0"})
    void validate_valueAtInclusiveLimit_returnsValid(double value) {
        assertThat(policy.validate(sample("temperature", value))).isEqualTo(ValidationStatus.VALID);
    }

    @ParameterizedTest
    @CsvSource({"-10.01", "50.01", "1000.0", "-1000.0"})
    void validate_valueOutsideRange_returnsOutOfBounds(double value) {
        assertThat(policy.validate(sample("temperature", value))).isEqualTo(ValidationStatus.OUT_OF_BOUNDS);
    }

    @Test
    void validate_metricWithoutBoundary_returnsUndefinedBoundary() {
        assertThat(policy.validate(sample("humidity", 10.0))).isEqualTo(ValidationStatus.UNDEFINED_BOUNDARY);
    }

    @Test
    void validate_emptyConfiguration_returnsUndefinedBoundary() {
        MetricBoundaryPolicy empty = new MetricBoundaryPolicy(Map.of());

        assertThat(empty.validate(sample("temperature", 20.0))).isEqualTo(ValidationStatus.UNDEFINED_BOUNDARY);
    }

    @Test
    void validate_boundariesComeFromConfiguration_usesConfiguredRange() {
        MetricBoundaryPolicy custom =
                new MetricBoundaryPolicy(Map.of("temperature", new MetricBoundary(100.0, 200.0)));

        assertThat(custom.validate(sample("temperature", 20.0))).isEqualTo(ValidationStatus.OUT_OF_BOUNDS);
    }
}
