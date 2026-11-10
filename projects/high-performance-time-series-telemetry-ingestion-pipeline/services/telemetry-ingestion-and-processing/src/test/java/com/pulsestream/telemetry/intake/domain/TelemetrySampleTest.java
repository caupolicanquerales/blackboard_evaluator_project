package com.pulsestream.telemetry.intake.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.intake.domain.TelemetrySample.MetricType;
import com.pulsestream.telemetry.intake.domain.TelemetrySample.ValidationStatus;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetrySampleTest {

    private static final UUID RECORD_ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final Instant DEVICE_TS = Instant.parse("2025-01-01T10:00:00Z");
    private static final Instant INGRESS_TS = Instant.parse("2025-01-01T10:00:05Z");

    private static TelemetrySample sample(String deviceId, MetricType type, Instant deviceTs,
            Instant ingressTs, ValidationStatus status, UUID id) {
        return new TelemetrySample(id, deviceId, type, 142.5, deviceTs, ingressTs, status);
    }

    private static TelemetrySample validSample() {
        return sample("dev-1", MetricType.HEART_RATE, DEVICE_TS, INGRESS_TS, ValidationStatus.VALID, RECORD_ID);
    }

    @Test
    void constructor_validArguments_exposesAllFields() {
        TelemetrySample s = validSample();

        assertThat(s.recordId()).isEqualTo(RECORD_ID);
        assertThat(s.deviceId()).isEqualTo("dev-1");
        assertThat(s.metricType()).isEqualTo(MetricType.HEART_RATE);
        assertThat(s.value()).isEqualTo(142.5);
        assertThat(s.deviceTimestamp()).isEqualTo(DEVICE_TS);
        assertThat(s.ingressTimestamp()).isEqualTo(INGRESS_TS);
        assertThat(s.validationStatus()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void metricType_values_containsAllDeclaredConstants() {
        assertThat(MetricType.values()).containsExactlyInAnyOrder(
                MetricType.HEART_RATE, MetricType.POWER, MetricType.CADENCE,
                MetricType.GROUND_CONTACT_TIME, MetricType.RESPIRATION,
                MetricType.SWIM_STROKE, MetricType.SWIM_PACE);
    }

    @Test
    void validationStatus_values_containsValidAndFailed() {
        assertThat(ValidationStatus.values())
                .containsExactlyInAnyOrder(ValidationStatus.VALID, ValidationStatus.VALIDATION_FAILED);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankDeviceId_throws(String deviceId) {
        assertThatThrownBy(() -> sample(deviceId, MetricType.POWER, DEVICE_TS, INGRESS_TS,
                ValidationStatus.VALID, RECORD_ID)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullDeviceId_throws() {
        assertThatThrownBy(() -> sample(null, MetricType.POWER, DEVICE_TS, INGRESS_TS,
                ValidationStatus.VALID, RECORD_ID)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullRecordId_throws() {
        assertThatThrownBy(() -> sample("dev-1", MetricType.POWER, DEVICE_TS, INGRESS_TS,
                ValidationStatus.VALID, null)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullMetricType_throws() {
        assertThatThrownBy(() -> sample("dev-1", null, DEVICE_TS, INGRESS_TS,
                ValidationStatus.VALID, RECORD_ID)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullDeviceTimestamp_throws() {
        assertThatThrownBy(() -> sample("dev-1", MetricType.POWER, null, INGRESS_TS,
                ValidationStatus.VALID, RECORD_ID)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullIngressTimestamp_throws() {
        assertThatThrownBy(() -> sample("dev-1", MetricType.POWER, DEVICE_TS, null,
                ValidationStatus.VALID, RECORD_ID)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullValidationStatus_throws() {
        assertThatThrownBy(() -> sample("dev-1", MetricType.POWER, DEVICE_TS, INGRESS_TS,
                null, RECORD_ID)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void recordIdFor_sameInputs_returnsSameId() {
        UUID first = TelemetrySample.recordIdFor("dev-1", MetricType.CADENCE, DEVICE_TS);
        UUID second = TelemetrySample.recordIdFor("dev-1", MetricType.CADENCE, DEVICE_TS);

        assertThat(first).isEqualTo(second);
    }

    @Test
    void recordIdFor_pipeDelimitedNameBytes_matchesNameUuid() {
        UUID expected = UUID.nameUUIDFromBytes(
                ("dev-1|" + MetricType.CADENCE + "|" + DEVICE_TS).getBytes(StandardCharsets.UTF_8));

        assertThat(TelemetrySample.recordIdFor("dev-1", MetricType.CADENCE, DEVICE_TS)).isEqualTo(expected);
    }

    @Test
    void recordIdFor_differentDevice_returnsDifferentId() {
        assertThat(TelemetrySample.recordIdFor("dev-1", MetricType.POWER, DEVICE_TS))
                .isNotEqualTo(TelemetrySample.recordIdFor("dev-2", MetricType.POWER, DEVICE_TS));
    }

    @Test
    void recordIdFor_differentMetricType_returnsDifferentId() {
        assertThat(TelemetrySample.recordIdFor("dev-1", MetricType.POWER, DEVICE_TS))
                .isNotEqualTo(TelemetrySample.recordIdFor("dev-1", MetricType.CADENCE, DEVICE_TS));
    }

    @Test
    void recordIdFor_differentDeviceTimestamp_returnsDifferentId() {
        assertThat(TelemetrySample.recordIdFor("dev-1", MetricType.POWER, DEVICE_TS))
                .isNotEqualTo(TelemetrySample.recordIdFor("dev-1", MetricType.POWER, DEVICE_TS.plusSeconds(1)));
    }

    @Test
    void recordIdFor_differentIngressTimestamp_doesNotAffectIdentity() {
        TelemetrySample early = sample("dev-1", MetricType.POWER, DEVICE_TS, INGRESS_TS,
                ValidationStatus.VALID, TelemetrySample.recordIdFor("dev-1", MetricType.POWER, DEVICE_TS));
        TelemetrySample late = sample("dev-1", MetricType.POWER, DEVICE_TS, INGRESS_TS.plusSeconds(60),
                ValidationStatus.VALID, TelemetrySample.recordIdFor("dev-1", MetricType.POWER, DEVICE_TS));

        assertThat(early.recordId()).isEqualTo(late.recordId());
    }

    @Test
    void withStatus_newStatus_returnsCopyWithNewStatus() {
        TelemetrySample original = validSample();

        TelemetrySample failed = original.withStatus(ValidationStatus.VALIDATION_FAILED);

        assertThat(failed.validationStatus()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
        assertThat(original.validationStatus()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void withStatus_failedStatus_keepsPayload() {
        TelemetrySample original = validSample();

        TelemetrySample failed = original.withStatus(ValidationStatus.VALIDATION_FAILED);

        assertThat(failed).usingRecursiveComparison().ignoringFields("validationStatus").isEqualTo(original);
    }

    @Test
    void withStatus_nullStatus_throws() {
        TelemetrySample original = validSample();

        assertThatThrownBy(() -> original.withStatus(null)).isInstanceOf(RuntimeException.class);
    }
}
