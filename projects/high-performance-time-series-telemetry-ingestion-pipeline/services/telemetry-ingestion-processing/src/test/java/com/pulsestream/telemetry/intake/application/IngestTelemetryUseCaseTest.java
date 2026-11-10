package com.pulsestream.telemetry.intake.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.shared.events.TelemetryContracts;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.MetricType;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetrySample;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class IngestTelemetryUseCaseTest {

    private static final Instant T = Instant.parse("2024-01-01T10:00:00Z");

    private final List<Object> published = new ArrayList<>();

    private final IngestTelemetryUseCase useCase = samples -> Mono.fromSupplier(() -> {
        for (TelemetrySample sample : samples) {
            boolean valid = Double.isFinite(sample.value()) && sample.value() >= 0;
            published.add(valid
                    ? new TelemetryContracts.TelemetrySampleValidated(sample)
                    : new TelemetryContracts.TelemetrySampleValidationFailed(sample, "invalid"));
        }
        return samples.size();
    });

    private static TelemetrySample sample(double value) {
        return new TelemetrySample("dev-1", MetricType.HEART_RATE, T, T.plusSeconds(1), value);
    }

    @Test
    void ingest_allValidSamples_emitsCountAndPublishesValidatedEvents() {
        StepVerifier.create(useCase.ingest(List.of(sample(60), sample(61))))
                .expectNext(2)
                .verifyComplete();

        assertThat(published).hasSize(2)
                .allMatch(e -> e instanceof TelemetryContracts.TelemetrySampleValidated);
    }

    @Test
    void ingest_invalidSampleMixedWithValid_countsBothAndPublishesFailure() {
        StepVerifier.create(useCase.ingest(List.of(sample(60), sample(-1))))
                .expectNext(2)
                .verifyComplete();

        assertThat(published).hasSize(2)
                .anyMatch(e -> e instanceof TelemetryContracts.TelemetrySampleValidationFailed);
    }

    @Test
    void ingest_emptyList_emitsZeroAndPublishesNothing() {
        StepVerifier.create(useCase.ingest(List.of()))
                .expectNext(0)
                .verifyComplete();

        assertThat(published).isEmpty();
    }
}
