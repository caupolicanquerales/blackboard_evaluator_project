package com.pulsestream.telemetry.broadcasting.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem.Kind;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class BroadcastItemTest {

    private static final Instant T0 = Instant.parse("2024-01-01T00:00:00Z");

    private static TelemetrySampleEvent sampleEvent(String deviceId, long offsetSeconds) {
        return new TelemetrySampleEvent(deviceId, "temperature", 21.5,
                T0.plusSeconds(offsetSeconds), T0.plusSeconds(offsetSeconds + 1),
                TelemetrySampleEvent.VALID);
    }

    private static TelemetryWindowClosedEvent windowEvent(String deviceId, List<TelemetrySampleEvent> samples) {
        return new TelemetryWindowClosedEvent(deviceId, T0, T0.plusSeconds(60), samples);
    }

    @Test
    void sample_withSampleEvent_createsSampleItemWithSingleSample() {
        TelemetrySampleEvent event = sampleEvent("device-1", 0);

        BroadcastItem item = BroadcastItem.sample(event);

        assertThat(item.kind()).isEqualTo(Kind.SAMPLE);
        assertThat(item.deviceId()).isEqualTo("device-1");
        assertThat(item.samples()).containsExactly(event);
    }

    @Test
    void window_withWindowEvent_createsWindowItemWithAllSamplesInOrder() {
        TelemetrySampleEvent first = sampleEvent("device-2", 1);
        TelemetrySampleEvent second = sampleEvent("device-2", 2);
        TelemetrySampleEvent third = sampleEvent("device-2", 3);

        BroadcastItem item = BroadcastItem.window(windowEvent("device-2", List.of(first, second, third)));

        assertThat(item.kind()).isEqualTo(Kind.WINDOW);
        assertThat(item.deviceId()).isEqualTo("device-2");
        assertThat(item.samples()).containsExactly(first, second, third);
    }

    @Test
    void sample_withNull_throws() {
        assertThatThrownBy(() -> BroadcastItem.sample(null)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void window_withNull_throws() {
        assertThatThrownBy(() -> BroadcastItem.window(null)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void window_withEmptySamples_throws() {
        TelemetryWindowClosedEvent empty = windowEvent("device-3", List.of());

        assertThatThrownBy(() -> BroadcastItem.window(empty)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_withEmptySamples_throws() {
        assertThatThrownBy(() -> new BroadcastItem(Kind.SAMPLE, "device-4", List.of()))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_withNullSamples_throws() {
        assertThatThrownBy(() -> new BroadcastItem(Kind.SAMPLE, "device-4", null))
                .isInstanceOf(RuntimeException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   "})
    void constructor_withBlankDeviceId_throws(String deviceId) {
        List<TelemetrySampleEvent> samples = List.of(sampleEvent("device-5", 0));

        assertThatThrownBy(() -> new BroadcastItem(Kind.SAMPLE, deviceId, samples))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void constructor_withNullDeviceId_throws() {
        List<TelemetrySampleEvent> samples = List.of(sampleEvent("device-5", 0));

        assertThatThrownBy(() -> new BroadcastItem(Kind.SAMPLE, null, samples))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void samples_returnedList_isUnmodifiable() {
        BroadcastItem item = BroadcastItem.sample(sampleEvent("device-6", 0));
        TelemetrySampleEvent other = sampleEvent("device-6", 5);

        assertThatThrownBy(() -> item.samples().add(other))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void constructor_whenSourceListMutatedAfterwards_itemIsUnaffected() {
        TelemetrySampleEvent original = sampleEvent("device-7", 0);
        List<TelemetrySampleEvent> source = new ArrayList<>(List.of(original));
        BroadcastItem item = new BroadcastItem(Kind.WINDOW, "device-7", source);

        source.add(sampleEvent("device-7", 9));

        assertThat(item.samples()).containsExactly(original);
    }
}
