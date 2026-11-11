package com.pulsestream.telemetry.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class TelemetryEventBusTest {

    private static final TelemetrySample SAMPLE =
            new TelemetrySample("d1", "temp", 1000L, 20.0, 1001L, TelemetrySample.VALID);

    @Test
    void publish_sample_returnsEmptyMono() {
        TelemetryEventBus bus = mock(TelemetryEventBus.class);
        when(bus.publish(SAMPLE)).thenReturn(Mono.empty());

        Mono<Void> result = bus.publish(SAMPLE);

        StepVerifier.create(result).verifyComplete();
        verify(bus).publish(SAMPLE);
    }

    @Test
    void stream_subscribed_returnsFluxOfSamples() {
        TelemetryEventBus bus = mock(TelemetryEventBus.class);
        when(bus.stream()).thenReturn(Flux.just(SAMPLE));

        Flux<TelemetrySample> result = bus.stream();

        assertThat(result).isNotNull();
        StepVerifier.create(result).expectNext(SAMPLE).verifyComplete();
    }
}
