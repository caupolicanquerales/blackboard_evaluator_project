package com.blackboard.telemetry.ingestion.domain;

import java.util.Objects;

public record SensorMetricBoundary(MetricKind metric, double min, double max, boolean minExclusive, boolean enabled) {

    public SensorMetricBoundary {
        Objects.requireNonNull(metric, "metric must not be null");
        if (min > max) {
            throw new IllegalArgumentException("min must be <= max");
        }
    }

    public boolean accepts(double value) {
        if (!enabled) {
            return true;
        }
        boolean aboveMin = minExclusive ? value > min : value >= min;
        return aboveMin && value <= max;
    }
}
