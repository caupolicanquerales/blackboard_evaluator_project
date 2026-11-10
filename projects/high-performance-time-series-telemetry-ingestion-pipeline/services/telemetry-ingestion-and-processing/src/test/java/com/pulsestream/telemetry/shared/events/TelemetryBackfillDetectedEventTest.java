package com.pulsestream.telemetry.shared.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class TelemetryBackfillDetectedEventTest {

    private static TelemetrySampleEvent sample() {
        return new TelemetrySampleEvent(
                "device-1",
                "temperature",
                21.5,
                Instant.parse("2024-01-01T00:00:00Z"),
                Instant.parse("2024-01-01T00:00:05Z"),
                TelemetrySampleEvent.VALID);
    }

    @Test
    void constructor_beyondWindow_exposesComponents() {
        TelemetrySampleEvent sample = sample();

        TelemetryBackfillDetectedEvent event = new TelemetryBackfillDetectedEvent(sample, true);

        assertThat(event.sample()).isEqualTo(sample);
        assertThat(event.beyondReorderWindow()).isTrue();
    }

    @Test
    void constructor_withinWindow_marksNotBeyondReorderWindow() {
        TelemetryBackfillDetectedEvent event = new TelemetryBackfillDetectedEvent(sample(), false);

        assertThat(event.beyondReorderWindow()).isFalse();
    }

    @Test
    void constructor_nullSample_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetryBackfillDetectedEvent(null, true))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullSampleWithinWindow_throwsNullPointerException() {
        assertThatThrownBy(() -> new TelemetryBackfillDetectedEvent(null, false))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void equals_sameComponents_areEqual() {
        assertThat(new TelemetryBackfillDetectedEvent(sample(), true))
                .isEqualTo(new TelemetryBackfillDetectedEvent(sample(), true))
                .hasSameHashCodeAs(new TelemetryBackfillDetectedEvent(sample(), true));
    }

    @Test
    void equals_differentBeyondFlag_areNotEqual() {
        assertThat(new TelemetryBackfillDetectedEvent(sample(), true))
                .isNotEqualTo(new TelemetryBackfillDetectedEvent(sample(), false));
    }
}
