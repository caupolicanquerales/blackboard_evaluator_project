package com.pulsestream.telemetry.distribution.domain;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class TelemetryWindowBroadcastTest {

    private static final Instant START = Instant.parse("2025-01-01T00:00:00Z");
    private static final Instant END = Instant.parse("2025-01-01T00:00:01Z");

    private static TelemetryEvent event() {
        return new TelemetryEvent(1, TelemetryEvent.Type.values()[0],
                TelemetryEvent.keyOf("dev-1", "temp", START, 1), "dev-1", "temp", START, 1, 1.5,
                ValidationStatus.values()[0], "pub-1");
    }

    @Test
    void windowStart_afterConstruction_returnsGivenStart() {
        var window = new TelemetryWindowBroadcast(START, END, List.of(event()));

        assertThat(window.windowStart()).isEqualTo(START);
    }

    @Test
    void windowEnd_afterConstruction_returnsGivenEnd() {
        var window = new TelemetryWindowBroadcast(START, END, List.of(event()));

        assertThat(window.windowEnd()).isEqualTo(END);
    }

    @Test
    void events_afterConstruction_returnsGivenEvents() {
        TelemetryEvent e = event();
        var window = new TelemetryWindowBroadcast(START, END, List.of(e));

        assertThat(window.events()).hasSize(1).containsExactly(e);
    }
}
