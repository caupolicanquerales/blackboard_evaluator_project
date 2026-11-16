package com.blackboard.telemetry.history.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class HistoryEventTest {

    private static final HistoryEventType TYPE = HistoryEventType.values()[0];

    private static TelemetrySample sample() {
        return new TelemetrySample("dev-1", MetricKind.values()[0],
                Instant.parse("2026-01-01T00:00:00Z"), Instant.parse("2026-01-01T00:00:01Z"),
                21.5, ValidationStatus.UNVALIDATED);
    }

    @Test
    void accessors_validArguments_returnConstructorValues() {
        TelemetrySample sample = sample();

        HistoryEvent event = new HistoryEvent(TYPE, sample, 1, 3, "req-1");

        assertThat(event.type()).isEqualTo(TYPE);
        assertThat(event.sample()).isEqualTo(sample);
        assertThat(event.revisionNo()).isEqualTo(1);
        assertThat(event.windowSize()).isEqualTo(3);
        assertThat(event.correlationId()).isEqualTo("req-1");
    }

    @Test
    void constructor_zeroRevisionAndWindow_isAccepted() {
        HistoryEvent event = new HistoryEvent(TYPE, sample(), 0, 0, "req-1");

        assertThat(event.revisionNo()).isZero();
        assertThat(event.windowSize()).isZero();
    }

    @Test
    void constructor_negativeRevisionNo_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> new HistoryEvent(TYPE, sample(), -1, 0, "req-1"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_negativeWindowSize_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> new HistoryEvent(TYPE, sample(), 0, -1, "req-1"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_nullType_throwsNullPointerException() {
        assertThatThrownBy(() -> new HistoryEvent(null, sample(), 0, 0, "req-1"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullSample_throwsNullPointerException() {
        assertThatThrownBy(() -> new HistoryEvent(TYPE, null, 0, 0, "req-1"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullCorrelationId_throwsNullPointerException() {
        assertThatThrownBy(() -> new HistoryEvent(TYPE, sample(), 0, 0, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_blankCorrelationId_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> new HistoryEvent(TYPE, sample(), 0, 0, "  "))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
