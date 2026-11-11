package com.pulsestream.telemetry.ingestion.domain;

import com.pulsestream.telemetry.shared.config.TelemetryProperties;

public class SampleValidator {

    private final TelemetryProperties properties;

    public SampleValidator(TelemetryProperties properties) {
        this.properties = java.util.Objects.requireNonNull(properties, "properties must not be null");
    }

    public TelemetrySample validate(TelemetrySample sample) {
        boolean valid = properties.boundsFor(sample.metric()).map(bounds -> sample.value() >= bounds.min() && sample.value() <= bounds.max()).orElse(false);
        return sample.withStatus(valid ? TelemetrySample.VALID : TelemetrySample.VALIDATION_FAILED);
    }
}
