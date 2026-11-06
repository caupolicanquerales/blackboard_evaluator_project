package com.pulsestream.telemetry.reordering.domain;

import com.pulsestream.telemetry.intake.domain.TelemetrySample;

public record ReleasedSample(TelemetrySample sample, boolean backfill) {
}
