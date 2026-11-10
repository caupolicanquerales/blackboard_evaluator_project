package com.pulsestream.telemetry.shared.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.shared.events.TelemetryContracts.AppendFailed;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.MetricType;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.RevisionReason;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetryBackfillDetected;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetryRecordAppended;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetrySample;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetrySampleOrdered;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetrySampleValidated;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetrySampleValidationFailed;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.ValidationStatus;
import java.lang.reflect.Constructor;
import java.lang.reflect.Modifier;
import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class TelemetryContractsTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T10:00:05Z");

    private static TelemetrySample sample() {
        return new TelemetrySample("dev-1", MetricType.HEART_RATE, T_DEVICE, T_INGRESS, 120.5);
    }

    @Test
    void metricType_values_containsAllDeclaredInOrder() {
        assertThat(MetricType.values()).containsExactly(MetricType.HEART_RATE, MetricType.POWER,
                MetricType.CADENCE, MetricType.GROUND_CONTACT_TIME, MetricType.RESPIRATION,
                MetricType.SWIM_PACE);
    }

    @Test
    void validationStatus_values_containsAllDeclaredInOrder() {
        assertThat(ValidationStatus.values())
                .containsExactly(ValidationStatus.VALID, ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void revisionReason_values_containsAllDeclaredInOrder() {
        assertThat(RevisionReason.values()).containsExactly(RevisionReason.ORIGINAL,
                RevisionReason.CORRECTION, RevisionReason.BACKFILL);
    }

    @Test
    void telemetrySample_validComponents_exposesAccessors() {
        TelemetrySample s = sample();

        assertThat(s.deviceId()).isEqualTo("dev-1");
        assertThat(s.metricType()).isEqualTo(MetricType.HEART_RATE);
        assertThat(s.tDevice()).isEqualTo(T_DEVICE);
        assertThat(s.tIngress()).isEqualTo(T_INGRESS);
        assertThat(s.value()).isEqualTo(120.5);
    }

    @Test
    void telemetrySample_sameComponents_areEqual() {
        assertThat(sample()).isEqualTo(sample()).hasSameHashCodeAs(sample());
    }

    @Test
    void telemetrySample_differentTIngressOnly_areNotEqual() {
        TelemetrySample other =
                new TelemetrySample("dev-1", MetricType.HEART_RATE, T_DEVICE, T_INGRESS.plusSeconds(1), 120.5);

        assertThat(other).isNotEqualTo(sample());
    }

    @Test
    void telemetrySample_nullDeviceId_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySample(null, MetricType.POWER, T_DEVICE, T_INGRESS, 1.0))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetrySample_nullMetricType_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySample("d", null, T_DEVICE, T_INGRESS, 1.0))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetrySample_nullTDevice_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySample("d", MetricType.POWER, null, T_INGRESS, 1.0))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetrySample_nullTIngress_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySample("d", MetricType.POWER, T_DEVICE, null, 1.0))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetrySampleValidated_validSample_exposesSample() {
        assertThat(new TelemetrySampleValidated(sample()).sample()).isEqualTo(sample());
    }

    @Test
    void telemetrySampleValidated_nullSample_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySampleValidated(null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetrySampleValidationFailed_validComponents_exposesAccessors() {
        TelemetrySampleValidationFailed e = new TelemetrySampleValidationFailed(sample(), "out of range");

        assertThat(e.sample()).isEqualTo(sample());
        assertThat(e.reason()).isEqualTo("out of range");
    }

    @Test
    void telemetrySampleValidationFailed_nullSample_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySampleValidationFailed(null, "r"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetrySampleValidationFailed_nullReason_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySampleValidationFailed(sample(), null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetrySampleOrdered_validComponents_exposesAccessors() {
        TelemetrySampleOrdered e = new TelemetrySampleOrdered(sample(), ValidationStatus.VALID);

        assertThat(e.sample()).isEqualTo(sample());
        assertThat(e.status()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void telemetrySampleOrdered_nullSample_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySampleOrdered(null, ValidationStatus.VALID))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetrySampleOrdered_nullStatus_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetrySampleOrdered(sample(), null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetryBackfillDetected_validComponents_exposesAccessors() {
        TelemetryBackfillDetected e = new TelemetryBackfillDetected(sample(),
                ValidationStatus.VALIDATION_FAILED, Duration.ofSeconds(30));

        assertThat(e.sample()).isEqualTo(sample());
        assertThat(e.status()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
        assertThat(e.lateness()).isEqualTo(Duration.ofSeconds(30));
    }

    @Test
    void telemetryBackfillDetected_nullSample_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetryBackfillDetected(null, ValidationStatus.VALID, Duration.ZERO))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetryBackfillDetected_nullStatus_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetryBackfillDetected(sample(), null, Duration.ZERO))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetryBackfillDetected_nullLateness_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetryBackfillDetected(sample(), ValidationStatus.VALID, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetryRecordAppended_validComponents_exposesAccessors() {
        TelemetryRecordAppended e = new TelemetryRecordAppended("dev-1", MetricType.POWER, T_DEVICE, 2,
                RevisionReason.CORRECTION);

        assertThat(e.deviceId()).isEqualTo("dev-1");
        assertThat(e.metricType()).isEqualTo(MetricType.POWER);
        assertThat(e.tDevice()).isEqualTo(T_DEVICE);
        assertThat(e.revision()).isEqualTo(2);
        assertThat(e.reason()).isEqualTo(RevisionReason.CORRECTION);
    }

    @Test
    void telemetryRecordAppended_nullDeviceId_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetryRecordAppended(null, MetricType.POWER, T_DEVICE, 1,
                RevisionReason.ORIGINAL)).isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetryRecordAppended_nullMetricType_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetryRecordAppended("d", null, T_DEVICE, 1, RevisionReason.ORIGINAL))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetryRecordAppended_nullTDevice_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetryRecordAppended("d", MetricType.POWER, null, 1,
                RevisionReason.ORIGINAL)).isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetryRecordAppended_nullReason_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetryRecordAppended("d", MetricType.POWER, T_DEVICE, 1, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void appendFailed_validComponents_exposesAccessors() {
        AppendFailed e = new AppendFailed("dev-1", MetricType.CADENCE, T_DEVICE, "db down");

        assertThat(e.deviceId()).isEqualTo("dev-1");
        assertThat(e.metricType()).isEqualTo(MetricType.CADENCE);
        assertThat(e.tDevice()).isEqualTo(T_DEVICE);
        assertThat(e.cause()).isEqualTo("db down");
    }

    @Test
    void appendFailed_nullDeviceId_throwsNullPointerException() {
        assertThatThrownBy(() -> new AppendFailed(null, MetricType.CADENCE, T_DEVICE, "c"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void appendFailed_nullMetricType_throwsNullPointerException() {
        assertThatThrownBy(() -> new AppendFailed("d", null, T_DEVICE, "c"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void appendFailed_nullTDevice_throwsNullPointerException() {
        assertThatThrownBy(() -> new AppendFailed("d", MetricType.CADENCE, null, "c"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void appendFailed_nullCause_throwsNullPointerException() {
        assertThatThrownBy(() -> new AppendFailed("d", MetricType.CADENCE, T_DEVICE, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void telemetryContracts_class_isFinalWithNoAccessibleConstructor() {
        assertThat(Modifier.isFinal(TelemetryContracts.class.getModifiers())).isTrue();
        for (Constructor<?> c : TelemetryContracts.class.getDeclaredConstructors()) {
            assertThat(Modifier.isPrivate(c.getModifiers())).isTrue();
        }
    }
}
