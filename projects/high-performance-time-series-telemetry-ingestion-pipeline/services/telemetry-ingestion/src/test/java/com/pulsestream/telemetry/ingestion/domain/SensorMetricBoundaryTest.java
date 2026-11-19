package com.pulsestream.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class SensorMetricBoundaryTest {

    private final SensorMetricBoundary boundary = new SensorMetricBoundary();

    @Test
    void check_swimPaceAtBoundary_isValidationFailed() {
        assertThat(boundary.check("swim_pace", 45.0)).isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void check_swimPaceAboveBoundary_isValidated() {
        assertThat(boundary.check("swim_pace", 45.1)).isEqualTo(ValidationStatus.VALIDATED);
    }

    @Test
    void check_swimPaceBelowBoundary_isValidationFailed() {
        assertThat(boundary.check("swim_pace", 10.0)).isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void check_nanValue_isValidationFailed() {
        assertThat(boundary.check("swim_pace", Double.NaN)).isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @ParameterizedTest
    @CsvSource({"heart_rate,0.0", "heart_rate,45.0", "heart_rate,-3.5", "cadence,180.0"})
    void check_otherMetricFiniteValue_isValidated(String metric, double value) {
        assertThat(boundary.check(metric, value)).isEqualTo(ValidationStatus.VALIDATED);
    }
}
