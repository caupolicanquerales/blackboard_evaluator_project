package com.blackboard.telemetry.ingestion.application;
import com.blackboard.telemetry.shared.events.TelemetryEvents;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import com.blackboard.telemetry.ingestion.domain.SensorMetricBoundary;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidated;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidationFailed;
import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class IngestTelemetryServiceTest {

    private static final String DEVICE = "device-1";
    private static final Instant T_DEVICE = Instant.parse("2026-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2026-01-01T10:00:05Z");

    @Mock
    private TelemetryEventPublisher publisher;

    private IngestTelemetryService service;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(T_INGRESS, ZoneOffset.UTC);
        service = new IngestTelemetryService(new SensorMetricBoundary(), publisher, clock);
    }

    private static TelemetrySample sample(String metric, double value) {
        return new TelemetrySample(DEVICE, T_DEVICE, metric, value);
    }

    private void stubPublisher() {
        when(publisher.publishValidated(any())).thenReturn(Mono.empty());
        when(publisher.publishValidationFailed(any())).thenReturn(Mono.empty());
    }

    @Test
    void ingest_validSample_publishesValidatedStampedWithIngressTime() {
        when(publisher.publishValidated(any())).thenReturn(Mono.empty());

        StepVerifier.create(service.ingest(Flux.just(sample("heart_rate", 150.0))))
                .expectNextCount(1)
                .verifyComplete();

        ArgumentCaptor<TelemetrySampleValidated> captor = ArgumentCaptor.forClass(TelemetrySampleValidated.class);
        verify(publisher).publishValidated(captor.capture());
        verify(publisher, never()).publishValidationFailed(any());
        assertThat(captor.getValue()).isEqualTo(
                new TelemetrySampleValidated(DEVICE, T_DEVICE, T_INGRESS, "heart_rate", 150.0, ValidationStatus.VALID));
    }

    @Test
    void ingest_sampleOutOfBoundary_publishesValidationFailedRetainingPayload() {
        when(publisher.publishValidationFailed(any())).thenReturn(Mono.empty());

        StepVerifier.create(service.ingest(Flux.just(sample("heart_rate", 400.0))))
                .expectNextCount(1)
                .verifyComplete();

        ArgumentCaptor<TelemetrySampleValidationFailed> captor =
                ArgumentCaptor.forClass(TelemetrySampleValidationFailed.class);
        verify(publisher).publishValidationFailed(captor.capture());
        verify(publisher, never()).publishValidated(any());
        assertThat(captor.getValue()).isEqualTo(new TelemetrySampleValidationFailed(DEVICE, T_DEVICE, T_INGRESS,
                "heart_rate", 400.0, ValidationStatus.VALIDATION_FAILED));
    }

    @Test
    void ingest_sampleAtInclusiveLimit_isPublishedAsValidated() {
        when(publisher.publishValidated(any())).thenReturn(Mono.empty());

        StepVerifier.create(service.ingest(Flux.just(sample("heart_rate", 240.0))))
                .expectNextCount(1)
                .verifyComplete();

        verify(publisher).publishValidated(any());
        verify(publisher, never()).publishValidationFailed(any());
    }

    @Test
    void ingest_mixedSamples_neverDropsAnyAndPublishesEachOnce() {
        stubPublisher();
        Flux<TelemetrySample> samples = Flux.just(
                sample("heart_rate", 150.0),
                sample("power", 3000.0),
                sample("cadence", 90.0),
                sample("heart_rate", 10.0));

        StepVerifier.create(service.ingest(samples)).expectNextCount(4).verifyComplete();

        verify(publisher, times(2)).publishValidated(any());
        verify(publisher, times(2)).publishValidationFailed(any());
    }

    @Test
    void ingest_mixedSamples_preservesArrivalOrderOfPublishedEvents() {
        stubPublisher();
        Flux<TelemetrySample> samples = Flux.just(
                sample("power", 100.0), sample("power", 9999.0), sample("power", 200.0));

        StepVerifier.create(service.ingest(samples)).expectNextCount(3).verifyComplete();

        ArgumentCaptor<TelemetrySampleValidated> valid = ArgumentCaptor.forClass(TelemetrySampleValidated.class);
        verify(publisher, times(2)).publishValidated(valid.capture());
        List<Double> values = valid.getAllValues().stream().map(TelemetrySampleValidated::value).toList();
        assertThat(values).containsExactly(100.0, 200.0);
    }

    @Test
    void ingest_emptyPacket_completesWithoutPublishing() {
        StepVerifier.create(service.ingest(Flux.empty())).verifyComplete();

        verifyNoInteractions(publisher);
    }

    @Test
    void ingest_upstreamError_propagatesErrorSignal() {
        stubPublisher();
        Flux<TelemetrySample> samples = Flux.concat(
                Flux.just(sample("heart_rate", 150.0)),
                Flux.error(new IllegalStateException("packet broken")));

        StepVerifier.create(service.ingest(samples))
                .expectNextCount(1)
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void ingest_publisherFails_propagatesErrorSignal() {
        when(publisher.publishValidated(any())).thenReturn(Mono.error(new IllegalStateException("broker down")));

        StepVerifier.create(service.ingest(Flux.just(sample("heart_rate", 150.0))))
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void ingest_noDownstreamDemand_publishesNothing() {
        StepVerifier.create(service.ingest(Flux.just(sample("heart_rate", 150.0))), 0)
                .expectSubscription()
                .thenCancel()
                .verify();

        verifyNoInteractions(publisher);
    }

    @Test
    void ingest_limitedDemand_requestsBoundedAmountFromUpstream() {
        stubPublisher();
        AtomicLong requested = new AtomicLong();
        Flux<TelemetrySample> upstream = Flux.range(0, 10_000)
                .map(i -> sample("heart_rate", 100.0))
                .doOnRequest(requested::addAndGet);

        StepVerifier.create(service.ingest(upstream), 2)
                .expectNextCount(2)
                .thenCancel()
                .verify();

        assertThat(requested.get()).isLessThan(10_000L);
    }

    @Test
    void ingest_slowConsumer_deliversAllSamplesAsDemandIsGranted() {
        stubPublisher();
        Flux<TelemetrySample> samples = Flux.range(0, 5).map(i -> sample("cadence", 80.0 + i));

        StepVerifier.create(service.ingest(samples), 1)
                .expectNextCount(1)
                .thenRequest(2)
                .expectNextCount(2)
                .thenRequest(2)
                .expectNextCount(2)
                .verifyComplete();

        verify(publisher, times(5)).publishValidated(any());
    }

    @Test
    void ingest_subscribedOnNonBlockingScheduler_completesWithoutBlockingCalls() {
        stubPublisher();
        Flux<TelemetrySample> samples = Flux.just(sample("heart_rate", 150.0), sample("heart_rate", 500.0));

        StepVerifier.create(service.ingest(samples).subscribeOn(Schedulers.parallel()))
                .expectNextCount(2)
                .verifyComplete();
    }
}
