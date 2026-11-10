package com.pulsestream.telemetry.shared.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNoException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetryStreamPublishedEventTest {

    private static final Instant PUBLISHED_AT = Instant.parse("2024-01-01T00:00:00Z");

    @ParameterizedTest
    @ValueSource(strings = {"SAMPLE", "WINDOW"})
    void constructor_validKind_exposesComponents(String kind) {
        TelemetryStreamPublishedEvent event =
                new TelemetryStreamPublishedEvent(kind, "device-1", 3, PUBLISHED_AT);

        assertThat(event.kind()).isEqualTo(kind);
        assertThat(event.deviceId()).isEqualTo("device-1");
        assertThat(event.sampleCount()).isEqualTo(3);
        assertThat(event.publishedAt()).isEqualTo(PUBLISHED_AT);
    }

    @Test
    void constructor_sampleCountOne_isAccepted() {
        assertThatNoException()
                .isThrownBy(() -> new TelemetryStreamPublishedEvent("SAMPLE", "device-1", 1, PUBLISHED_AT));
    }

    @ParameterizedTest
    @ValueSource(ints = {0, -1, Integer.MIN_VALUE})
    void constructor_sampleCountBelowOne_throws(int sampleCount) {
        assertThatThrownBy(() -> new TelemetryStreamPublishedEvent("SAMPLE", "device-1", sampleCount, PUBLISHED_AT))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {" ", "   ", "\t"})
    void constructor_blankOrNullDeviceId_throws(String deviceId) {
        assertThatThrownBy(() -> new TelemetryStreamPublishedEvent("SAMPLE", deviceId, 1, PUBLISHED_AT))
                .isInstanceOfAny(IllegalArgumentException.class, NullPointerException.class);
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"sample", "OTHER", " SAMPLE", "window"})
    void constructor_invalidKind_throws(String kind) {
        assertThatThrownBy(() -> new TelemetryStreamPublishedEvent(kind, "device-1", 1, PUBLISHED_AT))
                .isInstanceOfAny(IllegalArgumentException.class, NullPointerException.class);
    }

    @Test
    void constructor_nullPublishedAt_throws() {
        assertThatThrownBy(() -> new TelemetryStreamPublishedEvent("WINDOW", "device-1", 1, null))
                .isInstanceOfAny(IllegalArgumentException.class, NullPointerException.class);
    }

    @Test
    void equals_sameComponents_areEqual() {
        TelemetryStreamPublishedEvent first =
                new TelemetryStreamPublishedEvent("WINDOW", "device-1", 2, PUBLISHED_AT);
        TelemetryStreamPublishedEvent second =
                new TelemetryStreamPublishedEvent("WINDOW", "device-1", 2, PUBLISHED_AT);

        assertThat(first).isEqualTo(second).hasSameHashCodeAs(second);
    }
}
