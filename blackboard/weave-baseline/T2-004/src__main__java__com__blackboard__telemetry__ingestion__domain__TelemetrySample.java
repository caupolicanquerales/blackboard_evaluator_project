package com.blackboard.telemetry.ingestion.domain;

import java.time.Instant;
import java.util.Objects;

public record TelemetrySample(String deviceId, MetricKind metric, Instant tDevice, Instant tIngress, double value, ValidationStatus status) {

    public TelemetrySample withStatus(ValidationStatus status) {
        return new TelemetrySample(deviceId, metric, tDevice, tIngress, value, status);
    }

    public void TelemetrySample(String deviceId, MetricKind metric, Instant tDevice, Instant tIngress, double value, ValidationStatus status) {
        Objects.requireNonNull(deviceId, "deviceId");
        Objects.requireNonNull(metric, "metric");
        Objects.requireNonNull(tDevice, "tDevice");
        Objects.requireNonNull(tIngress, "tIngress");
        Objects.requireNonNull(status, "status");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
    }
}
