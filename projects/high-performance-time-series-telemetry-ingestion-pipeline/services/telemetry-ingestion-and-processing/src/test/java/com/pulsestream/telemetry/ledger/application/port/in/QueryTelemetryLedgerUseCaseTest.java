package com.pulsestream.telemetry.ledger.application.port.in;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

class QueryTelemetryLedgerUseCaseTest {

    private static final String DEVICE = "dev-1";
    private static final String METRIC = "temp";
    private static final Instant T1 = Instant.parse("2025-01-01T00:00:00Z");
    private static final Instant T2 = Instant.parse("2025-01-01T00:00:10Z");
    private static final Instant T3 = Instant.parse("2025-01-01T00:00:20Z");
    private static final Instant INGRESS = Instant.parse("2025-01-01T00:01:00Z");

    private static final class InMemoryLedger implements QueryTelemetryLedgerUseCase {
        private final List<TelemetryRecord> records;

        InMemoryLedger(List<TelemetryRecord> records) {
            this.records = records;
        }

        @Override
        public Flux<TelemetryRecord> history(String deviceId, Instant from, Instant toExclusive) {
            return Flux.fromIterable(records)
                    .filter(r -> inRange(r, deviceId, from, toExclusive))
                    .sort(Comparator.comparing(TelemetryRecord::tDevice)
                            .thenComparing(TelemetryRecord::revision));
        }

        @Override
        public Flux<TelemetryRecord> latestHistory(String deviceId, Instant from, Instant toExclusive) {
            Map<String, TelemetryRecord> latest = records.stream()
                    .filter(r -> inRange(r, deviceId, from, toExclusive))
                    .collect(Collectors.toMap(
                            r -> r.metric() + "|" + r.tDevice(),
                            Function.identity(),
                            (a, b) -> a.revision() >= b.revision() ? a : b));
            return Flux.fromIterable(latest.values())
                    .sort(Comparator.comparing(TelemetryRecord::tDevice));
        }

        @Override
        public Flux<TelemetryRecord> revisionChain(String deviceId, String metric, Instant tDevice) {
            return Flux.fromIterable(records)
                    .filter(r -> r.deviceId().equals(deviceId)
                            && r.metric().equals(metric)
                            && r.tDevice().equals(tDevice))
                    .sort(Comparator.comparingInt(TelemetryRecord::revision));
        }

        private static boolean inRange(TelemetryRecord r, String deviceId, Instant from, Instant toExclusive) {
            return r.deviceId().equals(deviceId)
                    && !r.tDevice().isBefore(from)
                    && r.tDevice().isBefore(toExclusive);
        }
    }

    private static TelemetryRecord original(String metric, Instant tDevice, double value) {
        return TelemetryRecord.original(DEVICE, metric, value, tDevice, INGRESS, "VALID");
    }

    private static InMemoryLedger ledgerWithRevisions(TelemetryRecord... records) {
        return new InMemoryLedger(List.of(records));
    }

    @Test
    void history_withRevisions_returnsAllOrderedByTDeviceThenRevision() {
        TelemetryRecord late = original(METRIC, T2, 2.0);
        TelemetryRecord early = original(METRIC, T1, 1.0);
        TelemetryRecord lateRev = late.reviseWith(2.5, INGRESS.plusSeconds(1), "VALID");
        QueryTelemetryLedgerUseCase useCase = ledgerWithRevisions(lateRev, late, early);

        StepVerifier.create(useCase.history(DEVICE, T1, T3))
                .expectNext(early, late, lateRev)
                .verifyComplete();
    }

    @Test
    void history_toExclusiveBoundary_excludesRecordAtUpperBound() {
        TelemetryRecord atFrom = original(METRIC, T1, 1.0);
        TelemetryRecord atTo = original(METRIC, T2, 2.0);
        QueryTelemetryLedgerUseCase useCase = ledgerWithRevisions(atFrom, atTo);

        StepVerifier.create(useCase.history(DEVICE, T1, T2))
                .expectNext(atFrom)
                .verifyComplete();
    }

