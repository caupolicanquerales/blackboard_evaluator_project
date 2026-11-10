package com.pulsestream.telemetry.shared.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNoException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetryRevisionAppendedEventTest {

    private static final UUID RECORD_ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");

    @Test
    void constructor_validArguments_exposesComponents() {
        TelemetryRevisionAppendedEvent event =
                new TelemetryRevisionAppendedEvent(RECORD_ID, "device-1", "temperature", T_DEVICE, 1);

        assertThat(event.recordId()).isEqualTo(RECORD_ID);
        assertThat(event.deviceId()).isEqualTo("device-1");
        assertThat(event.metric()).isEqualTo("temperature");
        assertThat(event.tDevice()).isEqualTo(T_DEVICE);
        assertThat(event.revision()).isEqualTo(1);
    }

    @Test
    void constructor_equalComponents_areEqual() {
        TelemetryRevisionAppendedEvent a =
                new TelemetryRevisionAppendedEvent(RECORD_ID, "device-1", "temperature", T_DEVICE, 2);
        TelemetryRevisionAppendedEvent b =
                new TelemetryRevisionAppendedEvent(RECORD_ID, "device-1", "temperature", T_DEVICE, 2);

        assertThat(a).isEqualTo(b).hasSameHashCodeAs(b);
    }

    @Test
    void constructor_largeRevision_isAccepted() {
        assertThatNoException().isThrownBy(() -> new TelemetryRevisionAppendedEvent(
                RECORD_ID, "device-1", "temperature", T_DEVICE, Integer.MAX_VALUE));
    }

    @ParameterizedTest
    @ValueSource(ints = {0, -1, Integer.MIN_VALUE})
    void constructor_revisionBelowOne_throws(int revision) {
        assertThatThrownBy(() -> new TelemetryRevisionAppendedEvent(
                RECORD_ID, "device-1", "temperature", T_DEVICE, revision))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullRecordId_throws() {
        assertThatThrownBy(() -> new TelemetryRevisionAppendedEvent(
                null, "device-1", "temperature", T_DEVICE, 1))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullDeviceId_throws() {
        assertThatThrownBy(() -> new TelemetryRevisionAppendedEvent(
                RECORD_ID, null, "temperature", T_DEVICE, 1))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullMetric_throws() {
        assertThatThrownBy(() -> new TelemetryRevisionAppendedEvent(
                RECORD_ID, "device-1", null, T_DEVICE, 1))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullTDevice_throws() {
        assertThatThrownBy(() -> new TelemetryRevisionAppendedEvent(
                RECORD_ID, "device-1", "temperature", null, 1))
                .isInstanceOf(RuntimeException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankDeviceId_throws(String deviceId) {
        assertThatThrownBy(() -> new TelemetryRevisionAppendedEvent(
                RECORD_ID, deviceId, "temperature", T_DEVICE, 1))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankMetric_throws(String metric) {
        assertThatThrownBy(() -> new TelemetryRevisionAppendedEvent(
                RECORD_ID, "device-1", metric, T_DEVICE, 1))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
