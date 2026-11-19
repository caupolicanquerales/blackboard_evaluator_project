package com.pulsestream.telemetry.distribution.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class TrustedPublisherPolicyTest {

    private static final Instant T = Instant.parse("2025-01-01T00:00:00Z");
    private static final String TRUSTED = "pub-1";

    private static TelemetryEvent event(int schemaVersion, String key, String publisher) {
        return new TelemetryEvent(schemaVersion, TelemetryEvent.Type.values()[0], key, "dev-1",
                "temp", T, 1, 1.5, ValidationStatus.values()[0], publisher);
    }

    private final TrustedPublisherPolicy policy = new TrustedPublisherPolicy(TRUSTED);

    @Test
    void permits_trustedVersionedEventWithMatchingKey_returnsTrue() {
        var e = event(1, TelemetryEvent.keyOf("dev-1", "temp", T, 1), TRUSTED);

        assertThat(policy.permits(e)).isTrue();
    }

    @Test
    void permits_unknownPublisher_returnsFalse() {
        var e = event(1, TelemetryEvent.keyOf("dev-1", "temp", T, 1), "intruder");

        assertThat(policy.permits(e)).isFalse();
    }

    @Test
    void permits_wrongSchemaVersion_returnsFalse() {
        var e = event(999, TelemetryEvent.keyOf("dev-1", "temp", T, 1), TRUSTED);

        assertThat(policy.permits(e)).isFalse();
    }

    @Test
    void permits_keyNotMatchingPayloadDeviceId_returnsFalse() {
        var e = event(1, TelemetryEvent.keyOf("dev-2", "temp", T, 1), TRUSTED);

        assertThat(policy.permits(e)).isFalse();
    }
}
