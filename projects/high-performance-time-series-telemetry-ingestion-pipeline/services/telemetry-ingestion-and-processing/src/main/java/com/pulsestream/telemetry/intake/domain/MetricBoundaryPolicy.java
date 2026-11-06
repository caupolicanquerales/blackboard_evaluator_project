package com.pulsestream.telemetry.intake.domain;

import java.util.Map;

public class MetricBoundaryPolicy {

    private final Map<String, MetricBoundary> boundaries;

    public MetricBoundaryPolicy(Map<String, MetricBoundary> boundaries) {
        this.boundaries = Map.copyOf(boundaries);
    }

    public boolean isWithinBounds(TelemetrySample sample) {
        return validate(sample) == ValidationStatus.VALID;
    }

    public ValidationStatus validate(TelemetrySample sample) {
        MetricBoundary boundary = boundaries.get(sample.metric());
        if (boundary == null) {
            return ValidationStatus.UNDEFINED_BOUNDARY;
        }
        if (sample.value() < boundary.min() || sample.value() > boundary.max()) {
            return ValidationStatus.OUT_OF_BOUNDS;
        }
        return ValidationStatus.VALID;
    }
}
