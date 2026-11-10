package com.pulsestream.telemetry.intake.domain;

import java.time.Instant;

public record TelemetrySample(String deviceId, String metric, double value, Instant tDevice, Instant tIngress, ValidationStatus status) {

    public TelemetrySample {
        if (deviceId == null || deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be null or blank");
        }
        if (metric == null || metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be null or blank");
        }
        if (tDevice == null) {
            throw new IllegalArgumentException("tDevice must not be null");
        }
        if (tIngress == null) {
            throw new IllegalArgumentException("tIngress must not be null");
        }
        if (status == null) {
            throw new IllegalArgumentException("status must not be null");
        }
    }

    public static TelemetrySample unvalidated(String deviceId, String metric, double value, Instant tDevice, Instant tIngress) {
        return new TelemetrySample(deviceId, metric, value, tDevice, tIngress, ValidationStatus.UNVALIDATED);
    }

    public TelemetrySample withStatus(ValidationStatus newStatus) {
        return new TelemetrySample(deviceId, metric, value, tDevice, tIngress, newStatus);
    }
}
