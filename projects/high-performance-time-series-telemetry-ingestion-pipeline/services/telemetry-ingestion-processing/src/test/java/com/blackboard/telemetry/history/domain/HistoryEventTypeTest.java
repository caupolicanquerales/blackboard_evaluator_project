package com.blackboard.telemetry.history.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class HistoryEventTypeTest {

    @Test
    void values_declaredConstants_areExactlyTheThreeBroadcastKinds() {
        HistoryEventType[] values = HistoryEventType.values();

        assertThat(values).extracting(Enum::name)
                .containsExactly("SAMPLE_BACKFILLED", "REVISION_APPENDED", "WINDOW_BUFFERED");
    }

    @ParameterizedTest
    @EnumSource(HistoryEventType.class)
    void valueOf_constantName_returnsSameConstant(HistoryEventType type) {
        assertThat(HistoryEventType.valueOf(type.name())).isSameAs(type);
    }

    @Test
    void valueOf_unknownName_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> HistoryEventType.valueOf("SAMPLE_DELETED"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void valueOf_nullName_throwsNullPointerException() {
        assertThatThrownBy(() -> HistoryEventType.valueOf(null))
                .isInstanceOf(NullPointerException.class);
    }
}
