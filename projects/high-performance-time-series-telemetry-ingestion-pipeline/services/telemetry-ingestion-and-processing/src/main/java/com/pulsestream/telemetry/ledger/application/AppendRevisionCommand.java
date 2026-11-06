package com.pulsestream.telemetry.ledger.application;

import com.pulsestream.telemetry.ledger.domain.TelemetryEventKey;

public record AppendRevisionCommand(TelemetryEventKey key, double value) {
}
