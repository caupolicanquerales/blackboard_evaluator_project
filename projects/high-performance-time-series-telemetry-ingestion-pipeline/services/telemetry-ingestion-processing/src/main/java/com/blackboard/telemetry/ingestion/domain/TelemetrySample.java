package com.blackboard.telemetry.ingestion.domain;

import java.time.Instant;

public record TelemetrySample(
        String deviceId,
        Instant tDevice,
        Instant tIngress,
        String metric,
        double value,
        ValidationStatus status) {

    public TelemetrySample(String deviceId, Instant tDevice, Instant tIngress, String metric, double value) {
        this(deviceId, tDevice, tIngress, metric, value, null);
    }

    public TelemetrySample(String deviceId, Instant tDevice, String metric, double value) {
        this(deviceId, tDevice, null, metric, value, null);
    }

    public TelemetrySample withIngress(Instant ingress) {
        return new TelemetrySample(deviceId, tDevice, ingress, metric, value, status);
    }

    public TelemetrySample withStatus(ValidationStatus newStatus) {
        return new TelemetrySample(deviceId, tDevice, tIngress, metric, value, newStatus);
    }
}
