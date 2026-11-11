package com.pulsestream.telemetry.ingestion.application;

import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import com.pulsestream.telemetry.ingestion.domain.SampleValidator;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;

@Service
public class IngestSamplesUseCase {

    private final SampleValidator validator;

    private final TelemetryEventBus eventBus;

    public IngestSamplesUseCase(SampleValidator validator, TelemetryEventBus eventBus) {
        this.validator = validator;
        this.eventBus = eventBus;
    }

    public Flux<TelemetrySample> ingest(Flux<TelemetrySample> samples) {
        return samples.map(validator::validate).concatMap(checked -> eventBus.publish(checked).thenReturn(checked));
    }
}
