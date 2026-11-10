package com.pulsestream.telemetry.ledger.interfaces;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

public record TelemetryRecordResponse(UUID id, String deviceId, String metric, double value, Instant tDevice, Instant tIngress, String validationStatus, int revision, UUID supersedesId) {

    public TelemetryRecordResponse(UUID id, String deviceId, String metric, double value, Instant tDevice, Instant tIngress, String validationStatus, int revision) {
        this(id, deviceId, metric, value, tDevice, tIngress, validationStatus, revision, null);
    }

    public TelemetryRecordResponse from(TelemetryRecord record) {
        Objects.requireNonNull(record, "record must not be null");
        return new TelemetryRecordResponse(record.id(), record.deviceId(), record.metric(), record.value(), record.tDevice(), record.tIngress(), record.validationStatus(), record.revision(), record.supersedesId());
    }
}
