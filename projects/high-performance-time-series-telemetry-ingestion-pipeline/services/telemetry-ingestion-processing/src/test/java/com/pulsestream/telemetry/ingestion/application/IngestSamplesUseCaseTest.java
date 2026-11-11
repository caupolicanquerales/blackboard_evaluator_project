package com.pulsestream.telemetry.ingestion.application;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ingestion.domain.SampleValidator;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class IngestSamplesUseCaseTest {

    @Mock
    private SampleValidator validator;

    @Mock
    private TelemetryEventBus eventBus;

    private static TelemetrySample sample(String device, String status) {
        return new TelemetrySample(device, "temp", 1L, 1.0, 2L, status);
    }

    @Test
    void ingest_validAndFailedSamples_emitsValidatedInOrderAndPublishesEach() {
        TelemetrySample a = sample("a", TelemetrySample.VALID);
        TelemetrySample b = sample("b", TelemetrySample.VALID);
        TelemetrySample aChecked = a.withStatus(TelemetrySample.VALID);
        TelemetrySample bFailed = b.withStatus(TelemetrySample.VALIDATION_FAILED);
        when(validator.validate(a)).thenReturn(aChecked);
        when(validator.validate(b)).thenReturn(bFailed);
        when(eventBus.publish(any())).thenReturn(Mono.empty());
        IngestSamplesUseCase useCase = new IngestSamplesUseCase(validator, eventBus);

        StepVerifier.create(useCase.ingest(Flux.just(a, b)))
                .expectNext(aChecked, bFailed)
                .expectComplete()
                .verify(Duration.ofSeconds(5));

        verify(eventBus, times(1)).publish(aChecked);
        verify(eventBus, times(1)).publish(bFailed);
    }

    @Test
    void ingest_emptyInput_completesWithoutPublishing() {
        IngestSamplesUseCase useCase = new IngestSamplesUseCase(validator, eventBus);

        StepVerifier.create(useCase.ingest(Flux.empty()))
                .expectComplete()
                .verify(Duration.ofSeconds(5));

        verify(eventBus, times(0)).publish(any());
    }
}
