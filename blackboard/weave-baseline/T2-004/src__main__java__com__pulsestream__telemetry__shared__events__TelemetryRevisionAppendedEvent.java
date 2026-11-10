package com.pulsestream.telemetry.shared.events;

import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

public record TelemetryRevisionAppendedEvent(UUID recordId, String deviceId, String metric, Instant tDevice, int revision) {

    public TelemetryRevisionAppendedEvent {
        Objects.requireNonNull(recordId, "recordId must not be null");
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(metric, "metric must not be null");
        Objects.requireNonNull(tDevice, "tDevice must not be null");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be blank");
        }
        if (revision < 1) {
            throw new IllegalArgumentException("revision must be >= 1");
        }
    }

    public void TelemetryRevisionAppendedEvent(UUID recordId, String deviceId, String metric, Instant tDevice, int revision) {
        Objects.requireNonNull(recordId, "recordId must not be null");
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(metric, "metric must not be null");
        Objects.requireNonNull(tDevice, "tDevice must not be null");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be blank");
        }
        if (revision < 1) {
            throw new IllegalArgumentException("revision must be >= 1");
        }
    }
}
