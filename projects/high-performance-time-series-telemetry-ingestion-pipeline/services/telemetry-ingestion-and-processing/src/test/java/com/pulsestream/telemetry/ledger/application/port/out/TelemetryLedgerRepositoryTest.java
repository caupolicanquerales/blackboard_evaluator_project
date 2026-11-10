package com.pulsestream.telemetry.ledger.application.port.out;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.lang.reflect.Method;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class TelemetryLedgerRepositoryTest {

    private static final Instant T0 = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T1 = Instant.parse("2024-01-01T00:01:00Z");
    private static final Instant T2 = Instant.parse("2024-01-01T00:02:00Z");
    private static final Instant INGRESS = Instant.parse("2024-01-01T00:05:00Z");

    private TelemetryLedgerRepository repository;

    @BeforeEach
    void setUp() {
        repository = new InMemoryLedger();
    }

    private static TelemetryRecord original(String device, String metric, Instant tDevice) {
        return TelemetryRecord.original(device, metric, 1.0, tDevice, INGRESS, "VALID");
    }

    @Test
    void append_newRecord_emitsAppendedRecord() {
        TelemetryRecord record = original("dev-1", "temp", T0);

        StepVerifier.create(repository.append(record)).expectNext(record).verifyComplete();
    }

    @Test
    void append_revision_keepsOriginalInChain() {
        TelemetryRecord first = original("dev-1", "temp", T0);
        TelemetryRecord revised = first.reviseWith(2.0, INGRESS, "VALID");
        repository.append(first).block();
        repository.append(revised).block();

        StepVerifier.create(repository.findRevisionChain("dev-1", "temp", T0))
                .expectNext(first, revised)
                .verifyComplete();
    }

    @Test
    void findHistory_multipleRecords_ordersByTDeviceThenRevision() {
        TelemetryRecord late = original("dev-1", "temp", T1);
        TelemetryRecord early = original("dev-1", "temp", T0);
        TelemetryRecord earlyRev = early.reviseWith(3.0, INGRESS, "VALID");
        repository.append(late).block();
        repository.append(earlyRev).block();
        repository.append(early).block();

        StepVerifier.create(repository.findHistory("dev-1", T0, T2))
                .expectNext(early, earlyRev, late)
                .verifyComplete();
    }

    @Test
    void findHistory_range_includesFromAndExcludesTo() {
        TelemetryRecord atFrom = original("dev-1", "temp", T0);
        TelemetryRecord atTo = original("dev-1", "temp", T1);
        repository.append(atFrom).block();
        repository.append(atTo).block();

        StepVerifier.create(repository.findHistory("dev-1", T0, T1))
                .expectNext(atFrom)
                .verifyComplete();
    }

    @Test
    void findHistory_otherDevice_isExcluded() {
        repository.append(original("dev-2", "temp", T0)).block();

        StepVerifier.create(repository.findHistory("dev-1", T0, T2)).verifyComplete();
    }

    @Test
    void findLatestRevision_withRevisions_emitsHighestRevision() {
        TelemetryRecord first = original("dev-1", "temp", T0);
        TelemetryRecord second = first.reviseWith(2.0, INGRESS, "VALID");
        TelemetryRecord third = second.reviseWith(3.0, INGRESS, "VALID");
        repository.append(first).block();
        repository.append(third).block();
        repository.append(second).block();

        StepVerifier.create(repository.findLatestRevision("dev-1", "temp", T0))
                .expectNext(third)
                .verifyComplete();
    }

    @Test
    void findLatestRevision_noRecords_completesEmpty() {
        StepVerifier.create(repository.findLatestRevision("dev-1", "temp", T0)).verifyComplete();
    }

    @Test
    void findRevisionChain_unorderedAppends_ordersByRevisionAscending() {
        TelemetryRecord first = original("dev-1", "temp", T0);
        TelemetryRecord second = first.reviseWith(2.0, INGRESS, "VALID");
        TelemetryRecord third = second.reviseWith(3.0, INGRESS, "VALID");
        repository.append(third).block();
        repository.append(first).block();
        repository.append(second).block();

        StepVerifier.create(repository.findRevisionChain("dev-1", "temp", T0))
                .expectNext(first, second, third)
                .verifyComplete();
    }

    @Test
    void findRevisionChain_otherMetric_isExcluded() {
        repository.append(original("dev-1", "humidity", T0)).block();

        StepVerifier.create(repository.findRevisionChain("dev-1", "temp", T0)).verifyComplete();
    }

    @Test
    void port_declaredMethods_haveNoUpdateOrDeleteOperations() {
        List<String> names = Arrays.stream(TelemetryLedgerRepository.class.getDeclaredMethods())
                .map(Method::getName)
                .toList();

        assertThat(names)
                .containsExactlyInAnyOrder(
                        "append", "findHistory", "findLatestRevision", "findRevisionChain");
    }

    private static final class InMemoryLedger implements TelemetryLedgerRepository {
        private final List<TelemetryRecord> store = new ArrayList<>();

        @Override
        public Mono<TelemetryRecord> append(TelemetryRecord record) {
            return Mono.fromSupplier(() -> {
                store.add(record);
                return record;
            });
        }

        @Override
        public Flux<TelemetryRecord> findHistory(
                String deviceId, Instant fromInclusive, Instant toExclusive) {
            return Flux.fromIterable(store)
                    .filter(r -> r.deviceId().equals(deviceId)
                            && !r.tDevice().isBefore(fromInclusive)
                            && r.tDevice().isBefore(toExclusive))
                    .sort(Comparator.comparing(TelemetryRecord::tDevice)
                            .thenComparingInt(TelemetryRecord::revision));
        }

        @Override
        public Mono<TelemetryRecord> findLatestRevision(
                String deviceId, String metric, Instant tDevice) {
            return findRevisionChain(deviceId, metric, tDevice).last();
        }

        @Override
        public Flux<TelemetryRecord> findRevisionChain(
                String deviceId, String metric, Instant tDevice) {
            return Flux.fromIterable(store)
                    .filter(r -> r.deviceId().equals(deviceId)
                            && r.metric().equals(metric)
                            && r.tDevice().equals(tDevice))
                    .sort(Comparator.comparingInt(TelemetryRecord::revision));
        }
    }
}
