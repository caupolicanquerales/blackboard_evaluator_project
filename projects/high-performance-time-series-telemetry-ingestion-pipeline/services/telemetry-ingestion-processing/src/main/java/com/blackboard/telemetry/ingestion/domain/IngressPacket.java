package com.blackboard.telemetry.ingestion.domain;

import java.util.List;
import java.util.Objects;

public record IngressPacket(String deviceId, SourceKind sourceKind, List<TelemetrySample> samples) {

    public IngressPacket {
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(sourceKind, "sourceKind must not be null");
        Objects.requireNonNull(samples, "samples must not be null");
        if (deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (samples.isEmpty()) {
            throw new IllegalArgumentException("samples must not be empty");
        }
        samples = List.copyOf(samples);
    }
}
