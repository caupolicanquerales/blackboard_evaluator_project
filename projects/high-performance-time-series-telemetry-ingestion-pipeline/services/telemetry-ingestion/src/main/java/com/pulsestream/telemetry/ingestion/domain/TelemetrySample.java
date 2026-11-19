package com.pulsestream.telemetry.ingestion.domain;

import java.time.Instant;

public record TelemetrySample(String deviceId, String metric, Instant tDevice, Instant tIngress, double value, ValidationStatus status, String payload) {
}
