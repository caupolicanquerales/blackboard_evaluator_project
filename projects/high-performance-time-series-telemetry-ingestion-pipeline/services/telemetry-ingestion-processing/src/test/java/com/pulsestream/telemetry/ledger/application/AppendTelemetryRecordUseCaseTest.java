package com.pulsestream.telemetry.ledger.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.shared.events.TelemetryContracts.MetricType;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.RevisionReason;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetryBackfillDetected;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetryRecordAppended;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetrySample;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.TelemetrySampleOrdered;
import com.pulsestream.telemetry.shared.events.TelemetryContracts.ValidationStatus;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class AppendTelemetryRecordUseCaseTest {

    private static final Instant T_DEVICE = Instant.parse("2024-05-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-05-01T10:00:05Z");

    private static TelemetrySample sample() {
        return new TelemetrySample("dev-1", MetricType.HEART_RATE, T_DEVICE, T_INGRESS, 142.0);
    }

    private static TelemetrySampleOrdered ordered() {
        return new TelemetrySampleOrdered(sample(), ValidationStatus.VALID);
    }

    private static TelemetryBackfillDetected backfill() {
        return new TelemetryBackfillDetected(sample(), ValidationStatus.VALID, Duration.ofSeconds(30));
    }

    /** In-memory contract fake: append-only revisions per sample key; null failure flag means dead-lettered. */
    private static final class InMemoryUseCase implements AppendTelemetryRecordUseCase {
        private final Map<String, List<TelemetryRecordAppended>> revisions = new HashMap<>();
        private final boolean failing;

        InMemoryUseCase(boolean failing) {
            this.failing = failing;
        }

        @Override
        public Mono<TelemetryRecordAppended> appendOrdered(TelemetrySampleOrdered ordered) {
            return append(ordered.sample(), RevisionReason.ORIGINAL);
        }

        @Override
        public Mono<TelemetryRecordAppended> appendBackfill(TelemetryBackfillDetected backfill) {
            return append(backfill.sample(), RevisionReason.BACKFILL);
        }

        private Mono<TelemetryRecordAppended> append(TelemetrySample s, RevisionReason reason) {
            if (failing) {
                return Mono.empty();
            }
            String key = s.deviceId() + "|" + s.metricType() + "|" + s.tDevice();
            List<TelemetryRecordAppended> list = revisions.computeIfAbsent(key, k -> new ArrayList<>());
            TelemetryRecordAppended event = new TelemetryRecordAppended(
                    s.deviceId(), s.metricType(), s.tDevice(), list.size() + 1, reason);
            list.add(event);
            return Mono.just(event);
        }
    }

    @Test
    void appendOrdered_validOrderedSample_emitsRecordAppendedForSample() {
        AppendTelemetryRecordUseCase useCase = new InMemoryUseCase(false);

        StepVerifier.create(useCase.appendOrdered(ordered()))
                .assertNext(e -> {
                    assertThat(e.deviceId()).isEqualTo("dev-1");
                    assertThat(e.metricType()).isEqualTo(MetricType.HEART_RATE);
                    assertThat(e.tDevice()).isEqualTo(T_DEVICE);
                    assertThat(e.revision()).isEqualTo(1);
                })
                .verifyComplete();
    }

    @Test
    void appendBackfill_backfillDetected_emitsRecordAppendedWithBackfillReason() {
        AppendTelemetryRecordUseCase useCase = new InMemoryUseCase(false);

        StepVerifier.create(useCase.appendBackfill(backfill()))
                .assertNext(e -> {
                    assertThat(e.reason()).isEqualTo(RevisionReason.BACKFILL);
                    assertThat(e.tDevice()).isEqualTo(T_DEVICE);
                })
                .verifyComplete();
    }

    @Test
    void appendOrdered_calledTwiceForSameSample_appendsNewRevisionEachTime() {
        AppendTelemetryRecordUseCase useCase = new InMemoryUseCase(false);

        StepVerifier.create(useCase.appendOrdered(ordered()).then(useCase.appendBackfill(backfill())))
                .assertNext(e -> assertThat(e.revision()).isEqualTo(2))
                .verifyComplete();
    }

    @Test
    void appendOrdered_appendPermanentlyFailed_emitsEmpty() {
        AppendTelemetryRecordUseCase useCase = new InMemoryUseCase(true);

        StepVerifier.create(useCase.appendOrdered(ordered())).verifyComplete();
    }

    @Test
    void appendBackfill_appendPermanentlyFailed_emitsEmpty() {
        AppendTelemetryRecordUseCase useCase = new InMemoryUseCase(true);

        StepVerifier.create(useCase.appendBackfill(backfill())).verifyComplete();
    }
}