    @Test
    void history_noRecordsForDevice_returnsEmpty() {
        QueryTelemetryLedgerUseCase useCase = ledgerWithRevisions(original(METRIC, T1, 1.0));

        StepVerifier.create(useCase.history("other-device", T1, T3)).verifyComplete();
    }

    @Test
    void latestHistory_withRevisions_returnsOnlyLatestPerMetricAndTDevice() {
        TelemetryRecord first = original(METRIC, T1, 1.0);
        TelemetryRecord firstRev = first.reviseWith(1.5, INGRESS.plusSeconds(1), "VALID");
        TelemetryRecord firstRev2 = firstRev.reviseWith(1.7, INGRESS.plusSeconds(2), "VALID");
        TelemetryRecord second = original(METRIC, T2, 2.0);
        QueryTelemetryLedgerUseCase useCase = ledgerWithRevisions(first, second, firstRev2, firstRev);

        StepVerifier.create(useCase.latestHistory(DEVICE, T1, T3))
                .expectNext(firstRev2, second)
                .verifyComplete();
    }

    @Test
    void latestHistory_differentMetricsSameTDevice_keepsOnePerMetric() {
        TelemetryRecord temp = original("temp", T1, 1.0);
        TelemetryRecord pressure = original("pressure", T1, 9.0);
        QueryTelemetryLedgerUseCase useCase = ledgerWithRevisions(temp, pressure);

        StepVerifier.create(useCase.latestHistory(DEVICE, T1, T2).collectList())
                .assertNext(list -> assertThat(list).containsExactlyInAnyOrder(temp, pressure))
                .verifyComplete();
    }

    @Test
    void latestHistory_resultsOrderedByTDevice() {
        TelemetryRecord a = original(METRIC, T3.minusSeconds(1), 3.0);
        TelemetryRecord b = original(METRIC, T1, 1.0);
        TelemetryRecord c = original(METRIC, T2, 2.0);
        QueryTelemetryLedgerUseCase useCase = ledgerWithRevisions(a, b, c);

        StepVerifier.create(useCase.latestHistory(DEVICE, T1, T3))
                .expectNext(b, c, a)
                .verifyComplete();
    }

    @Test
    void revisionChain_withRevisions_returnsAuditChainOrderedByRevision() {
        TelemetryRecord rev0 = original(METRIC, T1, 1.0);
        TelemetryRecord rev1 = rev0.reviseWith(1.5, INGRESS.plusSeconds(1), "VALID");
        TelemetryRecord rev2 = rev1.reviseWith(1.7, INGRESS.plusSeconds(2), "CORRECTED");
        QueryTelemetryLedgerUseCase useCase = ledgerWithRevisions(rev2, rev0, rev1, original(METRIC, T2, 5.0));

        StepVerifier.create(useCase.revisionChain(DEVICE, METRIC, T1))
                .expectNext(rev0, rev1, rev2)
                .verifyComplete();
    }

    @Test
    void revisionChain_unknownMetric_returnsEmpty() {
        QueryTelemetryLedgerUseCase useCase = ledgerWithRevisions(original(METRIC, T1, 1.0));

        StepVerifier.create(useCase.revisionChain(DEVICE, "unknown", T1)).verifyComplete();
    }

    @Test
    void port_delegatesWithExactArguments() {
        QueryTelemetryLedgerUseCase useCase = mock(QueryTelemetryLedgerUseCase.class);
        TelemetryRecord record = original(METRIC, T1, 1.0);
        when(useCase.revisionChain(DEVICE, METRIC, T1)).thenReturn(Flux.just(record));

        StepVerifier.create(useCase.revisionChain(DEVICE, METRIC, T1))
                .expectNext(record)
                .verifyComplete();
        verify(useCase).revisionChain(DEVICE, METRIC, T1);
    }
}
