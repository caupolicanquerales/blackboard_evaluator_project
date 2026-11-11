package com.pulsestream.telemetry.reordering.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.reordering.domain.ReorderBuffer;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;

class ReorderingServiceTest {

    private final TelemetryProperties properties = new TelemetryProperties(
            60L, 8, Map.of("temp", new TelemetryProperties.Bounds(-10.0, 50.0)));

    private TelemetrySample at(long tDevice, String status) {
        return new TelemetrySample("d1", "temp", tDevice, 20.0, tDevice, status);
    }

    private ReorderingService service(long nowEpochMs) {
        Clock clock = Clock.fixed(Instant.ofEpochMilli(nowEpochMs), ZoneOffset.UTC);
        return new ReorderingService(new ReorderBuffer(properties), clock);
    }

    @Test
    void windows_upstreamCompletesWithinWindow_emitsBufferedSamplesOrdered() {
        ReorderingService service = service(0L);
        Flux<TelemetrySample> input = Flux.just(
                at(3000L, TelemetrySample.VALID), at(1000L, TelemetrySample.VALID), at(2000L, TelemetrySample.VALID));

        List<TelemetrySample> result = service.windows(input).collectList().block();

        assertThat(result).extracting(TelemetrySample::tDeviceEpochMs).containsExactly(1000L, 2000L, 3000L);
    }

    @Test
    void windows_samplesPastWindow_emitsAllInAscendingOrder() {
        ReorderingService service = service(10_000_000L);
        Flux<TelemetrySample> input = Flux.just(
                at(1000L, TelemetrySample.VALID), at(2000L, TelemetrySample.VALID), at(3000L, TelemetrySample.VALID));

        List<TelemetrySample> result = service.windows(input).collectList().block();

        assertThat(result).extracting(TelemetrySample::tDeviceEpochMs).containsExactly(1000L, 2000L, 3000L);
    }

    @Test
    void windows_includesValidationFailedSamples_emitsEachExactlyOnce() {
        ReorderingService service = service(0L);
        TelemetrySample failed = at(2000L, TelemetrySample.VALIDATION_FAILED);
        Flux<TelemetrySample> input = Flux.just(at(3000L, TelemetrySample.VALID), failed, at(1000L, TelemetrySample.VALID));

        List<TelemetrySample> result = service.windows(input).collectList().block();

        assertThat(result).hasSize(3).containsOnlyOnce(failed);
    }

    @Test
    void windows_emptyUpstream_completesEmpty() {
        ReorderingService service = service(0L);

        List<TelemetrySample> result = service.windows(Flux.<TelemetrySample>empty()).collectList().block();

        assertThat(result).isEmpty();
    }
}
