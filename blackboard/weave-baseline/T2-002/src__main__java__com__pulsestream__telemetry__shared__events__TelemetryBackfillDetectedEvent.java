package com.pulsestream.telemetry.shared.events;

import java.util.Objects;

public record TelemetryBackfillDetectedEvent(TelemetrySampleEvent sample, boolean beyondReorderWindow) {

    public void TelemetryBackfillDetectedEvent(TelemetrySampleEvent sample, boolean beyondReorderWindow) {
        Objects.requireNonNull(sample, "sample must not be null");
    }
}
