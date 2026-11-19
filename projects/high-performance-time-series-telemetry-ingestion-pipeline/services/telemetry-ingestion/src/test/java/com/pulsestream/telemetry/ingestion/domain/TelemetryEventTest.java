package com.pulsestream.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class TelemetryEventTest {

    private static final Instant T_DEVICE = Instant.parse("2026-01-01T00:00:00Z");

    private static TelemetryEvent event(int revision) {
        TelemetryEvent.Type type = TelemetryEvent.Type.values()[0];
        return new TelemetryEvent(1, type, "key", "dev-1", "heart_rate", T_DEVICE, revision, 60.5,
                ValidationStatus.VALIDATED, "pub-1");
    }

    @Test
    void accessors_returnConstructorValues() {
        TelemetryEvent e = event(2);

        assertThat(e.schemaVersion()).isEqualTo(1);
        assertThat(e.type()).isEqualTo(TelemetryEvent.Type.values()[0]);
        assertThat(e.eventKey()).isEqualTo("key");
        assertThat(e.deviceId()).isEqualTo("dev-1");
        assertThat(e.metric()).isEqualTo("heart_rate");
        assertThat(e.tDevice()).isEqualTo(T_DEVICE);
        assertThat(e.revision()).isEqualTo(2);
        assertThat(e.value()).isEqualTo(60.5);
        assertThat(e.status()).isEqualTo(ValidationStatus.VALIDATED);
        assertThat(e.publisherId()).isEqualTo("pub-1");
    }

    @Test
    void keyOf_joinsFieldsWithPipes() {
        assertThat(TelemetryEvent.keyOf("dev-1", "heart_rate", T_DEVICE, 3))
                .isEqualTo("dev-1|heart_rate|" + T_DEVICE + "|3");
    }

    @Test
    void constructor_revisionBelowOne_isRejected() {
        assertThatThrownBy(() -> event(0)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_revisionOne_isAccepted() {
        assertThat(event(1).revision()).isEqualTo(1);
    }

    @Test
    void type_declaresConstants() {
        assertThat(TelemetryEvent.Type.values()).isNotEmpty();
    }
}
