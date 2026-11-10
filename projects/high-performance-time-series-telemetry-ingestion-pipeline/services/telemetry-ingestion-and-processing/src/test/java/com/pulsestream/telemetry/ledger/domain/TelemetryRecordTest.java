package com.pulsestream.telemetry.ledger.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetryRecordTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:01Z");
    private static final Instant T_INGRESS_2 = Instant.parse("2024-01-01T00:00:05Z");
    private static final UUID ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final UUID OTHER_ID = UUID.fromString("00000000-0000-0000-0000-000000000002");

    private static TelemetryRecord original() {
        return TelemetryRecord.original("dev-1", "temperature", 21.5, T_DEVICE, T_INGRESS, "VALID");
    }

    @Test
    void original_validInput_createsRevisionZeroWithoutSupersedes() {
        TelemetryRecord record = original();

        assertThat(record.id()).isNotNull();
        assertThat(record.deviceId()).isEqualTo("dev-1");
        assertThat(record.metric()).isEqualTo("temperature");
        assertThat(record.value()).isEqualTo(21.5);
        assertThat(record.tDevice()).isEqualTo(T_DEVICE);
        assertThat(record.tIngress()).isEqualTo(T_INGRESS);
        assertThat(record.validationStatus()).isEqualTo("VALID");
        assertThat(record.revision()).isZero();
        assertThat(record.supersedesId()).isNull();
    }

    @Test
    void original_calledTwice_generatesDistinctIds() {
        assertThat(original().id()).isNotEqualTo(original().id());
    }

    @Test
    void reviseWith_validInput_returnsNewRecordLinkedToPrevious() {
        TelemetryRecord first = original();

        TelemetryRecord revised = first.reviseWith(30.0, T_INGRESS_2, "CORRECTED");

        assertThat(revised).isNotSameAs(first);
        assertThat(revised.id()).isNotNull().isNotEqualTo(first.id());
        assertThat(revised.deviceId()).isEqualTo(first.deviceId());
        assertThat(revised.metric()).isEqualTo(first.metric());
        assertThat(revised.tDevice()).isEqualTo(first.tDevice());
        assertThat(revised.value()).isEqualTo(30.0);
        assertThat(revised.tIngress()).isEqualTo(T_INGRESS_2);
        assertThat(revised.validationStatus()).isEqualTo("CORRECTED");
        assertThat(revised.revision()).isEqualTo(1);
        assertThat(revised.supersedesId()).isEqualTo(first.id());
    }

    @Test
    void reviseWith_afterRevision_leavesOriginalUnchanged() {
        TelemetryRecord first = original();

        first.reviseWith(30.0, T_INGRESS_2, "CORRECTED");

        assertThat(first.value()).isEqualTo(21.5);
        assertThat(first.revision()).isZero();
        assertThat(first.supersedesId()).isNull();
        assertThat(first.validationStatus()).isEqualTo("VALID");
    }

    @Test
    void reviseWith_chained_incrementsRevisionAndChainsSupersedes() {
        TelemetryRecord second = original().reviseWith(1.0, T_INGRESS_2, "CORRECTED");

        TelemetryRecord third = second.reviseWith(2.0, T_INGRESS_2, "CORRECTED");

        assertThat(third.revision()).isEqualTo(2);
        assertThat(third.supersedesId()).isEqualTo(second.id());
    }

    @Test
    void constructor_negativeRevision_throws() {
        assertThatThrownBy(() -> new TelemetryRecord(ID, "dev-1", "m", 1.0, T_DEVICE, T_INGRESS, "VALID", -1, OTHER_ID))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_revisionZeroWithSupersedes_throws() {
        assertThatThrownBy(() -> new TelemetryRecord(ID, "dev-1", "m", 1.0, T_DEVICE, T_INGRESS, "VALID", 0, OTHER_ID))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_positiveRevisionWithoutSupersedes_throws() {
        assertThatThrownBy(() -> new TelemetryRecord(ID, "dev-1", "m", 1.0, T_DEVICE, T_INGRESS, "VALID", 1, null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_consistentRevisionAndSupersedes_createsRecord() {
        TelemetryRecord record =
                new TelemetryRecord(ID, "dev-1", "m", 1.0, T_DEVICE, T_INGRESS, "VALID", 1, OTHER_ID);

        assertThat(record.id()).isEqualTo(ID);
        assertThat(record.revision()).isEqualTo(1);
        assertThat(record.supersedesId()).isEqualTo(OTHER_ID);
    }

    @Test
    void constructor_nullId_throws() {
        assertThatThrownBy(() -> new TelemetryRecord(null, "dev-1", "m", 1.0, T_DEVICE, T_INGRESS, "VALID", 0, null))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullTDevice_throws() {
        assertThatThrownBy(() -> new TelemetryRecord(ID, "dev-1", "m", 1.0, null, T_INGRESS, "VALID", 0, null))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullTIngress_throws() {
        assertThatThrownBy(() -> new TelemetryRecord(ID, "dev-1", "m", 1.0, T_DEVICE, null, "VALID", 0, null))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullValidationStatus_throws() {
        assertThatThrownBy(() -> new TelemetryRecord(ID, "dev-1", "m", 1.0, T_DEVICE, T_INGRESS, null, 0, null))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullDeviceId_throws() {
        assertThatThrownBy(() -> new TelemetryRecord(ID, null, "m", 1.0, T_DEVICE, T_INGRESS, "VALID", 0, null))
                .isInstanceOf(RuntimeException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   "})
    void original_blankDeviceId_throws(String blank) {
        assertThatThrownBy(() -> TelemetryRecord.original(blank, "m", 1.0, T_DEVICE, T_INGRESS, "VALID"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   "})
    void original_blankMetric_throws(String blank) {
        assertThatThrownBy(() -> TelemetryRecord.original("dev-1", blank, 1.0, T_DEVICE, T_INGRESS, "VALID"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   "})
    void original_blankValidationStatus_throws(String blank) {
        assertThatThrownBy(() -> TelemetryRecord.original("dev-1", "m", 1.0, T_DEVICE, T_INGRESS, blank))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   "})
    void reviseWith_blankValidationStatus_throws(String blank) {
        TelemetryRecord first = original();

        assertThatThrownBy(() -> first.reviseWith(2.0, T_INGRESS_2, blank))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void reviseWith_nullTIngress_throws() {
        TelemetryRecord first = original();

        assertThatThrownBy(() -> first.reviseWith(2.0, null, "CORRECTED"))
                .isInstanceOf(RuntimeException.class);
    }
}
