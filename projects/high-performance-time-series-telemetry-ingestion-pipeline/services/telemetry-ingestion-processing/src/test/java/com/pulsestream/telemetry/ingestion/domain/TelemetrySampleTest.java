package com.pulsestream.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetrySampleTest {

    private TelemetrySample sample(String status) {
        return new TelemetrySample("dev-1", "temp", 1000L, 21.5, 2000L, status);
    }

    @Test
    void accessors_returnConstructorValues() {
        TelemetrySample s = sample(TelemetrySample.VALID);

        assertThat(s.deviceId()).isEqualTo("dev-1");
        assertThat(s.metric()).isEqualTo("temp");
        assertThat(s.tDeviceEpochMs()).isEqualTo(1000L);
        assertThat(s.value()).isEqualTo(21.5);
        assertThat(s.tIngressEpochMs()).isEqualTo(2000L);
        assertThat(s.validationStatus()).isEqualTo(TelemetrySample.VALID);
    }

    @Test
    void constants_areDistinctAndNotBlank() {
        assertThat(TelemetrySample.VALID).isNotBlank();
        assertThat(TelemetrySample.VALIDATION_FAILED).isNotBlank().isNotEqualTo(TelemetrySample.VALID);
    }

    @Test
    void isValidationFailed_validationFailedStatus_returnsTrue() {
        assertThat(sample(TelemetrySample.VALIDATION_FAILED).isValidationFailed()).isTrue();
    }

    @Test
    void isValidationFailed_validStatus_returnsFalse() {
        assertThat(sample(TelemetrySample.VALID).isValidationFailed()).isFalse();
    }

    @Test
    void withStatus_returnsCopyChangingOnlyStatus() {
        TelemetrySample original = sample(TelemetrySample.VALID);

        TelemetrySample copy = original.withStatus(TelemetrySample.VALIDATION_FAILED);

        assertThat(copy.validationStatus()).isEqualTo(TelemetrySample.VALIDATION_FAILED);
        assertThat(copy).usingRecursiveComparison().ignoringFields("validationStatus").isEqualTo(original);
    }

    @Test
    void withStatus_leavesOriginalUnchanged() {
        TelemetrySample original = sample(TelemetrySample.VALID);

        original.withStatus(TelemetrySample.VALIDATION_FAILED);

        assertThat(original.validationStatus()).isEqualTo(TelemetrySample.VALID);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "  "})
    void constructor_blankDeviceId_throwsIllegalArgument(String blank) {
        assertThatThrownBy(() -> new TelemetrySample(blank, "temp", 1L, 1.0, 2L, TelemetrySample.VALID))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "  "})
    void constructor_blankMetric_throwsIllegalArgument(String blank) {
        assertThatThrownBy(() -> new TelemetrySample("dev-1", blank, 1L, 1.0, 2L, TelemetrySample.VALID))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullStatus_throwsIllegalArgument() {
        assertThatThrownBy(() -> sample(null)).isInstanceOf(IllegalArgumentException.class);
    }
}
