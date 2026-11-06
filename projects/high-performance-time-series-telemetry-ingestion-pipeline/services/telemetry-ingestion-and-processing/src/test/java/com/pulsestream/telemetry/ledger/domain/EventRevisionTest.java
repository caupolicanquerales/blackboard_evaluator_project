package com.pulsestream.telemetry.ledger.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNoException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class EventRevisionTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:01Z");

    private static EventRevision revision(int revision) {
        return new EventRevision("device-1", "temperature", T_DEVICE, revision, T_INGRESS, "VALID", "{\"v\":1}");
    }

    @Test
    void constructor_validArguments_exposesValues() {
        EventRevision event = revision(1);

        assertThat(event.deviceId()).isEqualTo("device-1");
        assertThat(event.metric()).isEqualTo("temperature");
        assertThat(event.tDevice()).isEqualTo(T_DEVICE);
        assertThat(event.revision()).isEqualTo(1);
        assertThat(event.tIngress()).isEqualTo(T_INGRESS);
        assertThat(event.validationStatus()).isEqualTo("VALID");
        assertThat(event.rawPayload()).isEqualTo("{\"v\":1}");
    }

    @Test
    void constructor_revisionOne_isAccepted() {
        assertThatNoException().isThrownBy(() -> revision(1));
    }

    @ParameterizedTest
    @ValueSource(ints = {0, -1, -100})
    void constructor_revisionBelowOne_throwsIllegalArgument(int invalid) {
        assertThatThrownBy(() -> revision(invalid)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void nextRevision_fromRevision_returnsNewInstanceWithIncrementedRevision() {
        EventRevision original = revision(1);

        EventRevision next = original.nextRevision();

        assertThat(next).isNotSameAs(original);
        assertThat(next.revision()).isEqualTo(2);
    }

    @Test
    void nextRevision_fromRevision_doesNotMutateOriginal() {
        EventRevision original = revision(3);

        original.nextRevision();

        assertThat(original.revision()).isEqualTo(3);
    }

    @Test
    void nextRevision_fromRevision_keepsOtherFields() {
        EventRevision original = revision(1);

        EventRevision next = original.nextRevision();

        assertThat(next).usingRecursiveComparison().ignoringFields("revision").isEqualTo(original);
    }

    @Test
    void constructor_nullDeviceId_throwsNullPointer() {
        assertThatThrownBy(() -> new EventRevision(null, "m", T_DEVICE, 1, T_INGRESS, "VALID", "p"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullMetric_throwsNullPointer() {
        assertThatThrownBy(() -> new EventRevision("d", null, T_DEVICE, 1, T_INGRESS, "VALID", "p"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullTDevice_throwsNullPointer() {
        assertThatThrownBy(() -> new EventRevision("d", "m", null, 1, T_INGRESS, "VALID", "p"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullTIngress_throwsNullPointer() {
        assertThatThrownBy(() -> new EventRevision("d", "m", T_DEVICE, 1, null, "VALID", "p"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullValidationStatus_throwsNullPointer() {
        assertThatThrownBy(() -> new EventRevision("d", "m", T_DEVICE, 1, T_INGRESS, null, "p"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullRawPayload_throwsNullPointer() {
        assertThatThrownBy(() -> new EventRevision("d", "m", T_DEVICE, 1, T_INGRESS, "VALID", null))
                .isInstanceOf(NullPointerException.class);
    }
}
