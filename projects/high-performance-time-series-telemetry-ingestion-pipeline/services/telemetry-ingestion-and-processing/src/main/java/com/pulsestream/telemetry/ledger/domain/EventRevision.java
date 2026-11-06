package com.pulsestream.telemetry.ledger.domain;

import java.time.Instant;
import java.util.Objects;

public record EventRevision(String deviceId, String metric, Instant tDevice, long revision, Instant tIngress, String validationStatus, String rawPayload) {

    public EventRevision {
        Objects.requireNonNull(deviceId, "deviceId");
        Objects.requireNonNull(metric, "metric");
        Objects.requireNonNull(tDevice, "tDevice");
        Objects.requireNonNull(tIngress, "tIngress");
        Objects.requireNonNull(validationStatus, "validationStatus");
        Objects.requireNonNull(rawPayload, "rawPayload");
        if (revision < 1) {
            throw new IllegalArgumentException("revision must be >= 1");
        }
    }

    public EventRevision nextRevision() {
        return new EventRevision(deviceId, metric, tDevice, revision + 1, tIngress, validationStatus, rawPayload);
    }
    
    public EventRevision(String deviceId, String metric, Instant tDevice, long revision, double value) {
        this(deviceId, metric, tDevice, revision, tDevice, "VALID", String.valueOf(value));
    }
}
