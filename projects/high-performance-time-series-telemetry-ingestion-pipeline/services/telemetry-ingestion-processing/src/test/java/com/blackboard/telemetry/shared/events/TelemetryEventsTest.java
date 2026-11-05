package com.blackboard.telemetry.shared.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.stream.Stream;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;

import com.blackboard.telemetry.shared.events.TelemetryEvents.BackfilledSampleReindexed;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetryRevisionAppended;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleOrdered;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidated;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidationFailed;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetryWindowBuffered;
import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;

class TelemetryEventsTest {

    private static final String DEVICE = "device-1";
    private static final Instant T_DEVICE = Instant.parse("2026-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2026-01-01T10:00:05Z");
    private static final String METRIC = "heart_rate";
    private static final double VALUE = 150.0;

    @FunctionalInterface
    interface EventFactory {
        Object create(String deviceId, Instant tDevice, Instant tIngress);
    }

    private static Arguments factory(String name, EventFactory factory) {
        return Arguments.of(name, factory);
    }

    static Stream<Arguments> factories() {
        return Stream.of(
                factory("TelemetrySampleValidated", (d, td, ti) -> new TelemetrySampleValidated(d, td, ti, METRIC,
                        VALUE, ValidationStatus.VALID)),
                factory("TelemetrySampleValidationFailed", (d, td, ti) -> new TelemetrySampleValidationFailed(d, td,
                        ti, METRIC, VALUE, ValidationStatus.VALIDATION_FAILED)),
                factory("TelemetrySampleOrdered", (d, td, ti) -> new TelemetrySampleOrdered(d, td, ti, METRIC, VALUE,
                        ValidationStatus.VALID)),
                factory("BackfilledSampleReindexed", (d, td, ti) -> new BackfilledSampleReindexed(d, td, ti, METRIC,
                        VALUE, ValidationStatus.VALID)),
                factory("TelemetryWindowBuffered", (d, td, ti) -> new TelemetryWindowBuffered(d, td, ti, METRIC,
                        VALUE, ValidationStatus.VALID)),
                factory("TelemetryRevisionAppended", (d, td, ti) -> new TelemetryRevisionAppended(d, td, ti, METRIC,
                        VALUE, ValidationStatus.VALID)));
    }

