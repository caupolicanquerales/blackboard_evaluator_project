package com.pulsestream.telemetry.intake.application;

import java.time.Clock;
import reactor.core.publisher.Mono;
import com.pulsestream.telemetry.intake.domain.MetricBoundaryPolicy;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.intake.domain.TelemetrySampleValidated;
import com.pulsestream.telemetry.intake.domain.ValidationFailed;

public class IntakeTelemetryUseCase {

    private final MetricBoundaryPolicy policy;

    private final ReorderingEventPort port;

    private final Clock clock;

    public IntakeTelemetryUseCase(MetricBoundaryPolicy policy, ReorderingEventPort port, Clock clock) {
        this.policy = policy;
        this.port = port;
        this.clock = clock;
    }

    public Mono<Void> ingest(TelemetrySample sample) {
        return Mono.defer(() -> {
            TelemetrySample stamped = new TelemetrySample(sample.deviceId(), sample.metric(), sample.value(), sample.tDevice(), clock.instant());
            Object event = policy.isWithinBounds(stamped) ? new TelemetrySampleValidated(stamped) : new ValidationFailed(stamped);
            return port.publish(event);
        });
    }
}
