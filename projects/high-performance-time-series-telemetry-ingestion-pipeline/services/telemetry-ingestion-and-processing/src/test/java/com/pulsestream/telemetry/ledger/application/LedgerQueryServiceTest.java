package com.pulsestream.telemetry.ledger.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ledger.application.port.out.TelemetryLedgerRepository;
import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

class LedgerQueryServiceTest {

    private static final String DEVICE = "dev-1";
    private static final Instant T1 = Instant.parse("2025-01-01T00:00:00Z");
    private static final Instant T2 = Instant.parse("2025-01-01T00:00:01Z");
    private static final Instant T3 = Instant.parse("2025-01-01T00:00:02Z");

    private TelemetryLedgerRepository repository;
    private LedgerQueryService service;

    @BeforeEach
    void setUp() {
        repository = mock(TelemetryLedgerRepository.class);
        service = new LedgerQueryService(repository);
    }

    @Test
    void history_validRange_delegatesToRepository() {
        TelemetryRecord a = record("temp", T1, 0);
        TelemetryRecord b = record("temp", T2, 0);
        when(repository.findHistory(DEVICE, T1, T3)).thenReturn(Flux.just(a, b));

        StepVerifier.create(service.history(DEVICE, T1, T3))
                .expectNext(a, b)
                .verifyComplete();
    }

    @Test
    void history_fromEqualsToExclusive_throwsIllegalArgument() {
        assertThatThrownBy(() -> service.history(DEVICE, T1, T1))
                .isInstanceOf(IllegalArgumentException.class);
        verify(repository, never()).findHistory(DEVICE, T1, T1);
    }

    @Test
    void history_fromAfterToExclusive_throwsIllegalArgument() {
        assertThatThrownBy(() -> service.history(DEVICE, T3, T1))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void latestHistory_fromNotBeforeTo_throwsIllegalArgument() {
        assertThatThrownBy(() -> service.latestHistory(DEVICE, T2, T2))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void latestHistory_multipleRevisions_keepsHighestRevisionPerMetricAndTime() {
        TelemetryRecord original = record("temp", T1, 0);
        TelemetryRecord revised = record("temp", T1, 2);
        TelemetryRecord middle = record("temp", T1, 1);
        when(repository.findHistory(DEVICE, T1, T3))
                .thenReturn(Flux.just(original, revised, middle));

        StepVerifier.create(service.latestHistory(DEVICE, T1, T3))
                .expectNext(revised)
                .verifyComplete();
    }

    @Test
    void latestHistory_distinctMetricsAtSameTime_keepsEachMetric() {
        TelemetryRecord temp = record("temp", T1, 0);
        TelemetryRecord pressure = record("pressure", T1, 3);
        when(repository.findHistory(DEVICE, T1, T3)).thenReturn(Flux.just(temp, pressure));

        StepVerifier.create(service.latestHistory(DEVICE, T1, T3))
                .expectNext(temp, pressure)
                .verifyComplete();
    }

    @Test
    void latestHistory_multipleTimestamps_preservesTDeviceOrder() {
        TelemetryRecord first = record("temp", T1, 0);
        TelemetryRecord firstRev = record("temp", T1, 1);
        TelemetryRecord second = record("temp", T2, 0);
        when(repository.findHistory(DEVICE, T1, T3))
                .thenReturn(Flux.just(first, firstRev, second));

        StepVerifier.create(service.latestHistory(DEVICE, T1, T3))
                .expectNext(firstRev, second)
                .verifyComplete();
    }

    @Test
    void latestHistory_emptyHistory_completesEmpty() {
        when(repository.findHistory(DEVICE, T1, T3)).thenReturn(Flux.empty());

        StepVerifier.create(service.latestHistory(DEVICE, T1, T3)).verifyComplete();
    }

    @Test
    void revisionChain_existingEvent_delegatesToRepository() {
        TelemetryRecord a = record("temp", T1, 0);
        TelemetryRecord b = record("temp", T1, 1);
        when(repository.findRevisionChain(DEVICE, "temp", T1)).thenReturn(Flux.just(a, b));

        StepVerifier.create(service.revisionChain(DEVICE, "temp", T1))
                .expectNext(a, b)
                .verifyComplete();
    }

    @Test
    void revisionChain_unknownMetric_completesEmpty() {
        when(repository.findRevisionChain(DEVICE, "unknown", T1)).thenReturn(Flux.empty());

        StepVerifier.create(service.revisionChain(DEVICE, "unknown", T1)).verifyComplete();
    }

    private static TelemetryRecord record(String metric, Instant tDevice, int revision) {
        TelemetryRecord record = mock(TelemetryRecord.class);
        when(record.metric()).thenReturn(metric);
        when(record.tDevice()).thenReturn(tDevice);
        when(record.revision()).thenReturn(revision);
        return record;
    }
}
