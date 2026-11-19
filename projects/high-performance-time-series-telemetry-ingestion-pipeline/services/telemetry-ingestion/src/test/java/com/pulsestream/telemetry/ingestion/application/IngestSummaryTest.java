package com.pulsestream.telemetry.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class IngestSummaryTest {

    @Test
    void accessors_processedPacket_returnConstructorValues() {
        IngestSummary summary = new IngestSummary(3, 2, 1, 4, false);

        assertThat(summary.appended()).isEqualTo(3);
        assertThat(summary.rejectedValidation()).isEqualTo(2);
        assertThat(summary.revisions()).isEqualTo(1);
        assertThat(summary.duplicates()).isEqualTo(4);
        assertThat(summary.refused()).isFalse();
    }

    @Test
    void refused_ownershipFailed_returnsTrue() {
        IngestSummary summary = new IngestSummary(0, 0, 0, 0, true);

        assertThat(summary.refused()).isTrue();
    }
}
