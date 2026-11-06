package com.pulsestream.telemetry.reordering.domain;

import java.time.Instant;

public record ValidatedTelemetryEvent(String metric, Instant timestamp, double value) {
}
