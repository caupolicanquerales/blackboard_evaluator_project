package com.pulsestream.telemetry.ledger.domain;

public record TelemetryRevision(TelemetryEventKey key, long revision, double value) {
}
