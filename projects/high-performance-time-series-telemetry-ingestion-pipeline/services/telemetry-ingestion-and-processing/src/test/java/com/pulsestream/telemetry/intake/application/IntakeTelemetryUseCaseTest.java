package com.pulsestream.telemetry.intake.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.MetricBoundaryPolicy;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.intake.domain.TelemetrySampleValidated;
import com.pulsestream.telemetry.intake.domain.ValidationFailed;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class IntakeTelemetryUseCaseTest {

    private static final Instant NOW = Instant.parse("2025-01-01T00:00:00Z");
    private static final Clock CLOCK = Clock.fixed(NOW, ZoneOffset.UTC);

    private final MetricBoundaryPolicy policy = mock(MetricBoundaryPolicy.class);
    private final RecordingPort port = new RecordingPort();
    private final IntakeTelemetryUseCase useCase = new IntakeTelemetryUseCase(policy, port, CLOCK);

    private static TelemetrySample sample() {
        return new TelemetrySample("sensor-1", "cpu.temperature", 42.0, Instant.parse("2024-12-31T23:59:59Z"));
    }

    @Test
    void ingest_validSample_publishesTelemetrySampleValidated() {
        when(policy.isWithinBounds(any())).thenReturn(true);

        StepVerifier.create(useCase.ingest(sample())).verifyComplete();

        assertThat(port.events).hasSize(1);
        assertThat(port.events.get(0)).isInstanceOf(TelemetrySampleValidated.class);
    }

    @Test
    void ingest_validSample_stampsTIngressFromClock() {
        when(policy.isWithinBounds(any())).thenReturn(true);

        StepVerifier.create(useCase.ingest(sample())).verifyComplete();

        TelemetrySampleValidated event = (TelemetrySampleValidated) port.events.get(0);
        assertThat(event.tIngress()).isEqualTo(NOW);
    }

    @Test
    void ingest_outOfBoundsSample_publishesValidationFailedInsteadOfDiscarding() {
        when(policy.isWithinBounds(any())).thenReturn(false);

        StepVerifier.create(useCase.ingest(sample())).verifyComplete();

        assertThat(port.events).hasSize(1);
        assertThat(port.events.get(0)).isInstanceOf(ValidationFailed.class);
    }

    @Test
    void ingest_outOfBoundsSample_stampsTIngressOnFailureEvent() {
        when(policy.isWithinBounds(any())).thenReturn(false);

        StepVerifier.create(useCase.ingest(sample())).verifyComplete();

        ValidationFailed event = (ValidationFailed) port.events.get(0);
        assertThat(event.tIngress()).isEqualTo(NOW);
    }

    @Test
    void ingest_portNotYetAccepting_appliesBackpressureWithoutDropping() {
        when(policy.isWithinBounds(any())).thenReturn(true);
        port.gate = Mono.never();

        StepVerifier.create(useCase.ingest(sample()))
                .expectSubscription()
                .expectNoEvent(Duration.ofMillis(50))
                .thenCancel()
                .verify();

        assertThat(port.attempts).isEqualTo(1);
    }

    private static final class RecordingPort implements ReorderingEventPort {
        final List<Object> events = new ArrayList<>();
        Mono<Void> gate = Mono.empty();
        int attempts;

        @Override
        public Mono<Void> publish(Object event) {
            attempts++;
            return gate.doOnSuccess(v -> events.add(event));
        }
    }
}
