package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;

class TelemetryPropertiesTest {

    private TelemetryProperties bind() {
        var source = new MapConfigurationPropertySource(Map.ofEntries(
                Map.entry("telemetry.reorder-window", "PT2S"),
                Map.entry("telemetry.reorder-buffer-capacity", "128"),
                Map.entry("telemetry.window-duration", "PT1S"),
                Map.entry("telemetry.window-max-events", "50"),
                Map.entry("telemetry.bus-capacity", "256"),
                Map.entry("telemetry.broadcast-capacity", "64"),
                Map.entry("telemetry.publisher-id", "ingest-1"),
                Map.entry("telemetry.data-key", "base64key"),
                Map.entry("telemetry.devices[0].id", "dev-1"),
                Map.entry("telemetry.devices[0].secret-hash", "hash-1"),
                Map.entry("telemetry.devices[0].scope", "ingest"),
                Map.entry("telemetry.consumers[0].id", "con-1"),
                Map.entry("telemetry.consumers[0].secret-hash", "hash-2"),
                Map.entry("telemetry.consumers[0].scope", "broadcast")));
        return new Binder(source).bind("telemetry", TelemetryProperties.class).get();
    }

    @Test
    void bind_durationFields_areRead() {
        var props = bind();

        assertThat(props.reorderWindow()).isEqualTo(Duration.ofSeconds(2));
        assertThat(props.windowDuration()).isEqualTo(Duration.ofSeconds(1));
    }

    @Test
    void bind_numericFields_areRead() {
        var props = bind();

        assertThat(props.reorderBufferCapacity()).isEqualTo(128);
        assertThat(props.windowMaxEvents()).isEqualTo(50);
        assertThat(props.busCapacity()).isEqualTo(256);
        assertThat(props.broadcastCapacity()).isEqualTo(64);
    }

    @Test
    void bind_stringFields_areRead() {
        var props = bind();

        assertThat(props.publisherId()).isEqualTo("ingest-1");
        assertThat(props.dataKey()).isEqualTo("base64key");
    }

    @Test
    void bind_devices_areReadAsCredentials() {
        var props = bind();

        assertThat(props.devices()).containsExactly(
                new TelemetryProperties.Credential("dev-1", "hash-1", "ingest"));
    }

    @Test
    void bind_consumers_areReadAsCredentials() {
        var props = bind();

        assertThat(props.consumers()).containsExactly(
                new TelemetryProperties.Credential("con-1", "hash-2", "broadcast"));
    }

    @Test
    void credential_accessors_returnConstructorValues() {
        var credential = new TelemetryProperties.Credential("id-9", "hash-9", "scope-9");

        assertThat(credential.id()).isEqualTo("id-9");
        assertThat(credential.secretHash()).isEqualTo("hash-9");
        assertThat(credential.scope()).isEqualTo("scope-9");
    }

    @Test
    void constructor_accessors_returnConstructorValues() {
        var devices = List.of(new TelemetryProperties.Credential("d", "h", "s"));
        var props = new TelemetryProperties(Duration.ofSeconds(3), 10, Duration.ofSeconds(4), 20, 30, 40,
                "pub", "key", devices, List.of());

        assertThat(props.devices()).isEqualTo(devices);
        assertThat(props.consumers()).isEmpty();
        assertThat(props.busCapacity()).isEqualTo(30);
    }
}
