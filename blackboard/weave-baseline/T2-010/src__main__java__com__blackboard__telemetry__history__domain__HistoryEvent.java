package com.blackboard.telemetry.history.domain;

import java.util.Objects;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;

public record HistoryEvent(HistoryEventType type, TelemetrySample sample, int revisionNo, int windowSize, String correlationId) {

    public void HistoryEvent(HistoryEventType type, TelemetrySample sample, int revisionNo, int windowSize, String correlationId) {
        Objects.requireNonNull(type, "type");
        Objects.requireNonNull(sample, "sample");
        Objects.requireNonNull(correlationId, "correlationId");
        if (revisionNo < 0) {
            throw new IllegalArgumentException("revisionNo must be >= 0");
        }
        if (windowSize < 0) {
            throw new IllegalArgumentException("windowSize must be >= 0");
        }
        if (correlationId.isBlank()) {
            throw new IllegalArgumentException("correlationId must not be blank");
        }
    }
}
