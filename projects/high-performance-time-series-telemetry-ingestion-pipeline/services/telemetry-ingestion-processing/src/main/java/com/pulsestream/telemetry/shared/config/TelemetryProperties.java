package com.pulsestream.telemetry.shared.config;

import java.util.Map;
import java.util.Optional;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("pulsestream.telemetry")
public record TelemetryProperties(long reorderWindowSeconds, int busBufferCapacity, Map<String, TelemetryProperties.Bounds> metricBounds) {

    public TelemetryProperties {
        if (reorderWindowSeconds <= 0) {
            throw new IllegalArgumentException("reorderWindowSeconds must be > 0");
        }
        if (busBufferCapacity <= 0) {
            throw new IllegalArgumentException("busBufferCapacity must be > 0");
        }
        metricBounds = metricBounds == null ? Map.of() : Map.copyOf(metricBounds);
    }

    public Optional<TelemetryProperties.Bounds> boundsFor(String metric) {
        return Optional.ofNullable(metricBounds.get(metric));
    }

    public record Bounds(double min, double max) {
    }
}
