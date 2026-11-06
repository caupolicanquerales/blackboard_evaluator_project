package com.pulsestream.telemetry.intake.domain;

import java.time.Instant;

public record ValidationFailed(TelemetrySample sample) {

    public Instant tIngress() {
        return sample.tIngress();
    }
}
