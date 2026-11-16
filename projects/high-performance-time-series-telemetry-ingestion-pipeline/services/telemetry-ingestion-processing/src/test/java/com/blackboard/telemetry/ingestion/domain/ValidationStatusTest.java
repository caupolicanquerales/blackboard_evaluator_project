package com.blackboard.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class ValidationStatusTest {

    @Test
    void values_called_returnsExactConstantsInOrder() {
        ValidationStatus[] result = ValidationStatus.values();

        assertThat(result).containsExactly(
                ValidationStatus.UNVALIDATED,
                ValidationStatus.VALID,
                ValidationStatus.VALIDATION_FAILED);
    }

    @ParameterizedTest
    @EnumSource(ValidationStatus.class)
    void valueOf_constantName_returnsSameConstant(ValidationStatus status) {
        ValidationStatus result = ValidationStatus.valueOf(status.name());

        assertThat(result).isSameAs(status);
    }

    @Test
    void valueOf_unknownName_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> ValidationStatus.valueOf("DROPPED"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void valueOf_nullName_throwsNullPointerException() {
        assertThatThrownBy(() -> ValidationStatus.valueOf(null))
                .isInstanceOf(NullPointerException.class);
    }
}
