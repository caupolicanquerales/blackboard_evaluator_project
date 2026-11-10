package com.pulsestream.telemetry.intake.domain;

public record SensorMetricBoundary(String metric, Double min, Double max) {

    public SensorMetricBoundary {
        if (metric == null || metric.isBlank()) {
            throw new IllegalArgumentException("metric must not be blank");
        }
        if (min != null && max != null && min.doubleValue() > max.doubleValue()) {
            throw new IllegalArgumentException("min must not exceed max");
        }
    }

    public boolean contains(double value) {
        if (Double.isNaN(value) || Double.isInfinite(value)) {
            return false;
        }
        if (min != null && value < min.doubleValue()) {
            return false;
        }
        return max == null || value <= max.doubleValue();
    }
}
