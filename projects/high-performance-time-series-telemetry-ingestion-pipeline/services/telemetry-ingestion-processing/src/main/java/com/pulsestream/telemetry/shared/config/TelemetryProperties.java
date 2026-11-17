package com.pulsestream.telemetry.shared.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "telemetry")
public record TelemetryProperties(long reorderWindowSeconds, int bufferCapacity, double heartRateMin, double heartRateMax, double powerMin, double powerMax, double cadenceMin, double cadenceMax, double swimPaceMinExclusive) {
}
