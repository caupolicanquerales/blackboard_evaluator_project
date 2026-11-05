package com.blackboard.telemetry.eventlog.domain;
import com.blackboard.telemetry.shared.events.TelemetryEvents;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.time.Instant;
import java.util.Arrays;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;

class EventRevisionTest {

    private static final String DEVICE = "device-1";
    private static final Instant T_DEVICE = Instant.parse("2026-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2026-01-01T10:00:05Z");
    private static final Instant T_INGRESS_LATER = Instant.parse("2026-01-01T10:05:00Z");
    private static final String PAYLOAD = "heart_rate=150.0";
    private static final String CORRECTED_PAYLOAD = "heart_rate=151.0";

    private static EventRevision initial() {
        return EventRevision.first(DEVICE, T_DEVICE, T_INGRESS, ValidationStatus.VALID, PAYLOAD);
    }

    private static EventRevision corrected(EventRevision previous) {
        return previous.nextRevision(T_INGRESS_LATER, ValidationStatus.VALID, CORRECTED_PAYLOAD);
    }

    @Test
    void first_validArguments_isRevisionZero() {
        assertThat(initial().revision()).isEqualTo(0);
    }

    @Test
    void first_validArguments_isKeyedByDeviceIdAndTDevice() {
        EventRevision record = initial();

        assertThat(record.deviceId()).isEqualTo(DEVICE);
        assertThat(record.tDevice()).isEqualTo(T_DEVICE);
    }

    @Test
    void first_validArguments_keepsIngressTimeStatusAndPayload() {
        EventRevision record = initial();

        assertThat(record.tIngress()).isEqualTo(T_INGRESS);
        assertThat(record.validationStatus()).isEqualTo(ValidationStatus.VALID);
        assertThat(record.payload()).isEqualTo(PAYLOAD);
    }

    @Test
    void first_validationFailedStatus_isStoredAsRawRecord() {
        EventRevision record = EventRevision.first(DEVICE, T_DEVICE, T_INGRESS,
                ValidationStatus.VALIDATION_FAILED, "heart_rate=400.0");

        assertThat(record.validationStatus()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
        assertThat(record.revision()).isEqualTo(0);
    }

    @Test
    void nextRevision_fromInitial_yieldsRevisionOne() {
        assertThat(corrected(initial()).revision()).isEqualTo(1);
    }

    @Test
    void nextRevision_fromInitial_keepsOriginalKey() {
        EventRevision next = corrected(initial());

        assertThat(next.deviceId()).isEqualTo(DEVICE);
        assertThat(next.tDevice()).isEqualTo(T_DEVICE);
    }

    @Test
    void nextRevision_withCorrection_carriesNewIngressStatusAndPayload() {
        EventRevision next = initial().nextRevision(T_INGRESS_LATER, ValidationStatus.VALIDATION_FAILED,
                CORRECTED_PAYLOAD);

        assertThat(next.tIngress()).isEqualTo(T_INGRESS_LATER);
        assertThat(next.validationStatus()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
        assertThat(next.payload()).isEqualTo(CORRECTED_PAYLOAD);
    }

    @Test
    void nextRevision_called_leavesOriginalUnchanged() {
        EventRevision original = initial();

        corrected(original);

        assertThat(original).isEqualTo(initial());
        assertThat(original.revision()).isEqualTo(0);
        assertThat(original.payload()).isEqualTo(PAYLOAD);
    }

    @Test
    void nextRevision_called_returnsDistinctInstance() {
        EventRevision original = initial();

        assertThat(corrected(original)).isNotSameAs(original).isNotEqualTo(original);
    }

    @Test
    void nextRevision_chained_revisionsStrictlyIncrease() {
        EventRevision r0 = initial();
        EventRevision r1 = corrected(r0);
        EventRevision r2 = corrected(r1);
        EventRevision r3 = corrected(r2);

        assertThat(new int[] { r0.revision(), r1.revision(), r2.revision(), r3.revision() })
                .containsExactly(0, 1, 2, 3);
    }

    @Test
    void nextRevision_calledTwiceOnSameRevision_isDeterministic() {
        EventRevision r0 = initial();

        assertThat(corrected(r0)).isEqualTo(corrected(r0));
    }

    @Test
    void nextRevision_nullPayload_isRejected() {
        assertThatThrownBy(() -> initial().nextRevision(T_INGRESS_LATER, ValidationStatus.VALID, null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void nextRevision_nullIngressTime_isRejected() {
        assertThatThrownBy(() -> initial().nextRevision(null, ValidationStatus.VALID, CORRECTED_PAYLOAD))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void eventRevision_publicApi_exposesNoSetters() {
        boolean hasSetter = Arrays.stream(EventRevision.class.getMethods())
                .map(Method::getName)
                .anyMatch(name -> name.startsWith("set"));

        assertThat(hasSetter).isFalse();
    }

    @Test
    void eventRevision_publicApi_hasNoVoidMutators() {
        boolean voidMutators = Arrays.stream(EventRevision.class.getDeclaredMethods())
                .filter(m -> Modifier.isPublic(m.getModifiers()))
                .filter(m -> !Modifier.isStatic(m.getModifiers()))
                .anyMatch(m -> m.getReturnType() == void.class);

        assertThat(voidMutators).isFalse();
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = { " ", "   ", "\t" })
    void first_nullOrBlankDeviceId_isRejected(String deviceId) {
        assertThatThrownBy(() -> EventRevision.first(deviceId, T_DEVICE, T_INGRESS, ValidationStatus.VALID, PAYLOAD))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void first_nullTDevice_isRejected() {
        assertThatThrownBy(() -> EventRevision.first(DEVICE, null, T_INGRESS, ValidationStatus.VALID, PAYLOAD))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void first_nullTIngress_isRejected() {
        assertThatThrownBy(() -> EventRevision.first(DEVICE, T_DEVICE, null, ValidationStatus.VALID, PAYLOAD))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void first_nullValidationStatus_isRejected() {
        assertThatThrownBy(() -> EventRevision.first(DEVICE, T_DEVICE, T_INGRESS, null, PAYLOAD))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void first_nullPayload_isRejected() {
        assertThatThrownBy(() -> EventRevision.first(DEVICE, T_DEVICE, T_INGRESS, ValidationStatus.VALID, null))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
