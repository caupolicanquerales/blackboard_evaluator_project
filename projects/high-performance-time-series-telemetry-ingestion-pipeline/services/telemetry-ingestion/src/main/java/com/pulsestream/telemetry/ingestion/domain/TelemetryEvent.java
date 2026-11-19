package com.pulsestream.telemetry.ingestion.domain;

import java.time.Instant;

public record TelemetryEvent(int schemaVersion, Type type, String eventKey, String deviceId, String metric, Instant tDevice, int revision, double value, ValidationStatus status, String publisherId) {

    public TelemetryEvent {
        if (revision < 1) {
            throw new IllegalArgumentException("revision must be >= 1");
        }
    }

    public enum Type {

        SAMPLE,
        TELEMETRY_VALIDATED,
        SAMPLE_VALIDATED,
        SAMPLE_VALIDATION_FAILED,
        BACKFILL_REORDERED,
        REVISION_APPENDED
    }

    public static String keyOf(String deviceId, String metric, Instant tDevice, int revision) {
        return deviceId + "|" + metric + "|" + tDevice + "|" + revision;
    }
}
