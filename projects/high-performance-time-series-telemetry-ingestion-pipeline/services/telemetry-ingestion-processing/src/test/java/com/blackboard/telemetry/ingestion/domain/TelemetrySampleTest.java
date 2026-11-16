package com.blackboard.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetrySampleTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:01Z");

    private static MetricKind metric() {
        return MetricKind.values()[0];
    }

    private static TelemetrySample sample(ValidationStatus status) {
        return new TelemetrySample("dev-1", metric(), T_DEVICE, T_INGRESS, 42.5, status);
    }

    @Test
    void constructor_validArguments_exposesAllComponents() {
        TelemetrySample s = sample(ValidationStatus.UNVALIDATED);

        assertThat(s.deviceId()).isEqualTo("dev-1");
        assertThat(s.metric()).isEqualTo(metric());
        assertThat(s.tDevice()).isEqualTo(T_DEVICE);
        assertThat(s.tIngress()).isEqualTo(T_INGRESS);
        assertThat(s.value()).isEqualTo(42.5);
        assertThat(s.status()).isEqualTo(ValidationStatus.UNVALIDATED);
    }

    @Test
    void constructor_nullDeviceId_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySample(null, metric(), T_DEVICE, T_INGRESS, 1.0,
                ValidationStatus.UNVALIDATED)).isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullMetric_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySample("dev-1", null, T_DEVICE, T_INGRESS, 1.0,
                ValidationStatus.UNVALIDATED)).isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullTDevice_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySample("dev-1", metric(), null, T_INGRESS, 1.0,
                ValidationStatus.UNVALIDATED)).isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullTIngress_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySample("dev-1", metric(), T_DEVICE, null, 1.0,
                ValidationStatus.UNVALIDATED)).isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullStatus_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySample("dev-1", metric(), T_DEVICE, T_INGRESS, 1.0,
                null)).isInstanceOf(NullPointerException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankDeviceId_throwsIllegalArgumentException(String blank) {
        assertThatThrownBy(() -> new TelemetrySample(blank, metric(), T_DEVICE, T_INGRESS, 1.0,
                ValidationStatus.UNVALIDATED)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nanValue_keepsValueVerbatim() {
        TelemetrySample s = new TelemetrySample("dev-1", metric(), T_DEVICE, T_INGRESS,
                Double.NaN, ValidationStatus.UNVALIDATED);

        assertThat(s.value()).isNaN();
    }

    @Test
    void withStatus_newStatus_replacesOnlyStatus() {
        TelemetrySample original = sample(ValidationStatus.UNVALIDATED);

        TelemetrySample result = original.withStatus(ValidationStatus.VALID);

        assertThat(result).isEqualTo(sample(ValidationStatus.VALID));
        assertThat(original.status()).isEqualTo(ValidationStatus.UNVALIDATED);
    }

    @Test
    void withStatus_null_throwsNullPointerException() {
        TelemetrySample original = sample(ValidationStatus.UNVALIDATED);

        assertThatThrownBy(() -> original.withStatus(null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void equals_sameComponents_areEqual() {
        assertThat(sample(ValidationStatus.VALID)).isEqualTo(sample(ValidationStatus.VALID))
                .hasSameHashCodeAs(sample(ValidationStatus.VALID));
    }
}
