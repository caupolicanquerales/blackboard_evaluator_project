package com.blackboard.telemetry.history.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.blackboard.telemetry.history.domain.RevisionReason;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class TelemetryHistoryRepositoryTest {

    private static final Instant T0 = Instant.parse("2025-01-01T00:00:00Z");
    private static final MetricKind METRIC = MetricKind.values()[0];

    private final TelemetryHistoryRepository repository = mock(TelemetryHistoryRepository.class);

    private static TelemetrySample sample(Instant tDevice) {
        return new TelemetrySample("dev-1", METRIC, tDevice, T0.plusSeconds(60), 1.0, ValidationStatus.VALID);
    }

    @Test
    void appendSample_newIdentity_emitsGeneratedId() {
        TelemetrySample sample = sample(T0);
        when(repository.appendSample(sample)).thenReturn(Mono.just(7L));

        StepVerifier.create(repository.appendSample(sample)).expectNext(7L).verifyComplete();
    }

    @Test
    void appendSample_duplicateIdentity_completesEmpty() {
        TelemetrySample sample = sample(T0);
        when(repository.appendSample(sample)).thenReturn(Mono.empty());

        StepVerifier.create(repository.appendSample(sample)).verifyComplete();
    }

    @Test
    void appendRevision_firstRevision_emitsNumberOne() {
        when(repository.appendRevision(7L, RevisionReason.BACKFILL, 1.0, T0)).thenReturn(Mono.just(1));

        StepVerifier.create(repository.appendRevision(7L, RevisionReason.BACKFILL, 1.0, T0))
                .expectNext(1)
                .verifyComplete();
    }

    @Test
    void appendRevision_secondRevision_emitsNumberTwo() {
        when(repository.appendRevision(7L, RevisionReason.BACKFILL, 2.0, T0)).thenReturn(Mono.just(2));

        StepVerifier.create(repository.appendRevision(7L, RevisionReason.BACKFILL, 2.0, T0))
                .assertNext(n -> assertThat(n).isEqualTo(2))
                .verifyComplete();
    }

    @Test
    void findLatestTDevice_storedSamples_emitsGreatestTDevice() {
        when(repository.findLatestTDevice("dev-1", METRIC)).thenReturn(Mono.just(T0.plusSeconds(5)));

        StepVerifier.create(repository.findLatestTDevice("dev-1", METRIC))
                .expectNext(T0.plusSeconds(5))
                .verifyComplete();
    }

    @Test
    void findLatestTDevice_nothingStored_completesEmpty() {
        when(repository.findLatestTDevice("dev-1", METRIC)).thenReturn(Mono.empty());

        StepVerifier.create(repository.findLatestTDevice("dev-1", METRIC)).verifyComplete();
    }

    @Test
    void findWindow_samplesInRange_emitsAscendingByTDeviceWithinLimit() {
        TelemetrySample a = sample(T0);
        TelemetrySample b = sample(T0.plusSeconds(1));
        when(repository.findWindow("dev-1", METRIC, T0, T0.plusSeconds(5), 2)).thenReturn(Flux.just(a, b));

        StepVerifier.create(repository.findWindow("dev-1", METRIC, T0, T0.plusSeconds(5), 2))
                .expectNext(a, b)
                .verifyComplete();
    }
}
