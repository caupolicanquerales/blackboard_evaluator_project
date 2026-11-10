package com.pulsestream.telemetry.ledger.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class EventRevisionTest {

    private static final UUID RECORD_ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final Instant DEVICE_TS = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant INGRESS_TS = Instant.parse("2024-01-01T00:00:01Z");
    private static final Instant RECORDED_AT = Instant.parse("2024-01-01T00:00:02Z");
    private static final Instant LATER = Instant.parse("2024-01-01T00:05:00Z");

    private static TelemetrySample sample(double value) {
        TelemetrySample sample = mock(TelemetrySample.class);
        when(sample.recordId()).thenReturn(RECORD_ID);
        when(sample.deviceId()).thenReturn("device-1");
        when(sample.metricType()).thenReturn(TelemetrySample.MetricType.values()[0]);
        when(sample.value()).thenReturn(value);
        when(sample.deviceTimestamp()).thenReturn(DEVICE_TS);
        when(sample.ingressTimestamp()).thenReturn(INGRESS_TS);
        return sample;
    }

    @Test
    void original_fromSample_buildsRevisionOneWithOriginalReason() {
        EventRevision revision = EventRevision.original(sample(1.5), RECORDED_AT);

        assertThat(revision.revisionNumber()).isEqualTo(1);
        assertThat(revision.reason()).isEqualTo(EventRevision.RevisionReason.ORIGINAL);
        assertThat(revision.recordedAt()).isEqualTo(RECORDED_AT);
    }

    @Test
    void original_fromSample_copiesSampleFields() {
        EventRevision revision = EventRevision.original(sample(1.5), RECORDED_AT);

        assertThat(revision.recordId()).isEqualTo(RECORD_ID);
        assertThat(revision.deviceId()).isEqualTo("device-1");
        assertThat(revision.metricType()).isEqualTo(TelemetrySample.MetricType.values()[0]);
        assertThat(revision.value()).isEqualTo(1.5);
        assertThat(revision.deviceTimestamp()).isEqualTo(DEVICE_TS);
        assertThat(revision.ingressTimestamp()).isEqualTo(INGRESS_TS);
    }

    @Test
    void next_withCorrection_incrementsRevisionNumberAndKeepsRecordId() {
        EventRevision first = EventRevision.original(sample(1.5), RECORDED_AT);

        EventRevision second = first.next(sample(2.5), EventRevision.RevisionReason.CORRECTION, LATER);

        assertThat(second.revisionNumber()).isEqualTo(2);
        assertThat(second.recordId()).isEqualTo(first.recordId());
        assertThat(second.reason()).isEqualTo(EventRevision.RevisionReason.CORRECTION);
        assertThat(second.value()).isEqualTo(2.5);
        assertThat(second.recordedAt()).isEqualTo(LATER);
    }

    @Test
    void next_withBackfill_usesBackfillReason() {
        EventRevision first = EventRevision.original(sample(1.5), RECORDED_AT);

        EventRevision second = first.next(sample(3.0), EventRevision.RevisionReason.BACKFILL, LATER);

        assertThat(second.reason()).isEqualTo(EventRevision.RevisionReason.BACKFILL);
    }

    @Test
    void next_afterAppending_leavesPreviousRevisionUnchanged() {
        EventRevision first = EventRevision.original(sample(1.5), RECORDED_AT);

        first.next(sample(2.5), EventRevision.RevisionReason.CORRECTION, LATER);

        assertThat(first.revisionNumber()).isEqualTo(1);
        assertThat(first.value()).isEqualTo(1.5);
        assertThat(first.reason()).isEqualTo(EventRevision.RevisionReason.ORIGINAL);
    }

    @Test
    void next_chained_producesConsecutiveRevisionNumbers() {
        EventRevision third = EventRevision.original(sample(1.0), RECORDED_AT)
                .next(sample(2.0), EventRevision.RevisionReason.CORRECTION, LATER)
                .next(sample(3.0), EventRevision.RevisionReason.CORRECTION, LATER);

        assertThat(third.revisionNumber()).isEqualTo(3);
    }
}
