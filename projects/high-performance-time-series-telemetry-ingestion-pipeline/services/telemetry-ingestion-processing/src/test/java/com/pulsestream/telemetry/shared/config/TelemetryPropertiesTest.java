package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class TelemetryPropertiesTest {

    private static final TelemetryProperties.Bounds TEMP = new TelemetryProperties.Bounds(-10.5, 90.25);

    private TelemetryProperties build() {
        return new TelemetryProperties(7L, 32, Map.of("temperature", TEMP));
    }

    @Test
    void reorderWindowSeconds_constructed_returnsConstructorValue() {
        assertThat(build().reorderWindowSeconds()).isEqualTo(7L);
    }

    @Test
    void busBufferCapacity_constructed_returnsConstructorValue() {
        assertThat(build().busBufferCapacity()).isEqualTo(32);
    }

    @Test
    void metricBounds_constructed_returnsConstructorEntries() {
        assertThat(build().metricBounds()).containsExactly(Map.entry("temperature", TEMP));
    }

    @Test
    void bounds_constructed_exposesMinAndMax() {
        assertThat(TEMP.min()).isEqualTo(-10.5);
        assertThat(TEMP.max()).isEqualTo(90.25);
    }

    @Test
    void boundsFor_knownMetric_returnsBounds() {
        assertThat(build().boundsFor("temperature")).isPresent().contains(TEMP);
    }

    @Test
    void boundsFor_unknownMetric_returnsEmpty() {
        assertThat(build().boundsFor("unknown")).isEmpty();
    }

    @ParameterizedTest
    @ValueSource(longs = {0L, -1L})
    void constructor_nonPositiveWindow_throwsIllegalArgument(long window) {
        assertThatThrownBy(() -> new TelemetryProperties(window, 32, Map.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(ints = {0, -1})
    void constructor_nonPositiveCapacity_throwsIllegalArgument(int capacity) {
        assertThatThrownBy(() -> new TelemetryProperties(7L, capacity, Map.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
