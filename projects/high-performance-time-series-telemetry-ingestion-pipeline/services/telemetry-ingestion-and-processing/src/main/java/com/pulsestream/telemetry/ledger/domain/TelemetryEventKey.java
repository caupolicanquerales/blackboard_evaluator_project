package com.pulsestream.telemetry.ledger.domain;

import java.time.Instant;

public record TelemetryEventKey(String deviceId, String metric, Instant timestamp) {
}
