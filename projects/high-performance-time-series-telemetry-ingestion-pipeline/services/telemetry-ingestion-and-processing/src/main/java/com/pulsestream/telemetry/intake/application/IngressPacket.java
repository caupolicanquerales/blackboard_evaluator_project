package com.pulsestream.telemetry.intake.application;

import java.time.Instant;
import java.util.List;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;

public record IngressPacket(String deviceId, Instant tIngress, List<TelemetrySample> samples) {

    public IngressPacket {
        if (deviceId == null || deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (tIngress == null) {
            throw new IllegalArgumentException("tIngress must not be null");
        }
        if (samples == null || samples.isEmpty()) {
            throw new IllegalArgumentException("samples must not be null or empty");
        }
        List<TelemetrySample> copy = List.copyOf(samples);
        for (TelemetrySample sample : copy) {
            if (!deviceId.equals(sample.deviceId())) {
                throw new IllegalArgumentException("sample deviceId must match packet deviceId");
            }
        }
        samples = copy;
    }

    public void IngressPacket(String deviceId, Instant tIngress, List<TelemetrySample> samples) {
        if (deviceId == null || deviceId.isBlank()) {
            throw new IllegalArgumentException("deviceId must not be blank");
        }
        if (tIngress == null) {
            throw new IllegalArgumentException("tIngress must not be null");
        }
        if (samples == null || samples.isEmpty()) {
            throw new IllegalArgumentException("samples must not be null or empty");
        }
        List<TelemetrySample> copy = List.copyOf(samples);
        for (TelemetrySample sample : copy) {
            if (!deviceId.equals(sample.deviceId())) {
                throw new IllegalArgumentException("sample deviceId must match packet deviceId");
            }
        }
        samples = copy;
    }
}
