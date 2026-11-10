package com.pulsestream.telemetry.intake.application;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import com.pulsestream.telemetry.intake.domain.SensorMetricBoundaryPolicy;
import com.pulsestream.telemetry.intake.domain.ValidationStatus;
import com.pulsestream.telemetry.intake.application.port.in.IngestTelemetryUseCase;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;

public class IngestTelemetryService {

    private final SensorMetricBoundaryPolicy policy;

    private final BoundedEventChannel<TelemetrySampleEvent> validatedSamples;

    public IngestTelemetryService(SensorMetricBoundaryPolicy policy, BoundedEventChannel<TelemetrySampleEvent> validatedSamples) {
        this.policy = policy;
        this.validatedSamples = validatedSamples;
    }

    public Mono<Integer> ingest(IngressPacket packet) {
        return Flux.fromIterable(packet.samples()).map(policy::validate).map(validated -> new TelemetrySampleEvent(validated.deviceId(), validated.metric(), validated.value(), validated.tDevice(), validated.tIngress(), validated.status() == ValidationStatus.VALID ? TelemetrySampleEvent.VALID : TelemetrySampleEvent.VALIDATION_FAILED)).concatMap(event -> validatedSamples.publish(event).thenReturn(1)).reduce(0, Integer::sum);
    }
}
