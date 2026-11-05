package com.blackboard.telemetry.eventlog.domain;

import java.time.Instant;
import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;

public record EventRevision(String deviceId, Instant tDevice, int revision, Instant tIngress, ValidationStatus validationStatus, String payload) {

    public EventRevision {
        if (deviceId == null || deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (tDevice == null) {
            throw new IllegalArgumentException("tDevice must not be null");
        }
        if (revision < 0) {
            throw new IllegalArgumentException("revision must not be negative");
        }
        if (tIngress == null) {
            throw new IllegalArgumentException("tIngress must not be null");
        }
        if (validationStatus == null) {
            throw new IllegalArgumentException("validationStatus must not be null");
        }
        if (payload == null) {
            throw new IllegalArgumentException("payload must not be null");
        }
    }

    public static EventRevision first(String deviceId, Instant tDevice, Instant tIngress, ValidationStatus validationStatus, String payload) {
        return new EventRevision(deviceId, tDevice, 0, tIngress, validationStatus, payload);
    }

    public EventRevision nextRevision(Instant newTIngress, ValidationStatus newValidationStatus, String newPayload) {
        return new EventRevision(deviceId, tDevice, revision + 1, newTIngress, newValidationStatus, newPayload);
    }

    public EventRevision correctedBy(Instant newTIngress, ValidationStatus newValidationStatus, String newPayload) {
        return nextRevision(newTIngress, newValidationStatus, newPayload);
    }
}
