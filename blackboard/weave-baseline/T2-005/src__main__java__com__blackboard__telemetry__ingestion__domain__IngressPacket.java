package com.blackboard.telemetry.ingestion.domain;

import java.util.List;
import java.util.Objects;

public record IngressPacket(String deviceId, SourceKind sourceKind, List<TelemetrySample> samples) {

    public IngressPacket(String deviceId, SourceKind sourceKind, List<TelemetrySample> samples) {
        Objects.requireNonNull(deviceId, "deviceId");
        Objects.requireNonNull(sourceKind, "sourceKind");
        Objects.requireNonNull(samples, "samples");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (samples.isEmpty()) {
            throw new IllegalArgumentException("samples must not be empty");
        }
        samples = List.copyOf(samples);
    }
}
