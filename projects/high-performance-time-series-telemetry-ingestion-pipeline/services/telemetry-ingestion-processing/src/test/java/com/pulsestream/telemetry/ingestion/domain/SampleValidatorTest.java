package com.pulsestream.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class SampleValidatorTest {

    private final TelemetryProperties properties = new TelemetryProperties(
            60L, 16, Map.of("temp", new TelemetryProperties.Bounds(-10.0, 50.0)));
    private final SampleValidator validator = new SampleValidator(properties);

    private TelemetrySample sample(String metric, double value) {
        return new TelemetrySample("d1", metric, 1000L, value, 1001L, null);
    }

    @ParameterizedTest
    @ValueSource(doubles = {-10.0, 0.0, 50.0})
    void validate_valueWithinInclusiveBounds_returnsValid(double value) {
        TelemetrySample result = validator.validate(sample("temp", value));

        assertThat(result.validationStatus()).isEqualTo(TelemetrySample.VALID);
    }

    @ParameterizedTest
    @ValueSource(doubles = {-10.001, 50.001, 1000.0})
    void validate_valueOutOfRange_returnsValidationFailed(double value) {
        TelemetrySample result = validator.validate(sample("temp", value));

        assertThat(result.validationStatus()).isEqualTo(TelemetrySample.VALIDATION_FAILED);
        assertThat(result.isValidationFailed()).isTrue();
    }

    @Test
    void validate_unknownMetric_returnsValidationFailed() {
        TelemetrySample result = validator.validate(sample("humidity", 10.0));

        assertThat(result.validationStatus()).isEqualTo(TelemetrySample.VALIDATION_FAILED);
    }

    @Test
    void validate_failedSample_preservesOtherFields() {
        TelemetrySample input = sample("temp", 999.0);

        TelemetrySample result = validator.validate(input);

        assertThat(result).usingRecursiveComparison()
                .ignoringFields("validationStatus").isEqualTo(input);
    }

    @Test
    void validate_sameInputTwice_isDeterministic() {
        TelemetrySample input = sample("temp", 25.0);

        assertThat(validator.validate(input)).isEqualTo(validator.validate(input));
    }
}
