package com.pulsestream.telemetry.shared.observability;

import java.time.Instant;

public record AuditEntry(String actor, String action, String outcome, Instant timestamp, String correlationId) {
}
