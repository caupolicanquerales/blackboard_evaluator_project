package com.blackboard.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class IngressPacketTest {

    private static TelemetrySample sample() {
        return new TelemetrySample("dev-1", MetricKind.values()[0],
                Instant.parse("2024-01-01T00:00:00Z"), Instant.parse("2024-01-01T00:00:01Z"),
                10.0, ValidationStatus.UNVALIDATED);
    }

    @Test
    void constructor_validArguments_exposesComponents() {
        TelemetrySample s = sample();

        IngressPacket p = new IngressPacket("dev-1", SourceKind.EDGE_DEVICE, List.of(s));

        assertThat(p.deviceId()).isEqualTo("dev-1");
        assertThat(p.sourceKind()).isEqualTo(SourceKind.EDGE_DEVICE);
        assertThat(p.samples()).containsExactly(s);
    }

    @Test
    void constructor_nullDeviceId_throwsNullPointerException() {
        List<TelemetrySample> samples = List.of(sample());

        assertThatThrownBy(() -> new IngressPacket(null, SourceKind.EDGE_DEVICE, samples))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullSourceKind_throwsNullPointerException() {
        List<TelemetrySample> samples = List.of(sample());

        assertThatThrownBy(() -> new IngressPacket("dev-1", null, samples))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullSamples_throwsNullPointerException() {
        assertThatThrownBy(() -> new IngressPacket("dev-1", SourceKind.BIKE_COMPUTER, null))
                .isInstanceOf(NullPointerException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankDeviceId_throwsIllegalArgumentException(String blank) {
        List<TelemetrySample> samples = List.of(sample());

        assertThatThrownBy(() -> new IngressPacket(blank, SourceKind.SMART_WEARABLE, samples))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_emptySamples_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> new IngressPacket("dev-1", SourceKind.EDGE_DEVICE, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void samples_returnedList_isUnmodifiable() {
        IngressPacket p = new IngressPacket("dev-1", SourceKind.EDGE_DEVICE, List.of(sample()));
        List<TelemetrySample> result = p.samples();
        TelemetrySample extra = sample();

        assertThatThrownBy(() -> result.add(extra))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void samples_sourceListMutatedAfterConstruction_packetUnaffected() {
        List<TelemetrySample> source = new ArrayList<>(List.of(sample()));
        IngressPacket p = new IngressPacket("dev-1", SourceKind.EDGE_DEVICE, source);

        source.add(sample());

        assertThat(p.samples()).hasSize(1);
    }
}
