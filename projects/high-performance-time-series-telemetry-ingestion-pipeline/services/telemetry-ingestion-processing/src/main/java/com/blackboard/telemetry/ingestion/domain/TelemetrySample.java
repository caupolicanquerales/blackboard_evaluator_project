package com.blackboard.telemetry.ingestion.domain;

import java.time.Instant;
import java.util.Objects;

public record TelemetrySample(String deviceId, MetricKind metric, Instant tDevice, Instant tIngress, double value, ValidationStatus status) {

    public TelemetrySample(String deviceId, MetricKind metric, Instant tDevice, Instant tIngress, double value, ValidationStatus status) {
        this.deviceId = Objects.requireNonNull(deviceId, "deviceId");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        this.metric = Objects.requireNonNull(metric, "metric");
        this.tDevice = Objects.requireNonNull(tDevice, "tDevice");
        this.tIngress = Objects.requireNonNull(tIngress, "tIngress");
        this.value = value;
        this.status = Objects.requireNonNull(status, "status");
    }

    public TelemetrySample withStatus(ValidationStatus status) {
        return new TelemetrySample(deviceId, metric, tDevice, tIngress, value, status);
    }
}
