package com.pulsestream.telemetry.distribution.domain;

import java.time.Instant;
import java.util.List;
import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;

public record TelemetryWindowBroadcast(Instant windowStart, Instant windowEnd, List<TelemetryEvent> events) {

    public TelemetryWindowBroadcast {
        events = List.copyOf(events);
    }
}
