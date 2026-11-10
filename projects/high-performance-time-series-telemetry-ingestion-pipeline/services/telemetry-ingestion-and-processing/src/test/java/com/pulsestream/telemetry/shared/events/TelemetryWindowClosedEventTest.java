package com.pulsestream.telemetry.shared.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetryWindowClosedEventTest {

    private static final Instant START = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant END = Instant.parse("2024-01-01T00:00:10Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:20Z");

    private static TelemetrySampleEvent sample(long offsetSeconds) {
        return new TelemetrySampleEvent("dev-1", "temp", 21.5, START.plusSeconds(offsetSeconds),
                T_INGRESS, TelemetrySampleEvent.VALID);
    }

    private static TelemetryWindowClosedEvent event(String deviceId, Instant start, Instant end,
            List<TelemetrySampleEvent> samples) {
        return new TelemetryWindowClosedEvent(deviceId, start, end, samples);
    }

    @Test
    void constructor_validArguments_exposesComponents() {
        List<TelemetrySampleEvent> samples = List.of(sample(1), sample(2));

        TelemetryWindowClosedEvent e = event("dev-1", START, END, samples);

        assertThat(e.deviceId()).isEqualTo("dev-1");
        assertThat(e.windowStart()).isEqualTo(START);
        assertThat(e.windowEnd()).isEqualTo(END);
        assertThat(e.samples()).containsExactly(sample(1), sample(2));
    }

    @Test
    void constructor_emptySamples_isAccepted() {
        TelemetryWindowClosedEvent e = event("dev-1", START, END, List.of());

        assertThat(e.samples()).isEmpty();
    }

    @Test
    void constructor_nullDeviceId_isRejected() {
        assertThatThrownBy(() -> event(null, START, END, List.of()))
                .isInstanceOfAny(IllegalArgumentException.class, NullPointerException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "   "})
    void constructor_blankDeviceId_isRejected(String blank) {
        assertThatThrownBy(() -> event(blank, START, END, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullWindowStart_isRejected() {
        assertThatThrownBy(() -> event("dev-1", null, END, List.of()))
                .isInstanceOfAny(IllegalArgumentException.class, NullPointerException.class);
    }

    @Test
    void constructor_nullWindowEnd_isRejected() {
        assertThatThrownBy(() -> event("dev-1", START, null, List.of()))
                .isInstanceOfAny(IllegalArgumentException.class, NullPointerException.class);
    }

    @Test
    void constructor_windowEndEqualToStart_isRejected() {
        assertThatThrownBy(() -> event("dev-1", START, START, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_windowEndBeforeStart_isRejected() {
        assertThatThrownBy(() -> event("dev-1", END, START, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullSamples_isRejected() {
        assertThatThrownBy(() -> event("dev-1", START, END, null))
                .isInstanceOfAny(IllegalArgumentException.class, NullPointerException.class);
    }

    @Test
    void samples_sourceListMutatedAfterConstruction_isNotAffected() {
        List<TelemetrySampleEvent> source = new ArrayList<>(List.of(sample(1)));
        TelemetryWindowClosedEvent e = event("dev-1", START, END, source);

        source.add(sample(2));

        assertThat(e.samples()).containsExactly(sample(1));
    }

    @Test
    void samples_returnedList_isUnmodifiable() {
        TelemetryWindowClosedEvent e = event("dev-1", START, END, List.of(sample(1)));

        assertThatThrownBy(() -> e.samples().add(sample(2)))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void samples_suppliedOrder_isPreserved() {
        TelemetryWindowClosedEvent e = event("dev-1", START, END,
                List.of(sample(1), sample(3), sample(5)));

        assertThat(e.samples()).extracting(TelemetrySampleEvent::tDevice)
                .containsExactly(START.plusSeconds(1), START.plusSeconds(3), START.plusSeconds(5));
    }

    @Test
    void equals_sameComponents_areEqualWithSameHashCode() {
        TelemetryWindowClosedEvent a = event("dev-1", START, END, List.of(sample(1)));
        TelemetryWindowClosedEvent b = event("dev-1", START, END, List.of(sample(1)));

        assertThat(a).isEqualTo(b).hasSameHashCodeAs(b);
    }
}
