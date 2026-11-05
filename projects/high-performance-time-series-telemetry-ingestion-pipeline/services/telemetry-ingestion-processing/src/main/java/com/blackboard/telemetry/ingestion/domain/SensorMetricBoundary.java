package com.blackboard.telemetry.ingestion.domain;

import java.util.Objects;

public class SensorMetricBoundary {

    public TelemetrySample validate(TelemetrySample sample) {
        Objects.requireNonNull(sample, "sample must not be null");
        boolean withinLimits = switch(sample.metric()) {
            case "heart_rate" ->
                sample.value() >= 30.0 && sample.value() <= 240.0;
            case "power" ->
                sample.value() >= 0.0 && sample.value() <= 2500.0;
            case "cadence" ->
                sample.value() >= 0.0 && sample.value() <= 220.0;
            case "swim_pace" ->
                sample.value() > 45.0;
            default ->
                throw new IllegalArgumentException("Unknown metric: " + sample.metric());
        };
        ValidationStatus status = withinLimits ? ValidationStatus.VALID : ValidationStatus.VALIDATION_FAILED;
        return sample.withStatus(status);
    }
}
