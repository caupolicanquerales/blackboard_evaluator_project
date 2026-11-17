package com.pulsestream.telemetry.eventlog.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import com.pulsestream.telemetry.shared.observability.AuditEntry;
import com.pulsestream.telemetry.shared.observability.AuditTrail;
import com.pulsestream.telemetry.shared.observability.StepLog;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class EventLogServiceTest {

    @Mock
    private EventLogRepository repository;
    @Mock
    private EventBroadcast broadcast;
    @Mock
    private AuditTrail auditTrail;
    @Mock
    private StepLog stepLog;

    private SimpleMeterRegistry registry;
    private EventLogService service;
    private final TelemetrySample sample = new TelemetrySample("dev-1", "temp",
            Instant.parse("2026-01-01T00:00:00Z"), Instant.parse("2026-01-01T00:00:01Z"), 21.5, "OK", "corr-1");

    @BeforeEach
    void setUp() {
        registry = new SimpleMeterRegistry();
        service = new EventLogService(repository, broadcast, auditTrail, stepLog, registry);
    }

    private void stubAudit() {
        when(auditTrail.record(any(AuditEntry.class))).thenReturn(Mono.empty());
    }

    private double count(String name, String tagKey, String tagValue) {
        return registry.get(name).tag(tagKey, tagValue).counter().count();
    }

    @Test
    void append_firstRecord_countsRecordAndEmitsRecordStep() {
        EventRecord record = new EventRecord(sample, 1, EventRecord.KIND_RECORD);
        when(repository.append(sample)).thenReturn(Mono.just(record));
        when(broadcast.publish(record)).thenReturn(true);
        stubAudit();

        StepVerifier.create(service.append(sample)).expectNext(record).verifyComplete();

        assertThat(count("telemetry.eventlog.appended", "kind", "record")).isEqualTo(1.0);
        verify(stepLog).emit("eventlog.record.appended", "corr-1");
    }

    @Test
    void append_revision_countsRevisionAndEmitsRevisionStep() {
        EventRecord record = new EventRecord(sample, 2, EventRecord.KIND_REVISION);
        when(repository.append(sample)).thenReturn(Mono.just(record));
        when(broadcast.publish(record)).thenReturn(true);
        stubAudit();

        StepVerifier.create(service.append(sample)).expectNext(record).verifyComplete();

        assertThat(count("telemetry.eventlog.appended", "kind", "revision")).isEqualTo(1.0);
        verify(stepLog).emit("eventlog.revision.appended", "corr-1");
    }

    @Test
    void append_broadcastAccepted_emitsBroadcastPublishedStep() {
        EventRecord record = new EventRecord(sample, 1, EventRecord.KIND_RECORD);
        when(repository.append(sample)).thenReturn(Mono.just(record));
        when(broadcast.publish(record)).thenReturn(true);
        stubAudit();

        StepVerifier.create(service.append(sample)).expectNext(record).verifyComplete();

        verify(stepLog).emit("eventlog.broadcast.published", "corr-1");
    }

    @Test
    void append_broadcastRefused_countsDroppedBroadcastAndKeepsRecord() {
        EventRecord record = new EventRecord(sample, 1, EventRecord.KIND_RECORD);
        when(repository.append(sample)).thenReturn(Mono.just(record));
        when(broadcast.publish(record)).thenReturn(false);
        stubAudit();

        StepVerifier.create(service.append(sample)).expectNext(record).verifyComplete();

        assertThat(count("telemetry.pipeline.dropped", "stage", "broadcast")).isEqualTo(1.0);
    }

    @Test
    void append_success_auditsSuccessEntryWithSampleCorrelation() {
        EventRecord record = new EventRecord(sample, 1, EventRecord.KIND_RECORD);
        when(repository.append(sample)).thenReturn(Mono.just(record));
        when(broadcast.publish(record)).thenReturn(true);
        stubAudit();

        StepVerifier.create(service.append(sample)).expectNext(record).verifyComplete();

        ArgumentCaptor<AuditEntry> captor = ArgumentCaptor.forClass(AuditEntry.class);
        verify(auditTrail).record(captor.capture());
        AuditEntry entry = captor.getValue();
        assertThat(entry.actor()).isEqualTo("eventlog");
        assertThat(entry.action()).isEqualTo("append");
        assertThat(entry.outcome()).isEqualTo("success");
        assertThat(entry.correlationId()).isEqualTo("corr-1");
        assertThat(entry.timestamp()).isNotNull();
    }

    @Test
    void append_repositoryFails_completesEmptyAndCountsDroppedEventlog() {
        when(repository.append(sample)).thenReturn(Mono.error(new IllegalStateException("db down")));
        stubAudit();

        StepVerifier.create(service.append(sample)).verifyComplete();

        assertThat(count("telemetry.pipeline.dropped", "stage", "eventlog")).isEqualTo(1.0);
    }

    @Test
    void append_repositoryFails_auditsFailureAndNeverBroadcasts() {
        when(repository.append(sample)).thenReturn(Mono.error(new IllegalStateException("db down")));
        stubAudit();

        StepVerifier.create(service.append(sample)).verifyComplete();

        ArgumentCaptor<AuditEntry> captor = ArgumentCaptor.forClass(AuditEntry.class);
        verify(auditTrail).record(captor.capture());
        assertThat(captor.getValue().outcome()).isEqualTo("failure");
        assertThat(captor.getValue().correlationId()).isEqualTo("corr-1");
        org.mockito.Mockito.verifyNoInteractions(broadcast);
    }
}
