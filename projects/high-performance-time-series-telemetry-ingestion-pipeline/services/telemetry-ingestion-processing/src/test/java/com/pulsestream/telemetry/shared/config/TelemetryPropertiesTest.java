package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;

class TelemetryPropertiesTest {

    private static TelemetryProperties bind() {
        Map<String, String> source = Map.of(
                "telemetry.reorder-window-seconds", "60",
                "telemetry.buffer-capacity", "128",
                "telemetry.heart-rate-min", "30",
                "telemetry.heart-rate-max", "240",
                "telemetry.power-min", "1",
                "telemetry.power-max", "2500",
                "telemetry.cadence-min", "2",
                "telemetry.cadence-max", "220",
                "telemetry.swim-pace-min-exclusive", "45.5");
        return new Binder(new MapConfigurationPropertySource(source))
                .bind("telemetry", TelemetryProperties.class).get();
    }

    @Test
    void reorderWindowSeconds_boundFromKey_returnsBoundValue() {
        assertThat(bind().reorderWindowSeconds()).isEqualTo(60L);
    }

    @Test
    void bufferCapacity_boundFromKey_returnsBoundValue() {
        assertThat(bind().bufferCapacity()).isEqualTo(128);
    }

    @Test
    void heartRateBounds_boundFromKeys_returnBoundValues() {
        TelemetryProperties p = bind();
        assertThat(p.heartRateMin()).isEqualTo(30.0);
        assertThat(p.heartRateMax()).isEqualTo(240.0);
    }

    @Test
    void powerBounds_boundFromKeys_returnBoundValues() {
        TelemetryProperties p = bind();
        assertThat(p.powerMin()).isEqualTo(1.0);
        assertThat(p.powerMax()).isEqualTo(2500.0);
    }

    @Test
    void cadenceBounds_boundFromKeys_returnBoundValues() {
        TelemetryProperties p = bind();
        assertThat(p.cadenceMin()).isEqualTo(2.0);
        assertThat(p.cadenceMax()).isEqualTo(220.0);
    }

    @Test
    void swimPaceMinExclusive_boundFromKey_returnsBoundValue() {
        assertThat(bind().swimPaceMinExclusive()).isEqualTo(45.5);
    }
}
