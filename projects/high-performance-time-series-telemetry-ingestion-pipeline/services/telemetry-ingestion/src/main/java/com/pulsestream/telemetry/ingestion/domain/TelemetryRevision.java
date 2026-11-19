package com.pulsestream.telemetry.ingestion.domain;

import java.time.Instant;

public record TelemetryRevision(String deviceId, String metric, Instant tDevice, int revisionNumber, double value, String reason) {

    public TelemetryRevision {
        if (revisionNumber < 1) {
            throw new IllegalArgumentException("revisionNumber must be >= 1");
        }
    }
}
