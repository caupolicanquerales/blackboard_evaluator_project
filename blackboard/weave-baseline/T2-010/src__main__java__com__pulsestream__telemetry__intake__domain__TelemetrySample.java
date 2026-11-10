package com.pulsestream.telemetry.intake.domain;

import java.time.Instant;
import java.util.Objects;

public record TelemetrySample(String deviceId, String metric, double value, Instant tDevice, Instant tIngress, ValidationStatus status) {

    public TelemetrySample {
        if (deviceId == null || deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (metric == null || metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be blank");
        }
        Objects.requireNonNull(tDevice, "tDevice must not be null");
        Objects.requireNonNull(tIngress, "tIngress must not be null");
        Objects.requireNonNull(status, "status must not be null");
    }

    public static TelemetrySample unvalidated(String deviceId, String metric, double value, Instant tDevice, Instant tIngress) {
        return new TelemetrySample(deviceId, metric, value, tDevice, tIngress, ValidationStatus.UNVALIDATED);
    }

    public TelemetrySample withStatus(ValidationStatus newStatus) {
        return new TelemetrySample(deviceId, metric, value, tDevice, tIngress, newStatus);
    }
}