    @Test
    void validated_withValidArguments_carriesAllFields() {
        TelemetrySampleValidated event = new TelemetrySampleValidated(DEVICE, T_DEVICE, T_INGRESS, METRIC, VALUE,
                ValidationStatus.VALID);

        assertThat(event.deviceId()).isEqualTo(DEVICE);
        assertThat(event.tDevice()).isEqualTo(T_DEVICE);
        assertThat(event.tIngress()).isEqualTo(T_INGRESS);
        assertThat(event.metric()).isEqualTo(METRIC);
        assertThat(event.value()).isEqualTo(VALUE);
        assertThat(event.status()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void validationFailed_withValidArguments_retainsPayloadAndFailedStatus() {
        TelemetrySampleValidationFailed event = new TelemetrySampleValidationFailed(DEVICE, T_DEVICE, T_INGRESS,
                METRIC, 400.0, ValidationStatus.VALIDATION_FAILED);

        assertThat(event.deviceId()).isEqualTo(DEVICE);
        assertThat(event.tDevice()).isEqualTo(T_DEVICE);
        assertThat(event.tIngress()).isEqualTo(T_INGRESS);
        assertThat(event.metric()).isEqualTo(METRIC);
        assertThat(event.value()).isEqualTo(400.0);
        assertThat(event.status()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void validationFailed_withNonFailedStatus_isRejected() {
        assertThatThrownBy(() -> new TelemetrySampleValidationFailed(DEVICE, T_DEVICE, T_INGRESS, METRIC, 400.0,
                ValidationStatus.VALID)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void validationFailed_withNullStatus_isRejected() {
        assertThatThrownBy(() -> new TelemetrySampleValidationFailed(DEVICE, T_DEVICE, T_INGRESS, METRIC, 400.0,
                null)).isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @Test
    void ordered_withValidArguments_carriesAllFields() {
        TelemetrySampleOrdered event = new TelemetrySampleOrdered(DEVICE, T_DEVICE, T_INGRESS, METRIC, VALUE,
                ValidationStatus.VALID);

        assertThat(event.deviceId()).isEqualTo(DEVICE);
        assertThat(event.tDevice()).isEqualTo(T_DEVICE);
        assertThat(event.tIngress()).isEqualTo(T_INGRESS);
        assertThat(event.metric()).isEqualTo(METRIC);
        assertThat(event.value()).isEqualTo(VALUE);
        assertThat(event.status()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void reindexed_withValidArguments_carriesAllFields() {
        BackfilledSampleReindexed event = new BackfilledSampleReindexed(DEVICE, T_DEVICE, T_INGRESS, METRIC, VALUE,
                ValidationStatus.VALID);

        assertThat(event.deviceId()).isEqualTo(DEVICE);
        assertThat(event.tDevice()).isEqualTo(T_DEVICE);
        assertThat(event.tIngress()).isEqualTo(T_INGRESS);
        assertThat(event.metric()).isEqualTo(METRIC);
        assertThat(event.value()).isEqualTo(VALUE);
        assertThat(event.status()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void windowBuffered_withValidArguments_carriesAllFields() {
        TelemetryWindowBuffered event = new TelemetryWindowBuffered(DEVICE, T_DEVICE, T_INGRESS, METRIC, VALUE,
                ValidationStatus.VALID);

        assertThat(event.deviceId()).isEqualTo(DEVICE);
        assertThat(event.tDevice()).isEqualTo(T_DEVICE);
        assertThat(event.tIngress()).isEqualTo(T_INGRESS);
        assertThat(event.metric()).isEqualTo(METRIC);
        assertThat(event.value()).isEqualTo(VALUE);
        assertThat(event.status()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void revisionAppended_withValidArguments_carriesAllFields() {
        TelemetryRevisionAppended event = new TelemetryRevisionAppended(DEVICE, T_DEVICE, T_INGRESS, METRIC, VALUE,
                ValidationStatus.VALID);

        assertThat(event.deviceId()).isEqualTo(DEVICE);
        assertThat(event.tDevice()).isEqualTo(T_DEVICE);
        assertThat(event.tIngress()).isEqualTo(T_INGRESS);
        assertThat(event.metric()).isEqualTo(METRIC);
        assertThat(event.value()).isEqualTo(VALUE);
        assertThat(event.status()).isEqualTo(ValidationStatus.VALID);
    }

    @ParameterizedTest(name = "{0}: null deviceId rejected")
    @MethodSource("factories")
    void constructor_nullDeviceId_isRejected(String name, EventFactory factory) {
        assertThatThrownBy(() -> factory.create(null, T_DEVICE, T_INGRESS))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @ParameterizedTest(name = "{0}: blank deviceId rejected")
    @MethodSource("factories")
    void constructor_blankDeviceId_isRejected(String name, EventFactory factory) {
        assertThatThrownBy(() -> factory.create("   ", T_DEVICE, T_INGRESS))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest(name = "{0}: empty deviceId rejected")
    @MethodSource("factories")
    void constructor_emptyDeviceId_isRejected(String name, EventFactory factory) {
        assertThatThrownBy(() -> factory.create("", T_DEVICE, T_INGRESS))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest(name = "{0}: null tDevice rejected")
    @MethodSource("factories")
    void constructor_nullTDevice_isRejected(String name, EventFactory factory) {
        assertThatThrownBy(() -> factory.create(DEVICE, null, T_INGRESS))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @ParameterizedTest(name = "{0}: null tIngress rejected")
    @MethodSource("factories")
    void constructor_nullTIngress_isRejected(String name, EventFactory factory) {
        assertThatThrownBy(() -> factory.create(DEVICE, T_DEVICE, null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @ParameterizedTest(name = "{0}: equal fields give equal events")
    @MethodSource("factories")
    void equals_sameFields_areEqualWithSameHashCode(String name, EventFactory factory) {
        Object first = factory.create(DEVICE, T_DEVICE, T_INGRESS);
        Object second = factory.create(DEVICE, T_DEVICE, T_INGRESS);

        assertThat(first).isEqualTo(second).hasSameHashCodeAs(second);
    }

    @ParameterizedTest(name = "{0}: different deviceId gives different events")
    @MethodSource("factories")
    void equals_differentDeviceId_areNotEqual(String name, EventFactory factory) {
        Object first = factory.create(DEVICE, T_DEVICE, T_INGRESS);
        Object second = factory.create("device-2", T_DEVICE, T_INGRESS);

        assertThat(first).isNotEqualTo(second);
    }

    @ParameterizedTest(name = "{0}: different tDevice gives different events")
    @MethodSource("factories")
    void equals_differentTDevice_areNotEqual(String name, EventFactory factory) {
        Object first = factory.create(DEVICE, T_DEVICE, T_INGRESS);
        Object second = factory.create(DEVICE, T_DEVICE.plusSeconds(1), T_INGRESS);

        assertThat(first).isNotEqualTo(second);
    }

    @Test
    void validationStatus_declaresValidAndValidationFailed() {
        assertThat(ValidationStatus.values()).contains(ValidationStatus.VALID, ValidationStatus.VALIDATION_FAILED);
    }

    @ParameterizedTest
    @ValueSource(strings = { "\t", "\n", " \t " })
    void validated_whitespaceOnlyDeviceId_isRejected(String deviceId) {
        assertThatThrownBy(() -> new TelemetrySampleValidated(deviceId, T_DEVICE, T_INGRESS, METRIC, VALUE,
                ValidationStatus.VALID)).isInstanceOf(IllegalArgumentException.class);
    }
}
