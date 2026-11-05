package com.blackboard.telemetry.reordering.application;
import com.blackboard.telemetry.shared.events.TelemetryEvents;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.Instant;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.blackboard.telemetry.shared.events.TelemetryEvents.BackfilledSampleReindexed;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleOrdered;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidated;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidationFailed;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetryWindowBuffered;
import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;

import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

class StreamReorderingServiceTest {

    private static final String DEVICE = "device-1";
    private static final Instant BASE = Instant.parse("2026-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2026-01-01T10:05:00Z");

    private StreamReorderingService service;

    @BeforeEach
    void setUp() {
        service = new StreamReorderingService();
    }

    private static Instant at(long seconds) {
        return BASE.plusSeconds(seconds);
    }

    private static TelemetrySampleValidated validated(long seconds) {
        return validated(DEVICE, seconds, T_INGRESS);
    }

    private static TelemetrySampleValidated validated(String device, long seconds, Instant tIngress) {
        return new TelemetrySampleValidated(device, at(seconds), tIngress, "heart_rate", 100.0 + seconds,
                ValidationStatus.VALID);
    }

    private static TelemetrySampleValidationFailed failed(long seconds) {
        return new TelemetrySampleValidationFailed(DEVICE, at(seconds), T_INGRESS, "heart_rate", 400.0,
                ValidationStatus.VALIDATION_FAILED);
    }

    private static TelemetrySampleOrdered ordered(long seconds) {
        return new TelemetrySampleOrdered(DEVICE, at(seconds), T_INGRESS, "heart_rate", 100.0 + seconds,
                ValidationStatus.VALID);
    }

    private Flux<TelemetrySampleOrdered> reorder(TelemetrySampleValidated... samples) {
        return service.reorder(Flux.just(samples), Flux.empty());
    }

    @Test
    void reorder_outOfOrderSamplesWithinWindow_emitsAscendingByTDevice() {
        StepVerifier.create(reorder(validated(30), validated(10), validated(20)))
                .expectNext(ordered(10), ordered(20), ordered(30))
                .verifyComplete();
    }

    @Test
    void reorder_inconsistentIngressOrder_ordersByTDeviceNotTIngress() {
        TelemetrySampleValidated first = validated(DEVICE, 10, T_INGRESS.plusSeconds(20));
        TelemetrySampleValidated second = validated(DEVICE, 20, T_INGRESS);

        StepVerifier.create(reorder(second, first))
                .assertNext(s -> assertThat(s.tDevice()).isEqualTo(at(10)))
                .assertNext(s -> assertThat(s.tDevice()).isEqualTo(at(20)))
                .verifyComplete();
    }

    @Test
    void reorder_validationFailedSample_staysFlaggedValidationFailed() {
        StepVerifier.create(service.reorder(Flux.empty(), Flux.just(failed(10))))
                .assertNext(s -> assertThat(s.status())
                        .isEqualTo(ValidationStatus.VALIDATION_FAILED))
                .verifyComplete();
    }

    @Test
    void reorder_failedAndValidatedMixed_ordersByTDeviceKeepingFlags() {
        StepVerifier.create(service.reorder(Flux.just(validated(20)), Flux.just(failed(10))))
                .assertNext(s -> assertThat(s.status())
                        .isEqualTo(ValidationStatus.VALIDATION_FAILED))
                .expectNext(ordered(20))
                .verifyComplete();
    }

    @Test
    void reorder_lateSampleWithin60Seconds_isStillEmittedInTDeviceOrder() {
        StepVerifier.create(reorder(validated(10), validated(70), validated(30)))
                .expectNext(ordered(10), ordered(30), ordered(70))
                .verifyComplete();
    }

    @Test
    void reorder_lateSampleWithin60Seconds_emitsBackfilledSampleReindexed() {
        StepVerifier.create(service.reindexed().take(1))
                .then(() -> reorder(validated(10), validated(70), validated(30)).subscribe())
                .expectNext(new BackfilledSampleReindexed(DEVICE, at(30), T_INGRESS, "heart_rate", 130.0,
                        ValidationStatus.VALID))
                .verifyComplete();
    }

    @Test
    void reorder_lateSampleExactly60Seconds_isAcceptedAsBackfill() {
        StepVerifier.create(reorder(validated(100), validated(40)))
                .expectNext(ordered(40), ordered(100))
                .verifyComplete();
    }

    @Test
    void reorder_sampleOlderThan60Seconds_isNotReordered() {
        StepVerifier.create(reorder(validated(100), validated(39)))
                .expectNext(ordered(100))
                .verifyComplete();
    }

    @Test
    void reorder_sampleOlderThan60Seconds_isNotReindexed() {
        StepVerifier.withVirtualTime(() -> service.reindexed().take(Duration.ofSeconds(5)))
                .then(() -> reorder(validated(100), validated(39)).subscribe())
                .thenAwait(Duration.ofSeconds(5))
                .verifyComplete();
    }

    @Test
    void reorder_inOrderSamples_doNotEmitReindexed() {
        StepVerifier.withVirtualTime(() -> service.reindexed().take(Duration.ofSeconds(5)))
                .then(() -> reorder(validated(10), validated(20)).subscribe())
                .thenAwait(Duration.ofSeconds(5))
                .verifyComplete();
    }

    @Test
    void reorder_bufferedSample_emitsTelemetryWindowBuffered() {
        StepVerifier.create(service.buffered().take(1))
                .then(() -> reorder(validated(10), validated(20)).subscribe())
                .expectNext(new TelemetryWindowBuffered(DEVICE, at(10), T_INGRESS, "heart_rate", 110.0,
                        ValidationStatus.VALID))
                .verifyComplete();
    }

    @Test
    void reorder_samplesFromDifferentDevices_areOrderedIndependently() {
        TelemetrySampleValidated deviceBLate = validated("device-2", 5, T_INGRESS);
        TelemetrySampleValidated deviceAEarly = validated(DEVICE, 10, T_INGRESS);

        StepVerifier.create(service.reorder(Flux.just(deviceAEarly, deviceBLate), Flux.empty())
                .filter(s -> s.deviceId().equals(DEVICE)))
                .expectNext(ordered(10))
                .verifyComplete();
    }

    @Test
    void reorder_demandOfOne_emitsOnlyOneSamplePerRequest() {
        StepVerifier.create(reorder(validated(30), validated(10), validated(20)), 1)
                .expectNext(ordered(10))
                .expectNoEvent(Duration.ofMillis(10))
                .thenRequest(1)
                .expectNext(ordered(20))
                .thenRequest(1)
                .expectNext(ordered(30))
                .verifyComplete();
    }

    @Test
    void reorder_noDemand_emitsNothing() {
        StepVerifier.create(reorder(validated(10)), 0)
                .expectSubscription()
                .expectNoEvent(Duration.ofMillis(10))
                .thenCancel()
                .verify();
    }

    @Test
    void reorder_delayedSamplesOnVirtualTime_emitsInTDeviceOrder() {
        StepVerifier.withVirtualTime(() -> service.reorder(
                        Flux.just(validated(30), validated(10), validated(20)).delayElements(Duration.ofSeconds(10)),
                        Flux.empty()))
                .thenAwait(Duration.ofSeconds(30))
                .expectNext(ordered(10), ordered(20), ordered(30))
                .verifyComplete();
    }

    @Test
    void reorder_emptyInputs_completesWithoutEmitting() {
        StepVerifier.create(service.reorder(Flux.empty(), Flux.empty()))
                .verifyComplete();
    }
}
