package com.blackboard.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.ValueSource;

class ValidatedSampleEventTest {

    private static TelemetrySample sample(ValidationStatus status) {
        return new TelemetrySample("dev-1", MetricKind.values()[0],
                Instant.parse("2024-01-01T00:00:00Z"), Instant.parse("2024-01-01T00:00:01Z"),
                10.0, status);
    }

    @ParameterizedTest
    @EnumSource(value = ValidationStatus.class, names = {"VALID", "VALIDATION_FAILED"})
    void constructor_validatedStatus_exposesSampleAndCorrelationId(ValidationStatus status) {
        TelemetrySample s = sample(status);

        ValidatedSampleEvent event = new ValidatedSampleEvent(s, "req-1");

        assertThat(event.sample()).isEqualTo(s);
        assertThat(event.correlationId()).isEqualTo("req-1");
    }

    @Test
    void constructor_unvalidatedSample_throwsIllegalArgumentException() {
        TelemetrySample s = sample(ValidationStatus.UNVALIDATED);

        assertThatThrownBy(() -> new ValidatedSampleEvent(s, "req-1"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullSample_throwsNullPointerException() {
        assertThatThrownBy(() -> new ValidatedSampleEvent(null, "req-1"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullCorrelationId_throwsNullPointerException() {
        TelemetrySample s = sample(ValidationStatus.VALID);

        assertThatThrownBy(() -> new ValidatedSampleEvent(s, null))
                .isInstanceOf(NullPointerException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankCorrelationId_throwsIllegalArgumentException(String blank) {
        TelemetrySample s = sample(ValidationStatus.VALID);

        assertThatThrownBy(() -> new ValidatedSampleEvent(s, blank))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
