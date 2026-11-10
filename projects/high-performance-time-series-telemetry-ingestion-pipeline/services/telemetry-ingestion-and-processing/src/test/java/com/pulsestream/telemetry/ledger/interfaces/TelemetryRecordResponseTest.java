package com.pulsestream.telemetry.ledger.interfaces;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class TelemetryRecordResponseTest {

    private static final UUID ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final UUID PREVIOUS_ID = UUID.fromString("00000000-0000-0000-0000-000000000002");
    private static final Instant T_DEVICE = Instant.parse("2024-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T10:00:05Z");

    @Test
    void from_originalRecord_mapsAllFieldsWithNullSupersedesId() {
        TelemetryRecord record = new TelemetryRecord(
                ID, "device-1", "temperature", 21.5, T_DEVICE, T_INGRESS, "VALID", 0, null);

        TelemetryRecordResponse response = TelemetryRecordResponse.from(record);

        assertThat(response).isEqualTo(new TelemetryRecordResponse(
                ID, "device-1", "temperature", 21.5, T_DEVICE, T_INGRESS, "VALID", 0, null));
    }

    @Test
    void from_revisedRecord_preservesRevisionAndSupersedesId() {
        TelemetryRecord record = new TelemetryRecord(
                ID, "device-1", "temperature", 22.0, T_DEVICE, T_INGRESS, "CORRECTED", 3, PREVIOUS_ID);

        TelemetryRecordResponse response = TelemetryRecordResponse.from(record);

        assertThat(response.revision()).isEqualTo(3);
        assertThat(response.supersedesId()).isEqualTo(PREVIOUS_ID);
        assertThat(response.id()).isEqualTo(ID);
        assertThat(response.validationStatus()).isEqualTo("CORRECTED");
    }

    @Test
    void from_record_preservesInstantsAndValue() {
        TelemetryRecord record = new TelemetryRecord(
                ID, "device-9", "humidity", -0.25, T_DEVICE, T_INGRESS, "VALID", 0, null);

        TelemetryRecordResponse response = TelemetryRecordResponse.from(record);

        assertThat(response.tDevice()).isEqualTo(T_DEVICE);
        assertThat(response.tIngress()).isEqualTo(T_INGRESS);
        assertThat(response.value()).isEqualTo(-0.25);
        assertThat(response.deviceId()).isEqualTo("device-9");
        assertThat(response.metric()).isEqualTo("humidity");
    }

    @Test
    void from_nullRecord_throwsNullPointerException() {
        assertThatThrownBy(() -> TelemetryRecordResponse.from(null))
                .isInstanceOf(NullPointerException.class);
    }
}
