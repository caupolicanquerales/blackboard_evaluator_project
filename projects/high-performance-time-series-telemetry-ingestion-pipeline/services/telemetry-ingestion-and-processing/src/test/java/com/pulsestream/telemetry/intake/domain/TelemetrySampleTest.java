package com.pulsestream.telemetry.intake.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNoException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetrySampleTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T10:00:05Z");

    private static TelemetrySample sample(String deviceId, String metric, Instant tDevice, Instant tIngress) {
        return new TelemetrySample(deviceId, metric, 21.5, tDevice, tIngress);
    }

    @Test
    void constructor_validArguments_exposesAllComponents() {
        TelemetrySample s = sample("dev-1", "temperature", T_DEVICE, T_INGRESS);

        assertThat(s.deviceId()).isEqualTo("dev-1");
        assertThat(s.metric()).isEqualTo("temperature");
        assertThat(s.value()).isEqualTo(21.5);
        assertThat(s.tDevice()).isEqualTo(T_DEVICE);
        assertThat(s.tIngress()).isEqualTo(T_INGRESS);
    }

    @Test
    void constructor_nullDeviceId_throws() {
        assertThatThrownBy(() -> sample(null, "temperature", T_DEVICE, T_INGRESS))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankDeviceId_throws(String blank) {
        assertThatThrownBy(() -> sample(blank, "temperature", T_DEVICE, T_INGRESS))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullMetric_throws() {
        assertThatThrownBy(() -> sample("dev-1", null, T_DEVICE, T_INGRESS))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankMetric_throws(String blank) {
        assertThatThrownBy(() -> sample("dev-1", blank, T_DEVICE, T_INGRESS))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullTDevice_throws() {
        assertThatThrownBy(() -> sample("dev-1", "temperature", null, T_INGRESS))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullTIngress_throws() {
        assertThatThrownBy(() -> sample("dev-1", "temperature", T_DEVICE, null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void equals_sameComponents_areEqualWithSameHashCode() {
        TelemetrySample a = sample("dev-1", "temperature", T_DEVICE, T_INGRESS);
        TelemetrySample b = sample("dev-1", "temperature", T_DEVICE, T_INGRESS);

        assertThat(a).isEqualTo(b).hasSameHashCodeAs(b);
    }

    @Test
    void equals_differentTIngress_areNotEqual() {
        TelemetrySample a = sample("dev-1", "temperature", T_DEVICE, T_INGRESS);
        TelemetrySample b = sample("dev-1", "temperature", T_DEVICE, T_INGRESS.plusSeconds(1));

        assertThat(a).isNotEqualTo(b);
    }

    @Test
    void accessors_distinctTimestamps_tIngressDoesNotOverwriteTDevice() {
        TelemetrySample s = sample("dev-1", "temperature", T_DEVICE, T_INGRESS);

        assertThat(s.tDevice()).isNotEqualTo(s.tIngress()).isEqualTo(T_DEVICE);
    }

    @Test
    void constructor_equalTimestamps_keepsBothValues() {
        assertThatNoException().isThrownBy(() -> {
            TelemetrySample s = sample("dev-1", "temperature", T_DEVICE, T_DEVICE);
            assertThat(s.tDevice()).isEqualTo(T_DEVICE);
            assertThat(s.tIngress()).isEqualTo(T_DEVICE);
        });
    }
}
