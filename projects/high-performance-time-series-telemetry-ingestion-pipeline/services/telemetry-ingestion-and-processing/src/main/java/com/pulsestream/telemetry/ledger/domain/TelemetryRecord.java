package com.pulsestream.telemetry.ledger.domain;

import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

public record TelemetryRecord(UUID id, String deviceId, String metric, double value, Instant tDevice, Instant tIngress, String validationStatus, int revision, UUID supersedesId) {

    public TelemetryRecord {
        Objects.requireNonNull(id, "id must not be null");
        if (deviceId == null || deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (metric == null || metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be blank");
        }
        Objects.requireNonNull(tDevice, "tDevice must not be null");
        Objects.requireNonNull(tIngress, "tIngress must not be null");
        if (validationStatus == null || validationStatus.isBlank()) {
            throw new IllegalArgumentException("validationStatus must not be blank");
        }
        if (revision < 0) {
            throw new IllegalArgumentException("revision must not be negative");
        }
        if ((revision == 0) != (supersedesId == null)) {
            throw new IllegalArgumentException("revision 0 must have no supersedesId and revisions above 0 must have one");
        }
    }

    public static TelemetryRecord original(String deviceId, String metric, double value, Instant tDevice, Instant tIngress, String validationStatus) {
        return new TelemetryRecord(UUID.randomUUID(), deviceId, metric, value, tDevice, tIngress, validationStatus, 0, null);
    }

    public TelemetryRecord reviseWith(double value, Instant tIngress, String validationStatus) {
        return new TelemetryRecord(UUID.randomUUID(), deviceId, metric, value, tDevice, tIngress, validationStatus, revision + 1, id);
    }
}
