package com.pulsestream.telemetry.intake.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class IngressPacketTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:01Z");

    private static TelemetrySample sample(String deviceId) {
        return TelemetrySample.unvalidated(deviceId, "temp", 21.5, T_DEVICE, T_INGRESS);
    }

    @Test
    void constructor_validArguments_exposesComponents() {
        List<TelemetrySample> samples = List.of(sample("dev-1"), sample("dev-1"));

        IngressPacket packet = new IngressPacket("dev-1", T_INGRESS, samples);

        assertThat(packet.deviceId()).isEqualTo("dev-1");
        assertThat(packet.tIngress()).isEqualTo(T_INGRESS);
        assertThat(packet.samples()).containsExactlyElementsOf(samples);
    }

    @Test
    void constructor_nullDeviceId_throws() {
        List<TelemetrySample> samples = List.of(sample("dev-1"));

        assertThatThrownBy(() -> new IngressPacket(null, T_INGRESS, samples))
                .isInstanceOf(RuntimeException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankDeviceId_throws(String blank) {
        List<TelemetrySample> samples = List.of(sample("dev-1"));

        assertThatThrownBy(() -> new IngressPacket(blank, T_INGRESS, samples))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullTIngress_throws() {
        List<TelemetrySample> samples = List.of(sample("dev-1"));

        assertThatThrownBy(() -> new IngressPacket("dev-1", null, samples))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_nullSamples_throws() {
        assertThatThrownBy(() -> new IngressPacket("dev-1", T_INGRESS, null))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_emptySamples_throws() {
        assertThatThrownBy(() -> new IngressPacket("dev-1", T_INGRESS, List.of()))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_sampleWithDifferentDeviceId_throws() {
        List<TelemetrySample> samples = List.of(sample("dev-1"), sample("dev-2"));

        assertThatThrownBy(() -> new IngressPacket("dev-1", T_INGRESS, samples))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void samples_returnedList_isUnmodifiable() {
        IngressPacket packet = new IngressPacket("dev-1", T_INGRESS, List.of(sample("dev-1")));

        assertThatThrownBy(() -> packet.samples().add(sample("dev-1")))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void constructor_sourceListMutatedAfterwards_packetUnchanged() {
        List<TelemetrySample> source = new ArrayList<>(List.of(sample("dev-1")));
        IngressPacket packet = new IngressPacket("dev-1", T_INGRESS, source);

        source.add(sample("dev-1"));

        assertThat(packet.samples()).hasSize(1);
    }
}
