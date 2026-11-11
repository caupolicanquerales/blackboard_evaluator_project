package com.pulsestream.telemetry.ingestion.domain;

public record TelemetrySample(String deviceId, String metric, long tDeviceEpochMs, double value, long tIngressEpochMs, String validationStatus) {

    public static final String VALID = "VALID";

    public static final String VALIDATION_FAILED = "VALIDATION_FAILED";

    public TelemetrySample {
        if (deviceId == null || deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (metric == null || metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be blank");
        }
        if (validationStatus == null) {
            throw new IllegalArgumentException("validationStatus must not be null");
        }
    }

    public boolean isValidationFailed() {
        return VALIDATION_FAILED.equals(validationStatus);
    }

    public TelemetrySample withStatus(String status) {
        return new TelemetrySample(deviceId, metric, tDeviceEpochMs, value, tIngressEpochMs, status);
    }
}
