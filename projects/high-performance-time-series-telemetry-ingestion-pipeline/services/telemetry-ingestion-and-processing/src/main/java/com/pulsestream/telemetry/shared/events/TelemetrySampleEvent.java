package com.pulsestream.telemetry.shared.events;

import java.time.Instant;
import java.util.Objects;

public record TelemetrySampleEvent(String deviceId, String metric, double value, Instant tDevice, Instant tIngress, String validationStatus) {

    public static final String VALID = "VALID";

    public static final String VALIDATION_FAILED = "VALIDATION_FAILED";

    public TelemetrySampleEvent {
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(metric, "metric must not be null");
        Objects.requireNonNull(tDevice, "tDevice must not be null");
        Objects.requireNonNull(tIngress, "tIngress must not be null");
        Objects.requireNonNull(validationStatus, "validationStatus must not be null");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be blank");
        }
        if (!VALID.equals(validationStatus) && !VALIDATION_FAILED.equals(validationStatus)) {
            throw new IllegalArgumentException("unknown validationStatus: " + validationStatus);
        }
    }

    public boolean isValidationFailed() {
        return VALIDATION_FAILED.equals(validationStatus);
    }

    public void TelemetrySampleEvent(String deviceId, String metric, double value, Instant tDevice, Instant tIngress, String validationStatus) {
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(metric, "metric must not be null");
        Objects.requireNonNull(tDevice, "tDevice must not be null");
        Objects.requireNonNull(tIngress, "tIngress must not be null");
        Objects.requireNonNull(validationStatus, "validationStatus must not be null");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be blank");
        }
        if (!VALID.equals(validationStatus) && !VALIDATION_FAILED.equals(validationStatus)) {
            throw new IllegalArgumentException("unknown validationStatus: " + validationStatus);
        }
    }
}
