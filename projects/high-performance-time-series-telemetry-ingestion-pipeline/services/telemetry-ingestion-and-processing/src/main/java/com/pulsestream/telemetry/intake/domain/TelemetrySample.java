package com.pulsestream.telemetry.intake.domain;

import java.time.Instant;

public record TelemetrySample(String deviceId, String metric, double value, Instant tDevice, Instant tIngress) {

    public TelemetrySample {
        if (deviceId == null || deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (metric == null || metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be blank");
        }
        if (tDevice == null) {
            throw new IllegalArgumentException("tDevice must not be null");
        }
        if (tIngress == null) {
            throw new IllegalArgumentException("tIngress must not be null");
        }
    }

    public TelemetrySample(String deviceId, String metric, double value, Instant tDevice) {
        this(deviceId, metric, value, tDevice, tDevice);
    }

    public static TelemetrySample of(String deviceId, String metric, Instant tDevice, double value) {
        return new TelemetrySample(deviceId, metric, value, tDevice, tDevice);
    }
}
