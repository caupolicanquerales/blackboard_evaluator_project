package com.blackboard.telemetry.shared.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import com.blackboard.telemetry.ingestion.domain.SensorMetricBoundary;
import java.time.Duration;
import java.util.List;
import java.util.Objects;

@ConfigurationProperties(prefix = "telemetry")
public record TelemetryProperties(Duration reorderWindow, int reorderBufferCapacity, int validatedStreamCapacity, int broadcastCapacity, Duration emitRetryTimeout, List<SensorMetricBoundary> boundaries) {

    public TelemetryProperties(Duration reorderWindow, int reorderBufferCapacity, int validatedStreamCapacity, int broadcastCapacity, Duration emitRetryTimeout, List<SensorMetricBoundary> boundaries) {
        Objects.requireNonNull(reorderWindow, "reorderWindow");
        Objects.requireNonNull(emitRetryTimeout, "emitRetryTimeout");
        Objects.requireNonNull(boundaries, "boundaries");
        if (reorderWindow.isZero() || reorderWindow.isNegative()) {
            throw new IllegalArgumentException("reorderWindow must be positive");
        }
        if (reorderBufferCapacity < 1) {
            throw new IllegalArgumentException("reorderBufferCapacity must be >= 1");
        }
        if (validatedStreamCapacity < 1) {
            throw new IllegalArgumentException("validatedStreamCapacity must be >= 1");
        }
        if (broadcastCapacity < 1) {
            throw new IllegalArgumentException("broadcastCapacity must be >= 1");
        }
        if (emitRetryTimeout.isZero() || emitRetryTimeout.isNegative()) {
            throw new IllegalArgumentException("emitRetryTimeout must be positive");
        }
        boundaries = List.copyOf(boundaries);
    }
}
