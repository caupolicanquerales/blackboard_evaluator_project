package com.pulsestream.telemetry.intake.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetrySampleTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T10:00:05Z");

    private static TelemetrySample sample(ValidationStatus status) {
        return new TelemetrySample("dev-1", "temp", 21.5, T_DEVICE, T_INGRESS, status);
    }

    @Test
    void constructor_validArguments_exposesComponents() {
        TelemetrySample s = sample(ValidationStatus.VALID);

        assertThat(s.deviceId()).isEqualTo("dev-1");
        assertThat(s.metric()).isEqualTo("temp");
        assertThat(s.value()).isEqualTo(21.5);
        assertThat(s.tDevice()).isEqualTo(T_DEVICE);
        assertThat(s.tIngress()).isEqualTo(T_INGRESS);
        assertThat(s.status()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void constructor_nullDeviceId_throws() {
        assertThatThrownBy(() -> new TelemetrySample(null, "temp", 1.0, T_DEVICE, T_INGRESS, ValidationStatus.VALID))
                .isInstanceOf(RuntimeException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankDeviceId_throws(String blank) {
        assertThatThrownBy(() -> new TelemetrySample(blank, "temp", 1.0, T_DEVICE, T_INGRESS, ValidationStatus.VALID))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullMetric_throws() {
        assertThatThrownBy(() -> new TelemetrySample("dev-1", null, 1.0, T_DEVICE, T_INGRESS, ValidationStatus.VALID))
                .isInstanceOf(RuntimeException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankMetric_throws(String blank) {
        assertThatThrownBy(() -> new TelemetrySample("dev-1", blank, 1.0, T_DEVICE, T_INGRESS, ValidationStatus.VALID))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullTDevice_throws() {
        assertThatThrownBy(() -> new TelemetrySample("dev-1", "temp", 1.0, null, T_INGRESS, ValidationStatus.VALID))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullTIngress_throws() {
        assertThatThrownBy(() -> new TelemetrySample("dev-1", "temp", 1.0, T_DEVICE, null, ValidationStatus.VALID))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullStatus_throws() {
        assertThatThrownBy(() -> new TelemetrySample("dev-1", "temp", 1.0, T_DEVICE, T_INGRESS, null))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void unvalidated_validArguments_setsUnvalidatedStatus() {
        TelemetrySample s = TelemetrySample.unvalidated("dev-1", "temp", 21.5, T_DEVICE, T_INGRESS);

        assertThat(s).isEqualTo(sample(ValidationStatus.UNVALIDATED));
        assertThat(s.status()).isEqualTo(ValidationStatus.UNVALIDATED);
    }

    @Test
    void unvalidated_blankDeviceId_throws() {
        assertThatThrownBy(() -> TelemetrySample.unvalidated(" ", "temp", 1.0, T_DEVICE, T_INGRESS))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @EnumSource(ValidationStatus.class)
    void withStatus_anyStatus_returnsCopyWithNewStatusOnly(ValidationStatus newStatus) {
        TelemetrySample original = sample(ValidationStatus.UNVALIDATED);

        TelemetrySample copy = original.withStatus(newStatus);

        assertThat(copy.status()).isEqualTo(newStatus);
        assertThat(copy).usingRecursiveComparison().ignoringFields("status")
                .isEqualTo(original);
    }

    @Test
    void withStatus_called_leavesOriginalUnchanged() {
        TelemetrySample original = sample(ValidationStatus.UNVALIDATED);

        TelemetrySample copy = original.withStatus(ValidationStatus.VALID);

        assertThat(copy).isNotSameAs(original);
        assertThat(original.status()).isEqualTo(ValidationStatus.UNVALIDATED);
    }

    @Test
    void withStatus_nullStatus_throws() {
        TelemetrySample original = sample(ValidationStatus.UNVALIDATED);

        assertThatThrownBy(() -> original.withStatus(null)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void equals_differentTIngressOnly_areNotEqualAsRecordsButKeepSameTDevice() {
        TelemetrySample a = sample(ValidationStatus.VALID);
        TelemetrySample b = new TelemetrySample("dev-1", "temp", 21.5, T_DEVICE, T_INGRESS.plusSeconds(60),
                ValidationStatus.VALID);

        assertThat(b.tDevice()).isEqualTo(a.tDevice());
        assertThat(b.tIngress()).isNotEqualTo(a.tIngress());
    }
}
