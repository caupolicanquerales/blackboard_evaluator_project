package com.blackboard.telemetry.eventstore.domain;

import java.time.Instant;

public record TelemetryRecord(String deviceId, String metric, Instant tDevice, Instant tIngress, double value, String status, long revision) {
}
