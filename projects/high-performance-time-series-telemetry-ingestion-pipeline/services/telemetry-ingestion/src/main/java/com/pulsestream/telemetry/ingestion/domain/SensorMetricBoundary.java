package com.pulsestream.telemetry.ingestion.domain;

public class SensorMetricBoundary {

    private static final String SWIM_PACE_METRIC = "swim_pace";
    private static final double SWIM_PACE_EXCLUSIVE_MINIMUM = 45.0;

    public ValidationStatus check(String metric, double value) {
        return isAcceptable(metric, value) ? ValidationStatus.VALIDATED : ValidationStatus.VALIDATION_FAILED;
    }

    private static boolean isAcceptable(String metric, double value) {
        if (!Double.isFinite(value)) {
            return false;
        }
        return !SWIM_PACE_METRIC.equals(metric) || value > SWIM_PACE_EXCLUSIVE_MINIMUM;
    }
}
