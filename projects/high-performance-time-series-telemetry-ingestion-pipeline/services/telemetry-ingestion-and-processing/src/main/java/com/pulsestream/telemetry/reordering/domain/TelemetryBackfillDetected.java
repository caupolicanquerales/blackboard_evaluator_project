package com.pulsestream.telemetry.reordering.domain;

import java.time.Instant;

public record TelemetryBackfillDetected(String metric, Instant timestamp, Instant windowStart) {
}
