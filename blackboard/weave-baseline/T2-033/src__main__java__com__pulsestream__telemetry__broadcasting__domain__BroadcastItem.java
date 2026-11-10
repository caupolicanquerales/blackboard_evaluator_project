package com.pulsestream.telemetry.broadcasting.domain;

import java.util.List;
import java.util.Objects;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;

public record BroadcastItem(Kind kind, String deviceId, List<TelemetrySampleEvent> samples) {

    public enum Kind {

        SAMPLE, WINDOW
    }

    public static BroadcastItem sample(TelemetrySampleEvent event) {
        Objects.requireNonNull(event, "event must not be null");
        return new BroadcastItem(Kind.SAMPLE, event.deviceId(), List.of(event));
    }

    public static BroadcastItem window(TelemetryWindowClosedEvent event) {
        Objects.requireNonNull(event, "event must not be null");
        return new BroadcastItem(Kind.WINDOW, event.deviceId(), event.samples());
    }

    public void BroadcastItem(Kind kind, String deviceId, List<TelemetrySampleEvent> samples) {
        Objects.requireNonNull(kind, "kind must not be null");
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(samples, "samples must not be null");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (samples.isEmpty()) {
            throw new IllegalArgumentException("samples must not be empty");
        }
        samples = List.copyOf(samples);
    }
}
