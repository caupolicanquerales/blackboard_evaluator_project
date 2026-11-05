package com.blackboard.telemetry.ingestion.application;

import java.time.Clock;
import java.util.Objects;
import com.blackboard.telemetry.ingestion.domain.SensorMetricBoundary;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidated;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidationFailed;
import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public class IngestTelemetryService {

    private final SensorMetricBoundary boundary;

    private final TelemetryEventPublisher publisher;

    private final Clock clock;

    public IngestTelemetryService(SensorMetricBoundary boundary, TelemetryEventPublisher publisher, Clock clock) {
        this.boundary = Objects.requireNonNull(boundary, "boundary must not be null");
        this.publisher = Objects.requireNonNull(publisher, "publisher must not be null");
        this.clock = Objects.requireNonNull(clock, "clock must not be null");
    }

    private Mono<TelemetrySample> publish(TelemetrySample sample) {
        ValidationStatus status = ValidationStatus.valueOf(sample.status().name());
        if (status == ValidationStatus.VALID) {
            return publisher.publishValidated(new TelemetrySampleValidated(sample.deviceId(), sample.tDevice(), sample.tIngress(), sample.metric(), sample.value(), status)).thenReturn(sample);
        }
        return publisher.publishValidationFailed(new TelemetrySampleValidationFailed(sample.deviceId(), sample.tDevice(), sample.tIngress(), sample.metric(), sample.value(), status)).thenReturn(sample);
    }

    public Flux<TelemetrySample> ingest(Flux<TelemetrySample> samples) {
        Objects.requireNonNull(samples, "samples must not be null");
        return samples.map(sample -> boundary.validate(sample.withIngress(clock.instant()))).concatMap(validated -> Mono.just(validated).flatMap(this::publish));
    }
}
