package com.pulsestream.telemetry.intake.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.intake.domain.IngressPacket.RawSample;
import com.pulsestream.telemetry.intake.domain.TelemetrySample.MetricType;
import com.pulsestream.telemetry.intake.domain.TelemetrySample.ValidationStatus;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;

class IngressPacketTest {

    private static final String DEVICE_ID = "device-1";
    private static final Instant INGRESS = Instant.parse("2024-01-01T10:00:05Z");
    private static final Instant T1 = Instant.parse("2024-01-01T10:00:00Z");
    private static final Instant T2 = Instant.parse("2024-01-01T10:00:01Z");

    private static RawSample raw(MetricType type, double value, Instant ts) {
        return new RawSample(type, value, ts);
    }

    @Test
    void toSamples_withTwoRawSamples_returnsOneSamplePerRawSampleInOrder() {
        IngressPacket packet = new IngressPacket(DEVICE_ID, INGRESS,
                List.of(raw(MetricType.HEART_RATE, 140.0, T1), raw(MetricType.POWER, 250.5, T2)));

        List<TelemetrySample> samples = packet.toSamples();

        assertThat(samples).hasSize(2);
        assertThat(samples).extracting(TelemetrySample::metricType)
                .containsExactly(MetricType.HEART_RATE, MetricType.POWER);
        assertThat(samples).extracting(TelemetrySample::value).containsExactly(140.0, 250.5);
        assertThat(samples).extracting(TelemetrySample::deviceTimestamp).containsExactly(T1, T2);
    }

    @Test
    void toSamples_always_marksSamplesValidPendingValidation() {
        IngressPacket packet = new IngressPacket(DEVICE_ID, INGRESS,
                List.of(raw(MetricType.CADENCE, 90.0, T1)));

        assertThat(packet.toSamples()).extracting(TelemetrySample::validationStatus)
                .containsExactly(ValidationStatus.VALID);
    }

    @Test
    void toSamples_always_usesPacketDeviceIdAndIngressTimestamp() {
        IngressPacket packet = new IngressPacket(DEVICE_ID, INGRESS,
                List.of(raw(MetricType.RESPIRATION, 18.0, T1), raw(MetricType.SWIM_PACE, 1.5, T2)));

        List<TelemetrySample> samples = packet.toSamples();

        assertThat(samples).extracting(TelemetrySample::deviceId).containsOnly(DEVICE_ID);
        assertThat(samples).extracting(TelemetrySample::ingressTimestamp).containsOnly(INGRESS);
    }

    @Test
    void toSamples_always_usesDeterministicRecordId() {
        IngressPacket packet = new IngressPacket(DEVICE_ID, INGRESS,
                List.of(raw(MetricType.HEART_RATE, 140.0, T1)));

        assertThat(packet.toSamples().get(0).recordId())
                .isEqualTo(TelemetrySample.recordIdFor(DEVICE_ID, MetricType.HEART_RATE, T1));
    }

    @Test
    void toSamples_calledTwice_returnsEqualSamples() {
        IngressPacket packet = new IngressPacket(DEVICE_ID, INGRESS,
                List.of(raw(MetricType.POWER, 200.0, T1)));

        assertThat(packet.toSamples()).isEqualTo(packet.toSamples());
    }

    @Test
    void samples_afterSourceListMutated_remainsUnchanged() {
        List<RawSample> source = new ArrayList<>(List.of(raw(MetricType.POWER, 200.0, T1)));
        IngressPacket packet = new IngressPacket(DEVICE_ID, INGRESS, source);

        source.add(raw(MetricType.CADENCE, 80.0, T2));

        assertThat(packet.samples()).hasSize(1);
    }

    @Test
    void samples_whenModifiedThroughAccessor_throwsUnsupportedOperation() {
        IngressPacket packet = new IngressPacket(DEVICE_ID, INGRESS,
                List.of(raw(MetricType.POWER, 200.0, T1)));

        assertThatThrownBy(() -> packet.samples().add(raw(MetricType.CADENCE, 80.0, T2)))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void accessors_afterConstruction_returnConstructorValues() {
        RawSample sample = raw(MetricType.SWIM_STROKE, 30.0, T1);
        IngressPacket packet = new IngressPacket(DEVICE_ID, INGRESS, List.of(sample));

        assertThat(packet.deviceId()).isEqualTo(DEVICE_ID);
        assertThat(packet.ingressTimestamp()).isEqualTo(INGRESS);
        assertThat(packet.samples()).containsExactly(sample);
        assertThat(sample.metricType()).isEqualTo(MetricType.SWIM_STROKE);
        assertThat(sample.value()).isEqualTo(30.0);
        assertThat(sample.deviceTimestamp()).isEqualTo(T1);
    }

    @Test
    void constructor_withEmptySamples_throws() {
        assertThatThrownBy(() -> new IngressPacket(DEVICE_ID, INGRESS, List.of()))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_withNullSamplesList_throws() {
        assertThatThrownBy(() -> new IngressPacket(DEVICE_ID, INGRESS, null))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_withNullElementInSamples_throws() {
        List<RawSample> withNull = Arrays.asList(raw(MetricType.POWER, 1.0, T1), null);

        assertThatThrownBy(() -> new IngressPacket(DEVICE_ID, INGRESS, withNull))
                .isInstanceOf(RuntimeException.class);
    }
}
