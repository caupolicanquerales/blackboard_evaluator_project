package com.pulsestream.telemetry.ledger.application;

import com.pulsestream.telemetry.ledger.domain.TelemetryRevisionAppended;

public interface TelemetryRevisionEventPublisher {

    void publish(TelemetryRevisionAppended event);
}
