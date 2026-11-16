package com.blackboard.telemetry.ingestion.domain;

import java.util.Objects;

public record ValidatedSampleEvent(TelemetrySample sample, String correlationId) {

    public ValidatedSampleEvent(TelemetrySample sample, String correlationId) {
        Objects.requireNonNull(sample, "sample");
        Objects.requireNonNull(correlationId, "correlationId");
        if (sample.status() == ValidationStatus.UNVALIDATED) {
            throw new IllegalArgumentException("sample must be validated");
        }
        if (correlationId.isBlank()) {
            throw new IllegalArgumentException("correlationId must not be blank");
        }
    }
}
