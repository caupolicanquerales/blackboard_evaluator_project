package com.pulsestream.telemetry.intake.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.intake.domain.TelemetrySample.MetricType;
import com.pulsestream.telemetry.intake.domain.TelemetrySample.ValidationStatus;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class SensorMetricBoundaryTest {

    private static final Instant DEVICE_TS = Instant.parse("2024-01-01T10:00:00Z");
    private static final Instant INGRESS_TS = Instant.parse("2024-01-01T10:00:01Z");

    private static SensorMetricBoundary heartRate() {
        return new SensorMetricBoundary(MetricType.HEART_RATE, 30.0, 240.0, false);
    }

    private static TelemetrySample sample(MetricType type, double value) {
        return new TelemetrySample(
                UUID.fromString("00000000-0000-0000-0000-000000000001"),
                "device-1", type, value, DEVICE_TS, INGRESS_TS, ValidationStatus.VALID);
    }

    @Test
    void accessors_afterConstruction_returnConfiguredValues() {
        SensorMetricBoundary boundary = new SensorMetricBoundary(MetricType.SWIM_PACE, 45.0, 600.0, true);

        assertThat(boundary.metricType()).isEqualTo(MetricType.SWIM_PACE);
        assertThat(boundary.min()).isEqualTo(45.0);
        assertThat(boundary.max()).isEqualTo(600.0);
        assertThat(boundary.minExclusive()).isTrue();
    }

    @ParameterizedTest
    @CsvSource({"30.0,true", "240.0,true", "120.0,true", "29.99,false", "240.01,false"})
    void isWithin_inclusiveBoundary_reflectsRange(double value, boolean expected) {
        assertThat(heartRate().isWithin(value)).isEqualTo(expected);
    }

    @ParameterizedTest
    @CsvSource({"45.0,false", "45.01,true", "100.0,true", "600.0,true", "600.01,false"})
    void isWithin_minExclusive_excludesMin(double value, boolean expected) {
        SensorMetricBoundary swimPace = new SensorMetricBoundary(MetricType.SWIM_PACE, 45.0, 600.0, true);

        assertThat(swimPace.isWithin(value)).isEqualTo(expected);
    }

    @Test
    void isWithin_nanValue_returnsFalse() {
        assertThat(heartRate().isWithin(Double.NaN)).isFalse();
    }

    @Test
    void validate_valueWithinRange_returnsSampleTaggedValid() {
        TelemetrySample input = sample(MetricType.HEART_RATE, 150.0).withStatus(ValidationStatus.VALIDATION_FAILED);

        TelemetrySample result = heartRate().validate(input);

        assertThat(result.validationStatus()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void validate_valueOutOfRange_returnsSampleTaggedFailedWithPayloadRetained() {
        TelemetrySample input = sample(MetricType.HEART_RATE, 300.0);

        TelemetrySample result = heartRate().validate(input);

        assertThat(result.validationStatus()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
        assertThat(result).usingRecursiveComparison().ignoringFields("validationStatus").isEqualTo(input);
    }

    @Test
    void validate_valueAtExcludedMin_returnsFailed() {
        SensorMetricBoundary swimPace = new SensorMetricBoundary(MetricType.SWIM_PACE, 45.0, 600.0, true);

        TelemetrySample result = swimPace.validate(sample(MetricType.SWIM_PACE, 45.0));

        assertThat(result.validationStatus()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void constructor_minGreaterThanMax_throwsIllegalArgument() {
        assertThatThrownBy(() -> new SensorMetricBoundary(MetricType.POWER, 2500.0, 0.0, false))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nanMin_throwsIllegalArgument() {
        assertThatThrownBy(() -> new SensorMetricBoundary(MetricType.POWER, Double.NaN, 2500.0, false))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nanMax_throwsIllegalArgument() {
        assertThatThrownBy(() -> new SensorMetricBoundary(MetricType.POWER, 0.0, Double.NaN, false))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
