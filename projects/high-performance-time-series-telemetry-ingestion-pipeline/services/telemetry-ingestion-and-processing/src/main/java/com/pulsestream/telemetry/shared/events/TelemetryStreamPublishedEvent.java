package com.pulsestream.telemetry.shared.events;

import java.time.Instant;
import java.util.Objects;

public record TelemetryStreamPublishedEvent(String kind, String deviceId, int sampleCount, Instant publishedAt) {

    public static final String SAMPLE = "SAMPLE";

    public static final String WINDOW = "WINDOW";

    public TelemetryStreamPublishedEvent {
        Objects.requireNonNull(kind, "kind must not be null");
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(publishedAt, "publishedAt must not be null");
        if (!SAMPLE.equals(kind) && !WINDOW.equals(kind)) {
            throw new IllegalArgumentException("kind must be SAMPLE or WINDOW");
        }
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (sampleCount < 1) {
            throw new IllegalArgumentException("sampleCount must be >= 1");
        }
    }

    public void TelemetryStreamPublishedEvent(String kind, String deviceId, int sampleCount, Instant publishedAt) {
        Objects.requireNonNull(kind, "kind must not be null");
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(publishedAt, "publishedAt must not be null");
        if (!SAMPLE.equals(kind) && !WINDOW.equals(kind)) {
            throw new IllegalArgumentException("kind must be SAMPLE or WINDOW");
        }
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (sampleCount < 1) {
            throw new IllegalArgumentException("sampleCount must be >= 1");
        }
    }
}
