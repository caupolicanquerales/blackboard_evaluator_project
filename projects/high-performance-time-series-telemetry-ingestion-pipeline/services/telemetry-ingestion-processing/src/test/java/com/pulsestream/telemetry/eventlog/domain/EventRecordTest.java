package com.pulsestream.telemetry.eventlog.domain;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class EventRecordTest {

    private static TelemetrySample sample() {
        return new TelemetrySample("dev-1", "temp", Instant.parse("2026-01-01T00:00:00Z"),
                Instant.parse("2026-01-01T00:00:01Z"), 21.5, "OK", "corr-1");
    }

    @Test
    void accessors_constructedRecord_returnConstructorValues() {
        TelemetrySample sample = sample();

        EventRecord record = new EventRecord(sample, 3, "REVISION");

        assertThat(record.sample()).isEqualTo(sample);
        assertThat(record.revision()).isEqualTo(3);
        assertThat(record.kind()).isEqualTo("REVISION");
    }

    @Test
    void equals_sameComponents_areEqual() {
        EventRecord a = new EventRecord(sample(), 1, "RECORD");
        EventRecord b = new EventRecord(sample(), 1, "RECORD");

        assertThat(a).isEqualTo(b).hasSameHashCodeAs(b);
    }

    @Test
    void equals_differentRevision_areNotEqual() {
        EventRecord a = new EventRecord(sample(), 1, "RECORD");
        EventRecord b = new EventRecord(sample(), 2, "RECORD");

        assertThat(a).isNotEqualTo(b);
    }

    @Test
    void kindConstants_haveContractValues() {
        assertThat(EventRecord.KIND_RECORD).isEqualTo("RECORD");
        assertThat(EventRecord.KIND_REVISION).isEqualTo("REVISION");
    }
}
