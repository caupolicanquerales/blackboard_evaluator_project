package com.pulsestream.telemetry.shared.config;

import java.time.Duration;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "telemetry")
public record TelemetryProperties(Duration reorderWindow, int reorderBufferCapacity, Duration windowDuration, int windowMaxEvents, int busCapacity, int broadcastCapacity, String publisherId, String dataKey, List<Credential> devices, List<Credential> consumers) {

    public record Credential(String id, String secretHash, String scope) {
    }

    @Override
    public List<Credential> devices() {
        return orEmpty(devices);
    }

    @Override
    public List<Credential> consumers() {
        return orEmpty(consumers);
    }

    private static List<Credential> orEmpty(List<Credential> credentials) {
        return credentials == null ? List.of() : credentials;
    }
}
