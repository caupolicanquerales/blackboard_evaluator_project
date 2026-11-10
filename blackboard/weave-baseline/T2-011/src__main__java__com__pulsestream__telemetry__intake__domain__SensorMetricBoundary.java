package com.pulsestream.telemetry.intake.domain;

public record SensorMetricBoundary(String metric, Double min, Double max) {

    public SensorMetricBoundary {
        if (metric == null || metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be blank");
        }
        if (min != null && max != null && min > max) {
            throw new IllegalArgumentException("min must not exceed max");
        }
    }

    public boolean contains(double value) {
        if (Double.isNaN(value) || Double.isInfinite(value)) {
            return false;
        }
        boolean aboveMin = min == null || value >= min;
        boolean belowMax = max == null || value <= max;
        return aboveMin && belowMax;
    }
}
