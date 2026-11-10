package com.pulsestream.telemetry.ledger.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.ledger.domain.EventRevision;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class TelemetryRecordEventEntityTest {

    private static final UUID RECORD_ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final Instant RECORDED_AT = Instant.parse("2025-01-01T00:00:10Z");

    @Mock
    private TelemetrySample sample;

    private EventRevision original() {
        when(sample.recordId()).thenReturn(RECORD_ID);
        when(sample.deviceId()).thenReturn("device-1");
        when(sample.metricType()).thenReturn(TelemetrySample.MetricType.values()[0]);
        when(sample.value()).thenReturn(21.5);
        when(sample.deviceTimestamp()).thenReturn(Instant.parse("2025-01-01T00:00:00Z"));
        when(sample.ingressTimestamp()).thenReturn(Instant.parse("2025-01-01T00:00:05Z"));
        return EventRevision.original(sample, RECORDED_AT);
    }

    @Test
    void toDomain_afterFromDomain_returnsEquivalentRevision() {
        EventRevision revision = original();

        EventRevision result = TelemetryRecordEventEntity.fromDomain(revision).toDomain();

        assertThat(result).usingRecursiveComparison().isEqualTo(revision);
    }

    @Test
    void fromDomain_originalRevision_preservesIdentityFields() {
        EventRevision revision = original();

        EventRevision result = TelemetryRecordEventEntity.fromDomain(revision).toDomain();

        assertThat(result.recordId()).isEqualTo(RECORD_ID);
        assertThat(result.revisionNumber()).isEqualTo(revision.revisionNumber());
        assertThat(result.reason()).isEqualTo(revision.reason());
        assertThat(result.deviceId()).isEqualTo("device-1");
        assertThat(result.value()).isEqualTo(21.5);
    }

    @Test
    void toDomain_afterCorrectionRevision_preservesRevisionNumberAndReason() {
        EventRevision next = original().next(sample, EventRevision.RevisionReason.values()[1], RECORDED_AT.plusSeconds(5));

        EventRevision result = TelemetryRecordEventEntity.fromDomain(next).toDomain();

        assertThat(result.revisionNumber()).isEqualTo(next.revisionNumber());
        assertThat(result.reason()).isEqualTo(EventRevision.RevisionReason.values()[1]);
    }
}
