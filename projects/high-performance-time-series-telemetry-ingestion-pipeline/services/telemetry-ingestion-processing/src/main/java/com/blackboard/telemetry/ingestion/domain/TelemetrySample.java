package com.blackboard.telemetry.ingestion.domain;

import java.time.Instant;

public record TelemetrySample(String deviceId, String metric, Instant tDevice, Instant tIngress, double value) {
}
