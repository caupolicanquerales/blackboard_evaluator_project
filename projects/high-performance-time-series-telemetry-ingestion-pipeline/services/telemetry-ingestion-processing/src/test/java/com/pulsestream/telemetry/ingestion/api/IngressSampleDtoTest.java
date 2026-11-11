package com.pulsestream.telemetry.ingestion.api;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class IngressSampleDtoTest {

    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    @Test
    void toDomain_validDto_mapsFieldsWithIngressTimeAndValidStatus() {
        IngressSampleDto dto = new IngressSampleDto("dev-1", "temp", 1_000L, 21.5);

        TelemetrySample sample = dto.toDomain(2_000L);

        assertThat(sample).isEqualTo(new TelemetrySample("dev-1", "temp", 1_000L, 21.5, 2_000L, TelemetrySample.VALID));
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "  "})
    void validate_blankDeviceId_hasViolation(String blank) {
        assertThat(validator.validate(new IngressSampleDto(blank, "temp", 1L, 1.0))).hasSize(1);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "  "})
    void validate_blankMetric_hasViolation(String blank) {
        assertThat(validator.validate(new IngressSampleDto("dev-1", blank, 1L, 1.0))).hasSize(1);
    }

    @Test
    void validate_validDto_hasNoViolations() {
        assertThat(validator.validate(new IngressSampleDto("dev-1", "temp", 1L, 1.0))).isEmpty();
    }
}
