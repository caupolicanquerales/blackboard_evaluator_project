package com.pulsestream.telemetry.ingestion.domain;

import com.pulsestream.telemetry.shared.config.TelemetryProperties;

public class SampleValidator {

    private final TelemetryProperties properties;

    public SampleValidator(TelemetryProperties properties) {
        this.properties = properties;
    }

    public TelemetrySample validate(TelemetrySample sample) {
        return properties.boundsFor(sample.metric()).filter(bounds -> sample.value() >= bounds.min() && sample.value() <= bounds.max()).map(bounds -> sample.withStatus(TelemetrySample.VALID)).orElseGet(() -> sample.withStatus(TelemetrySample.VALIDATION_FAILED));
    }
}
