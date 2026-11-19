package com.pulsestream.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class ValidationStatusTest {

    @Test
    void values_called_containsValidatedAndValidationFailed() {
        assertThat(ValidationStatus.values())
                .contains(ValidationStatus.VALIDATED, ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void valueOf_validatedName_roundTrips() {
        assertThat(ValidationStatus.valueOf("VALIDATED")).isEqualTo(ValidationStatus.VALIDATED);
    }

    @Test
    void valueOf_validationFailedName_roundTrips() {
        assertThat(ValidationStatus.valueOf("VALIDATION_FAILED")).isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void valueOf_unknownName_throwsIllegalArgument() {
        assertThatThrownBy(() -> ValidationStatus.valueOf("NOPE")).isInstanceOf(IllegalArgumentException.class);
    }
}
