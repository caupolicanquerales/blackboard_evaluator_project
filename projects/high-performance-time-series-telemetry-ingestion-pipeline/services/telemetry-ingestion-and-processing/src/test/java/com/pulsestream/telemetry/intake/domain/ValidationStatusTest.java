package com.pulsestream.telemetry.intake.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.EnumSet;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class ValidationStatusTest {

    @Test
    void values_declared_containsExactlyThreeStatesInOrder() {
        assertThat(ValidationStatus.values())
                .containsExactly(
                        ValidationStatus.UNVALIDATED,
                        ValidationStatus.VALID,
                        ValidationStatus.VALIDATION_FAILED);
    }

    @ParameterizedTest
    @EnumSource(ValidationStatus.class)
    void valueOf_eachName_returnsSameConstant(ValidationStatus status) {
        assertThat(ValidationStatus.valueOf(status.name())).isSameAs(status);
    }

    @Test
    void postValidationStates_excludingUnvalidated_areExactlyValidAndValidationFailed() {
        Set<ValidationStatus> postValidation = EnumSet.complementOf(EnumSet.of(ValidationStatus.UNVALIDATED));

        assertThat(postValidation)
                .containsExactlyInAnyOrder(ValidationStatus.VALID, ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void names_allStates_areDistinctAndNoDroppedState() {
        assertThat(Arrays.stream(ValidationStatus.values()).map(Enum::name))
                .containsExactly("UNVALIDATED", "VALID", "VALIDATION_FAILED")
                .doesNotHaveDuplicates();
    }
}
