package com.blackboard.telemetry.shared.events;

import java.time.Instant;
import java.util.Objects;

public class TelemetryEvents {

    private TelemetryEvents() {
    }

    public enum ValidationStatus {

        VALID, VALIDATION_FAILED
    }

    private static String requireDeviceId(String deviceId) {
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        return deviceId;
    }

    public record TelemetrySampleValidated(String deviceId, Instant tDevice, Instant tIngress, String metric, double value, ValidationStatus status) {

        public TelemetrySampleValidated {
            requireDeviceId(deviceId);
            Objects.requireNonNull(tDevice, "tDevice must not be null");
            Objects.requireNonNull(tIngress, "tIngress must not be null");
            Objects.requireNonNull(status, "status must not be null");
        }
    }

    public record TelemetrySampleValidationFailed(String deviceId, Instant tDevice, Instant tIngress, String metric, double value, ValidationStatus status) {

        public TelemetrySampleValidationFailed {
            requireDeviceId(deviceId);
            Objects.requireNonNull(tDevice, "tDevice must not be null");
            Objects.requireNonNull(tIngress, "tIngress must not be null");
            Objects.requireNonNull(status, "status must not be null");
            if (status != ValidationStatus.VALIDATION_FAILED) {
                throw new IllegalArgumentException("status must be VALIDATION_FAILED");
            }
        }
    }

    public record TelemetrySampleOrdered(String deviceId, Instant tDevice, Instant tIngress, String metric, double value, ValidationStatus status) {

        public TelemetrySampleOrdered {
            requireDeviceId(deviceId);
            Objects.requireNonNull(tDevice, "tDevice must not be null");
            Objects.requireNonNull(tIngress, "tIngress must not be null");
            Objects.requireNonNull(status, "status must not be null");
        }
    }

    public record BackfilledSampleReindexed(String deviceId, Instant tDevice, Instant tIngress, String metric, double value, ValidationStatus status) {

        public BackfilledSampleReindexed {
            requireDeviceId(deviceId);
            Objects.requireNonNull(tDevice, "tDevice must not be null");
            Objects.requireNonNull(tIngress, "tIngress must not be null");
            Objects.requireNonNull(status, "status must not be null");
        }
    }

    public record TelemetryWindowBuffered(String deviceId, Instant tDevice, Instant tIngress, String metric, double value, ValidationStatus status) {

        public TelemetryWindowBuffered {
            requireDeviceId(deviceId);
            Objects.requireNonNull(tDevice, "tDevice must not be null");
            Objects.requireNonNull(tIngress, "tIngress must not be null");
            Objects.requireNonNull(status, "status must not be null");
        }
    }

    public record TelemetryRevisionAppended(String deviceId, Instant tDevice, Instant tIngress, String metric, double value, ValidationStatus status) {

        public TelemetryRevisionAppended {
            requireDeviceId(deviceId);
            Objects.requireNonNull(tDevice, "tDevice must not be null");
            Objects.requireNonNull(tIngress, "tIngress must not be null");
            Objects.requireNonNull(status, "status must not be null");
        }
    }
}
