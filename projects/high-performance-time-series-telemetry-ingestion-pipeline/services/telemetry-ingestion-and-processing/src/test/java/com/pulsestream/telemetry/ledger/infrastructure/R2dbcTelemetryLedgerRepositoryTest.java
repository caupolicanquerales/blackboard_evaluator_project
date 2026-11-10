package com.pulsestream.telemetry.ledger.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.ledger.domain.EventRevision;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.r2dbc.core.R2dbcEntityTemplate;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class R2dbcTelemetryLedgerRepositoryTest {

    private static final UUID RECORD_ID = UUID.fromString("00000000-0000-0000-0000-000000000001");

    @Mock
    private R2dbcEntityTemplate template;

    @Mock
    private TelemetrySample sample;

    private R2dbcTelemetryLedgerRepository repository;

    @BeforeEach
    void setUp() {
        repository = new R2dbcTelemetryLedgerRepository(template);
    }

    private EventRevision revision() {
        when(sample.recordId()).thenReturn(RECORD_ID);
        when(sample.deviceId()).thenReturn("device-1");
        when(sample.metricType()).thenReturn(TelemetrySample.MetricType.values()[0]);
        when(sample.value()).thenReturn(21.5);
        when(sample.deviceTimestamp()).thenReturn(Instant.parse("2025-01-01T00:00:00Z"));
        when(sample.ingressTimestamp()).thenReturn(Instant.parse("2025-01-01T00:00:05Z"));
        return EventRevision.original(sample, Instant.parse("2025-01-01T00:00:10Z"));
    }

    @Test
    void append_newRevision_insertsEntityAndReturnsRevision() {
        EventRevision revision = revision();
        when(template.insert(any(TelemetryRecordEventEntity.class)))
                .thenAnswer(inv -> Mono.just(inv.getArgument(0)));

        StepVerifier.create(repository.append(revision))
                .assertNext(saved -> assertThat(saved).usingRecursiveComparison().isEqualTo(revision))
                .verifyComplete();

        ArgumentCaptor<TelemetryRecordEventEntity> captor = ArgumentCaptor.forClass(TelemetryRecordEventEntity.class);
        verify(template).insert(captor.capture());
        assertThat(captor.getValue().toDomain()).usingRecursiveComparison().isEqualTo(revision);
    }

    @Test
    void append_newRevision_neverUpdatesOrDeletes() {
        EventRevision revision = revision();
        when(template.insert(any(TelemetryRecordEventEntity.class)))
                .thenAnswer(inv -> Mono.just(inv.getArgument(0)));

        StepVerifier.create(repository.append(revision)).expectNextCount(1).verifyComplete();

        verify(template, never()).update(any(TelemetryRecordEventEntity.class));
        verify(template, never()).delete(any(TelemetryRecordEventEntity.class));
    }

    @Test
    void append_duplicateRecordIdAndRevision_surfacesError() {
        EventRevision revision = revision();
        when(template.insert(any(TelemetryRecordEventEntity.class)))
                .thenReturn(Mono.error(new DataIntegrityViolationException("unique (record_id, revision_number)")));

        StepVerifier.create(repository.append(revision))
                .expectError(DataIntegrityViolationException.class)
                .verify();
    }
}
