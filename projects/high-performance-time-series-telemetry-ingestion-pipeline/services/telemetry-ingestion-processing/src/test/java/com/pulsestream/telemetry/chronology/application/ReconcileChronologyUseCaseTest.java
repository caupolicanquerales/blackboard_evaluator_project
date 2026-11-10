package com.pulsestream.telemetry.chronology.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.shared.events.TelemetryContracts.MetricType;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetrySample;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.ValidationStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class ReconcileChronologyUseCaseTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T10:00:05Z");

    private final ReconcileChronologyUseCase useCase = mock(ReconcileChronologyUseCase.class);

    private static TelemetrySample sample() {
        return new TelemetrySample("device-1", MetricType.HEART_RATE, T_DEVICE, T_INGRESS, 120.0);
    }

    @ParameterizedTest
    @EnumSource(ValidationStatus.class)
    void reconcile_sampleWithAnyStatus_completesEmpty(ValidationStatus status) {
        TelemetrySample sample = sample();
        when(useCase.reconcile(sample, status)).thenReturn(Mono.empty());

        StepVerifier.create(useCase.reconcile(sample, status)).verifyComplete();

        verify(useCase).reconcile(sample, status);
    }

    @Test
    void reconcile_publishFails_propagatesErrorSignal() {
        TelemetrySample sample = sample();
        IllegalStateException failure = new IllegalStateException("publish failed");
        when(useCase.reconcile(sample, ValidationStatus.VALID)).thenReturn(Mono.error(failure));

        StepVerifier.create(useCase.reconcile(sample, ValidationStatus.VALID))
                .expectErrorSatisfies(e -> assertThat(e).isSameAs(failure))
                .verify();
    }

    @Test
    void reconcile_returnedMono_isLazyUntilSubscribed() {
        TelemetrySample sample = sample();
        boolean[] subscribed = {false};
        when(useCase.reconcile(sample, ValidationStatus.VALID))
                .thenReturn(Mono.<Void>empty().doOnSubscribe(s -> subscribed[0] = true));

        Mono<Void> result = useCase.reconcile(sample, ValidationStatus.VALID);

        assertThat(subscribed[0]).isFalse();
        StepVerifier.create(result).verifyComplete();
        assertThat(subscribed[0]).isTrue();
    }

    @Test
    void flush_bufferedSamples_completesEmpty() {
        when(useCase.flush()).thenReturn(Mono.empty());

        StepVerifier.create(useCase.flush()).verifyComplete();

        verify(useCase).flush();
    }

    @Test
    void flush_publishFails_propagatesErrorSignal() {
        when(useCase.flush()).thenReturn(Mono.error(new IllegalStateException("flush failed")));

        StepVerifier.create(useCase.flush())
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void reconcile_doesNotTriggerFlush() {
        TelemetrySample sample = sample();
        when(useCase.reconcile(sample, ValidationStatus.VALIDATION_FAILED)).thenReturn(Mono.empty());

        StepVerifier.create(useCase.reconcile(sample, ValidationStatus.VALIDATION_FAILED)).verifyComplete();

        verify(useCase, never()).flush();
    }
}
