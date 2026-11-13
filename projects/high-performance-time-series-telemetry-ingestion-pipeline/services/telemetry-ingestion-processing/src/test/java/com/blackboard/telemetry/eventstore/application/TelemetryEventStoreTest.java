package com.blackboard.telemetry.eventstore.application;
import java.util.Arrays;

import static org.assertj.core.api.Assertions.assertThat;

import com.blackboard.telemetry.eventstore.domain.TelemetryRecord;
import java.lang.reflect.Method;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class TelemetryEventStoreTest {

    private static final Instant T1 = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T2 = Instant.parse("2024-01-01T00:01:00Z");
    private static final Instant T3 = Instant.parse("2024-01-01T00:02:00Z");

    private static class InMemoryStore implements TelemetryEventStore {
        private final List<TelemetryRecord> rows = new ArrayList<>();

        @Override
        public Mono<TelemetryRecord> append(TelemetryRecord record) {
            return Mono.fromSupplier(() -> {
                rows.add(record);
                return record;
            });
        }

        @Override
        public Flux<TelemetryRecord> findLatestInRange(String deviceId, String metric, Instant from, Instant to) {
            return Flux.defer(() -> {
                Map<Instant, TelemetryRecord> latest = new TreeMap<>();
                rows.stream()
                        .filter(r -> r.deviceId().equals(deviceId) && r.metric().equals(metric))
                        .filter(r -> !r.tDevice().isBefore(from) && !r.tDevice().isAfter(to))
                        .forEach(r -> latest.merge(r.tDevice(), r,
                                (a, b) -> a.revision() >= b.revision() ? a : b));
                return Flux.fromIterable(latest.values());
            });
        }
    }

    private static TelemetryRecord rec(Instant tDevice, long revision) {
        return new TelemetryRecord("dev-1", "temp", tDevice, tDevice, 1.0 * revision, "VALIDATED", revision);
    }

    @Test
    void append_record_emitsStoredRecord() {
        InMemoryStore store = new InMemoryStore();
        TelemetryRecord record = rec(T1, 1);

        StepVerifier.create(store.append(record)).expectNext(record).verifyComplete();
    }

    @Test
    void findLatestInRange_multipleRevisions_returnsOnlyHighestRevision() {
        InMemoryStore store = new InMemoryStore();
        TelemetryRecord latest = rec(T1, 2);
        store.append(rec(T1, 1)).block();
        store.append(latest).block();

        StepVerifier.create(store.findLatestInRange("dev-1", "temp", T1, T3))
                .expectNext(latest).verifyComplete();
    }

    @Test
    void findLatestInRange_unorderedAppends_returnsOrderedByTDeviceAscending() {
        InMemoryStore store = new InMemoryStore();
        store.append(rec(T3, 1)).block();
        store.append(rec(T1, 1)).block();
        store.append(rec(T2, 1)).block();

        StepVerifier.create(store.findLatestInRange("dev-1", "temp", T1, T3).map(TelemetryRecord::tDevice))
                .expectNext(T1, T2, T3).verifyComplete();
    }

    @Test
    void findLatestInRange_recordsOutsideRange_areExcludedAndBoundsInclusive() {
        InMemoryStore store = new InMemoryStore();
        store.append(rec(T1, 1)).block();
        store.append(rec(T2, 1)).block();
        store.append(rec(T3, 1)).block();

        StepVerifier.create(store.findLatestInRange("dev-1", "temp", T2, T2).map(TelemetryRecord::tDevice))
                .expectNext(T2).verifyComplete();
    }

    @Test
    void findLatestInRange_otherDeviceOrMetric_isExcluded() {
        InMemoryStore store = new InMemoryStore();
        store.append(new TelemetryRecord("dev-2", "temp", T1, T1, 1.0, "VALIDATED", 1)).block();
        store.append(new TelemetryRecord("dev-1", "hum", T1, T1, 1.0, "VALIDATED", 1)).block();

        StepVerifier.create(store.findLatestInRange("dev-1", "temp", T1, T3)).verifyComplete();
    }

    @Test
    void interface_declaredMethods_areOnlyAppendAndFindLatestInRange() {
        List<String> names = java.util.Arrays.stream(TelemetryEventStore.class.getDeclaredMethods())
                .map(Method::getName)
                .sorted(Comparator.naturalOrder())
                .toList();

        assertThat(names).containsExactly("append", "findLatestInRange");
    }
}
