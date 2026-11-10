package com.pulsestream.telemetry.intake.infrastructure;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.SensorMetricBoundary;
import com.pulsestream.telemetry.intake.domain.TelemetrySample.MetricType;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class ConfiguredBoundaryProviderTest {

    private static ConfiguredBoundaryProvider providerWith(Map<String, TelemetryProperties.Boundary> boundaries) {
        TelemetryProperties properties = mock(TelemetryProperties.class);
        when(properties.boundaries()).thenReturn(boundaries);
        return new ConfiguredBoundaryProvider(properties);
    }

    @Test
    void boundaryFor_configuredMetric_returnsBoundaryWithConfiguredLimits() {
        var provider = providerWith(Map.of("HEART_RATE", new TelemetryProperties.Boundary(30.0, 240.0, false)));

        Optional<SensorMetricBoundary> result = provider.boundaryFor(MetricType.HEART_RATE);

        assertThat(result).isPresent();
        SensorMetricBoundary boundary = result.get();
        assertThat(boundary.metricType()).isEqualTo(MetricType.HEART_RATE);
        assertThat(boundary.min()).isEqualTo(30.0);
        assertThat(boundary.max()).isEqualTo(240.0);
        assertThat(boundary.minExclusive()).isFalse();
    }

    @Test
    void boundaryFor_minExclusiveConfigured_preservesExclusivity() {
        var provider = providerWith(Map.of("SWIM_PACE", new TelemetryProperties.Boundary(45.0, 600.0, true)));

        Optional<SensorMetricBoundary> result = provider.boundaryFor(MetricType.SWIM_PACE);

        assertThat(result).isPresent();
        assertThat(result.get().minExclusive()).isTrue();
        assertThat(result.get().isWithin(45.0)).isFalse();
    }

    @Test
    void boundaryFor_metricWithoutEntry_returnsEmpty() {
        var provider = providerWith(Map.of("HEART_RATE", new TelemetryProperties.Boundary(30.0, 240.0, false)));

        assertThat(provider.boundaryFor(MetricType.POWER)).isEmpty();
    }

    @Test
    void boundaryFor_emptyConfiguration_returnsEmpty() {
        var provider = providerWith(Map.of());

        assertThat(provider.boundaryFor(MetricType.CADENCE)).isEmpty();
    }

    @Test
    void constructor_unknownMetricKey_failsFast() {
        var boundaries = Map.of("NOT_A_METRIC", new TelemetryProperties.Boundary(0.0, 10.0, false));

        assertThatThrownBy(() -> providerWith(boundaries)).isInstanceOf(IllegalArgumentException.class);
    }
}
