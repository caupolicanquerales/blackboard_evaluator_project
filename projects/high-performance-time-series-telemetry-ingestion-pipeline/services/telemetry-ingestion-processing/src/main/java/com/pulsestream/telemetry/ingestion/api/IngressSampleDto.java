package com.pulsestream.telemetry.ingestion.api;

import jakarta.validation.constraints.NotBlank;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;

public record IngressSampleDto(@NotBlank String deviceId, @NotBlank String metric, long tDeviceEpochMs, double value) {

    public TelemetrySample toDomain(long tIngressEpochMs) {
        return new TelemetrySample(deviceId, metric, tDeviceEpochMs, value, tIngressEpochMs, TelemetrySample.VALID);
    }
}
