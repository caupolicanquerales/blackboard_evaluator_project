package com.pulsestream.telemetry.shared.events;

import java.time.Instant;
import java.util.List;
import java.util.Objects;

public record TelemetryWindowClosedEvent(String deviceId, Instant windowStart, Instant windowEnd, List<TelemetrySampleEvent> samples) {

    public TelemetryWindowClosedEvent {
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(windowStart, "windowStart must not be null");
        Objects.requireNonNull(windowEnd, "windowEnd must not be null");
        Objects.requireNonNull(samples, "samples must not be null");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (!windowEnd.isAfter(windowStart)) {
            throw new IllegalArgumentException("windowEnd must be after windowStart");
        }
        samples = List.copyOf(samples);
    }

    public void TelemetryWindowClosedEvent(String deviceId, Instant windowStart, Instant windowEnd, List<TelemetrySampleEvent> samples) {
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(windowStart, "windowStart must not be null");
        Objects.requireNonNull(windowEnd, "windowEnd must not be null");
        Objects.requireNonNull(samples, "samples must not be null");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (!windowEnd.isAfter(windowStart)) {
            throw new IllegalArgumentException("windowEnd must be after windowStart");
        }
        samples = List.copyOf(samples);
    }
}
