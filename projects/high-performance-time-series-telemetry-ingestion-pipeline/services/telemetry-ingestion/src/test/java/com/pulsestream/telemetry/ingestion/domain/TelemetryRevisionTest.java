package com.pulsestream.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetryRevisionTest {

    private static final Instant T_DEVICE = Instant.parse("2026-01-01T00:00:00Z");

    @Test
    void accessors_returnConstructorValues() {
        TelemetryRevision r = new TelemetryRevision("dev-1", "heart_rate", T_DEVICE, 2, 61.5, "correction");

        assertThat(r.deviceId()).isEqualTo("dev-1");
        assertThat(r.metric()).isEqualTo("heart_rate");
        assertThat(r.tDevice()).isEqualTo(T_DEVICE);
        assertThat(r.revisionNumber()).isEqualTo(2);
        assertThat(r.value()).isEqualTo(61.5);
        assertThat(r.reason()).isEqualTo("correction");
    }

    @ParameterizedTest
    @ValueSource(ints = {0, -1})
    void constructor_revisionNumberBelowOne_isRejected(int revisionNumber) {
        assertThatThrownBy(() -> new TelemetryRevision("dev-1", "heart_rate", T_DEVICE, revisionNumber, 1.0, "r"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_revisionNumberOne_isAccepted() {
        TelemetryRevision r = new TelemetryRevision("dev-1", "heart_rate", T_DEVICE, 1, 1.0, "initial");

        assertThat(r.revisionNumber()).isEqualTo(1);
    }
}
