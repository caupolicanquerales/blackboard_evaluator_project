package com.pulsestream.telemetry.reordering.domain;

import java.time.Instant;
import java.util.List;

public record TelemetryWindowOrdered(String metric, Instant windowStart, Instant windowEnd, List<ValidatedTelemetryEvent> samples) {
}
