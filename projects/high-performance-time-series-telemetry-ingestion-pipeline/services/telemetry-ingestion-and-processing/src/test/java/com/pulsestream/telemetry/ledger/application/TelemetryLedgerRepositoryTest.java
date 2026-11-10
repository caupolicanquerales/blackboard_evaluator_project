package com.pulsestream.telemetry.ledger.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.ledger.domain.EventRevision;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class TelemetryLedgerRepositoryTest {

    private static final Instant T0 = Instant.parse("2024-01-01T10:00:00Z");
    private static final Instant T1 = Instant.parse("2024-01-01T10:01:00Z");
    private static final Instant T2 = Instant.parse("2024-01-01T10:02:00Z");
    private static final Instant INGRESS = Instant.parse("2024-01-01T10:05:00Z");
    private static final Instant RECORDED = Instant.parse("2024-01-01T10:06:00Z");

    private TelemetryLedgerRepository repository;

    @BeforeEach
    void setUp() {
        repository = new InMemoryLedger();
    }

    @Test
    void append_newRevision_returnsStoredRevision() {
        EventRevision original = original("dev-1", TelemetrySample.MetricType.HEART_RATE, T0, 60);

        StepVerifier.create(repository.append(original)).expectNext(original).verifyComplete();
    }

    @Test
    void append_duplicateRecordIdAndRevisionNumber_emitsError() {
        EventRevision original = original("dev-1", TelemetrySample.MetricType.HEART_RATE, T0, 60);
        repository.append(original).block();

        StepVerifier.create(repository.append(original)).expectError().verify();
    }

    @Test
    void findLatest_multipleRevisions_returnsHighestRevision() {
        EventRevision first = original("dev-1", TelemetrySample.MetricType.HEART_RATE, T0, 60);
        EventRevision second = correction(first, 61);
        EventRevision third = correction(second, 62);
        Flux.just(first, third, second).concatMap(repository::append).blockLast();

        StepVerifier.create(repository.findLatest(first.recordId())).expectNext(third).verifyComplete();
    }

    @Test
    void findLatest_unknownRecord_returnsEmpty() {
        StepVerifier.create(repository.findLatest(UUID.fromString("00000000-0000-0000-0000-000000000001")))
                .verifyComplete();
    }

    @Test
    void findRevisions_multipleRevisions_returnsOrderedByRevisionNumber() {
        EventRevision first = original("dev-1", TelemetrySample.MetricType.HEART_RATE, T0, 60);
        EventRevision second = correction(first, 61);
        EventRevision third = correction(second, 62);
        Flux.just(third, first, second).concatMap(repository::append).blockLast();

        StepVerifier.create(repository.findRevisions(first.recordId()))
                .expectNext(first, second, third)
                .verifyComplete();
    }

    @Test
    void findRevisions_unknownRecord_returnsEmpty() {
        StepVerifier.create(repository.findRevisions(UUID.fromString("00000000-0000-0000-0000-000000000002")))
                .verifyComplete();
    }

    @Test
    void findHistory_rangeInclusive_returnsMatchingOrderedByDeviceTimestamp() {
        EventRevision atT2 = original("dev-1", TelemetrySample.MetricType.HEART_RATE, T2, 70);
        EventRevision atT0 = original("dev-1", TelemetrySample.MetricType.HEART_RATE, T0, 60);
        EventRevision atT1 = original("dev-1", TelemetrySample.MetricType.HEART_RATE, T1, 65);
        Flux.just(atT2, atT0, atT1).concatMap(repository::append).blockLast();

        StepVerifier.create(repository.findHistory("dev-1", TelemetrySample.MetricType.HEART_RATE, T0, T2))
                .expectNext(atT0, atT1, atT2)
                .verifyComplete();
    }

    @Test
    void findHistory_otherDeviceMetricOrOutOfRange_excluded() {
        EventRevision inRange = original("dev-1", TelemetrySample.MetricType.HEART_RATE, T1, 65);
        EventRevision otherDevice = original("dev-2", TelemetrySample.MetricType.HEART_RATE, T1, 65);
        EventRevision otherMetric = original("dev-1", TelemetrySample.MetricType.POWER, T1, 200);
        EventRevision outOfRange = original("dev-1", TelemetrySample.MetricType.HEART_RATE, T2, 70);
        Flux.just(inRange, otherDevice, otherMetric, outOfRange).concatMap(repository::append).blockLast();

        StepVerifier.create(repository.findHistory("dev-1", TelemetrySample.MetricType.HEART_RATE, T0, T1))
                .expectNext(inRange)
                .verifyComplete();
    }

    private static EventRevision original(
            String deviceId, TelemetrySample.MetricType metric, Instant deviceTimestamp, double value) {
        return EventRevision.original(sample(deviceId, metric, deviceTimestamp, value), RECORDED);
    }

    private static EventRevision correction(EventRevision previous, double value) {
        TelemetrySample sample =
                sample(previous.deviceId(), previous.metricType(), previous.deviceTimestamp(), value);
        return previous.next(sample, EventRevision.RevisionReason.CORRECTION, RECORDED);
    }

    private static TelemetrySample sample(
            String deviceId, TelemetrySample.MetricType metric, Instant deviceTimestamp, double value) {
        return new TelemetrySample(
                TelemetrySample.recordIdFor(deviceId, metric, deviceTimestamp),
                deviceId,
                metric,
                value,
                deviceTimestamp,
                INGRESS,
                TelemetrySample.ValidationStatus.VALID);
    }

    private static final class InMemoryLedger implements TelemetryLedgerRepository {
        private final List<EventRevision> store = new ArrayList<>();

        @Override
        public Mono<EventRevision> append(EventRevision revision) {
            boolean duplicate = store.stream()
                    .anyMatch(r -> r.recordId().equals(revision.recordId())
                            && r.revisionNumber() == revision.revisionNumber());
            if (duplicate) {
                return Mono.error(new IllegalStateException("duplicate revision"));
            }
            store.add(revision);
            return Mono.just(revision);
        }

        @Override
        public Mono<EventRevision> findLatest(UUID recordId) {
            return Flux.fromIterable(store)
                    .filter(r -> r.recordId().equals(recordId))
                    .sort(Comparator.comparingInt(EventRevision::revisionNumber).reversed())
                    .next();
        }

        @Override
        public Flux<EventRevision> findRevisions(UUID recordId) {
            return Flux.fromIterable(store)
                    .filter(r -> r.recordId().equals(recordId))
                    .sort(Comparator.comparingInt(EventRevision::revisionNumber));
        }

        @Override
        public Flux<EventRevision> findHistory(
                String deviceId, TelemetrySample.MetricType metricType, Instant from, Instant to) {
            return Flux.fromIterable(store)
                    .filter(r -> r.deviceId().equals(deviceId)
                            && r.metricType() == metricType
                            && !r.deviceTimestamp().isBefore(from)
                            && !r.deviceTimestamp().isAfter(to))
                    .sort(Comparator.comparing(EventRevision::deviceTimestamp));
        }
    }
}
