package com.pulsestream.telemetry.eventlog.application;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.eventlog.domain.EventLogRepository;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class EventLogServiceTest {

    @Mock
    private EventLogRepository repository;

    @InjectMocks
    private EventLogService service;

    private final TelemetrySample sample =
            new TelemetrySample("dev-1", "temp", 1000L, 21.5, 2000L, TelemetrySample.VALID);

    @Test
    void record_delegatesToAppendRecordAndCompletes() {
        when(repository.appendRecord(sample)).thenReturn(Mono.just(true));

        StepVerifier.create(service.record(sample)).verifyComplete();

        verify(repository).appendRecord(sample);
    }

    @Test
    void record_duplicateSample_toleratedAndCompletes() {
        when(repository.appendRecord(sample)).thenReturn(Mono.just(false));

        StepVerifier.create(service.record(sample)).verifyComplete();
    }

    @Test
    void reconcile_delegatesToAppendRevision() {
        TelemetrySample revision = sample.withStatus(TelemetrySample.VALIDATION_FAILED);
        when(repository.appendRevision(revision)).thenReturn(Mono.empty());

        StepVerifier.create(service.reconcile(revision)).verifyComplete();

        verify(repository).appendRevision(revision);
    }

    @Test
    void reconcile_neverCallsAppendRecord() {
        when(repository.appendRevision(sample)).thenReturn(Mono.empty());

        StepVerifier.create(service.reconcile(sample)).verifyComplete();

        verify(repository, never()).appendRecord(any());
    }

    @Test
    void query_delegatesToFindByDeviceAndRange() {
        when(repository.findByDeviceAndRange("dev-1", 0L, 5000L)).thenReturn(Flux.just(sample));

        StepVerifier.create(service.query("dev-1", 0L, 5000L)).expectNext(sample).verifyComplete();

        verify(repository).findByDeviceAndRange("dev-1", 0L, 5000L);
    }
}
