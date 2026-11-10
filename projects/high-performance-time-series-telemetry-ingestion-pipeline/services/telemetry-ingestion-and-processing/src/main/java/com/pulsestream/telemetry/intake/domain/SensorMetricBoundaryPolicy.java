package com.pulsestream.telemetry.intake.domain;

import java.util.Locale;
import java.util.Map;

public class SensorMetricBoundaryPolicy {

    private final Map<String, SensorMetricBoundary> boundariesByMetric;

    public SensorMetricBoundaryPolicy(Map<String, SensorMetricBoundary> boundariesByMetric) {
        this.boundariesByMetric = Map.copyOf(boundariesByMetric);
    }

    public TelemetrySample validate(TelemetrySample sample) {
        String key = sample.metric() == null ? null : sample.metric().toLowerCase(Locale.ROOT);
        SensorMetricBoundary boundary = key == null ? null : boundariesByMetric.get(key);
        boolean inside = boundary != null && boundary.contains(sample.value());
        return sample.withStatus(inside ? ValidationStatus.VALID : ValidationStatus.VALIDATION_FAILED);
    }
}
