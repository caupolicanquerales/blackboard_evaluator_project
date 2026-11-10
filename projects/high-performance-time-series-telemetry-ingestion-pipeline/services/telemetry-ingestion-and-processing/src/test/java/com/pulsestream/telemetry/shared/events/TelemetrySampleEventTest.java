package com.pulsestream.telemetry.shared.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNoException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetrySampleEventTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:05Z");

    private static TelemetrySampleEvent event(String deviceId, String metric, Instant tDevice,
            Instant tIngress, String status) {
        return new TelemetrySampleEvent(deviceId, metric, 21.5, tDevice, tIngress, status);
    }

    @Test
    void constants_values_matchContract() {
        assertThat(TelemetrySampleEvent.VALID).isEqualTo("VALID");
        assertThat(TelemetrySampleEvent.VALIDATION_FAILED).isEqualTo("VALIDATION_FAILED");
    }

    @Test
    void constructor_validArguments_exposesComponents() {
        TelemetrySampleEvent e = event("dev-1", "temp", T_DEVICE, T_INGRESS, TelemetrySampleEvent.VALID);

        assertThat(e.deviceId()).isEqualTo("dev-1");
        assertThat(e.metric()).isEqualTo("temp");
        assertThat(e.value()).isEqualTo(21.5);
        assertThat(e.tDevice()).isEqualTo(T_DEVICE);
        assertThat(e.tIngress()).isEqualTo(T_INGRESS);
        assertThat(e.validationStatus()).isEqualTo("VALID");
    }

    @Test
    void constructor_equalComponents_areEqual() {
        TelemetrySampleEvent a = event("dev-1", "temp", T_DEVICE, T_INGRESS, TelemetrySampleEvent.VALID);
        TelemetrySampleEvent b = event("dev-1", "temp", T_DEVICE, T_INGRESS, TelemetrySampleEvent.VALID);

        assertThat(a).isEqualTo(b).hasSameHashCodeAs(b);
    }

    @Test
    void constructor_nullDeviceId_throws() {
        assertThatThrownBy(() -> event(null, "temp", T_DEVICE, T_INGRESS, TelemetrySampleEvent.VALID))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankDeviceId_throws(String blank) {
        assertThatThrownBy(() -> event(blank, "temp", T_DEVICE, T_INGRESS, TelemetrySampleEvent.VALID))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @Test
    void constructor_nullMetric_throws() {
        assertThatThrownBy(() -> event("dev-1", null, T_DEVICE, T_INGRESS, TelemetrySampleEvent.VALID))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankMetric_throws(String blank) {
        assertThatThrownBy(() -> event("dev-1", blank, T_DEVICE, T_INGRESS, TelemetrySampleEvent.VALID))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @Test
    void constructor_nullTDevice_throws() {
        assertThatThrownBy(() -> event("dev-1", "temp", null, T_INGRESS, TelemetrySampleEvent.VALID))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @Test
    void constructor_nullTIngress_throws() {
        assertThatThrownBy(() -> event("dev-1", "temp", T_DEVICE, null, TelemetrySampleEvent.VALID))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @Test
    void constructor_nullValidationStatus_throws() {
        assertThatThrownBy(() -> event("dev-1", "temp", T_DEVICE, T_INGRESS, null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "valid", "UNKNOWN", "validation_failed"})
    void constructor_unknownValidationStatus_throws(String status) {
        assertThatThrownBy(() -> event("dev-1", "temp", T_DEVICE, T_INGRESS, status))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @Test
    void constructor_validationFailedStatus_isAccepted() {
        assertThatNoException().isThrownBy(
                () -> event("dev-1", "temp", T_DEVICE, T_INGRESS, TelemetrySampleEvent.VALIDATION_FAILED));
    }

    @Test
    void isValidationFailed_validStatus_returnsFalse() {
        TelemetrySampleEvent e = event("dev-1", "temp", T_DEVICE, T_INGRESS, TelemetrySampleEvent.VALID);

        assertThat(e.isValidationFailed()).isFalse();
    }

    @Test
    void isValidationFailed_failedStatus_returnsTrue() {
        TelemetrySampleEvent e = event("dev-1", "temp", T_DEVICE, T_INGRESS,
                TelemetrySampleEvent.VALIDATION_FAILED);

        assertThat(e.isValidationFailed()).isTrue();
    }

    @Test
    void tDevice_earlierDeviceTimeLaterIngress_keepsDeviceTimeAsOrderingKey() {
        TelemetrySampleEvent early = event("dev-1", "temp", T_DEVICE, T_INGRESS.plusSeconds(60),
                TelemetrySampleEvent.VALID);
        TelemetrySampleEvent late = event("dev-1", "temp", T_DEVICE.plusSeconds(10), T_INGRESS,
                TelemetrySampleEvent.VALID);

        assertThat(early.tDevice()).isBefore(late.tDevice());
        assertThat(early.tIngress()).isAfter(late.tIngress());
    }
}
