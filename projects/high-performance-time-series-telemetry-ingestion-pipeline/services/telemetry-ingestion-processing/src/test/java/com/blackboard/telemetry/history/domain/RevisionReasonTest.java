package com.blackboard.telemetry.history.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class RevisionReasonTest {

    @Test
    void values_called_returnsExactlyBackfillAndCorrectionInOrder() {
        RevisionReason[] result = RevisionReason.values();

        assertThat(result).containsExactly(RevisionReason.BACKFILL, RevisionReason.CORRECTION);
    }

    @Test
    void valueOf_backfillName_returnsBackfill() {
        assertThat(RevisionReason.valueOf("BACKFILL")).isEqualTo(RevisionReason.BACKFILL);
    }

    @Test
    void valueOf_correctionName_returnsCorrection() {
        assertThat(RevisionReason.valueOf("CORRECTION")).isEqualTo(RevisionReason.CORRECTION);
    }

    @Test
    void valueOf_unknownName_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> RevisionReason.valueOf("UNKNOWN"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
