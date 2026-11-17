package com.pulsestream.telemetry.validation.domain;

import java.time.Instant;

public record TelemetrySample(String deviceId, String metric, Instant tDevice, Instant tIngress, double value, String status, String correlationId) {

    public static final String STATUS_PENDING = "PENDING";

    public static final String STATUS_VALID = "VALID";

    public static final String STATUS_VALIDATION_FAILED = "VALIDATION_FAILED";

    public TelemetrySample withIngress(Instant tIngress) {
        return new TelemetrySample(deviceId, metric, tDevice, tIngress, value, status, correlationId);
    }

    public TelemetrySample withStatus(String status) {
        return new TelemetrySample(deviceId, metric, tDevice, tIngress, value, status, correlationId);
    }
}
