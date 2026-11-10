package com.pulsestream.telemetry.intake.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.intake.domain.SensorMetricBoundary;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.intake.domain.TelemetrySample.MetricType;
import com.pulsestream.telemetry.intake.domain.TelemetrySample.ValidationStatus;
import java.time.Instant;
import java.util.EnumMap;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class SensorMetricBoundaryProviderTest {

    private static final Instant T = Instant.parse("2024-01-01T00:00:00Z");

    private static SensorMetricBoundaryProvider providerWith(Map<MetricType, SensorMetricBoundary> boundaries) {
        return metricType -> Optional.ofNullable(boundaries.get(metricType));
    }

    private static TelemetrySample sample(MetricType type, double value) {
        return new TelemetrySample(
                TelemetrySample.recordIdFor("dev-1", type, T),
                "dev-1", type, value, T, T, ValidationStatus.VALID);
    }

    @Test
    void boundaryFor_configuredMetric_returnsItsBoundary() {
        SensorMetricBoundary hr = new SensorMetricBoundary(MetricType.HEART_RATE, 30, 240, false);
        SensorMetricBoundaryProvider provider = providerWith(Map.of(MetricType.HEART_RATE, hr));

        Optional<SensorMetricBoundary> result = provider.boundaryFor(MetricType.HEART_RATE);

        assertThat(result).isPresent().contains(hr);
    }

    @ParameterizedTest
    @EnumSource(MetricType.class)
    void boundaryFor_noBoundaryConfigured_returnsEmpty(MetricType type) {
        SensorMetricBoundaryProvider provider = providerWith(new EnumMap<>(MetricType.class));

        assertThat(provider.boundaryFor(type)).isEmpty();
    }

    @Test
    void boundaryFor_onlyOtherMetricConfigured_returnsEmptyForRequestedMetric() {
        SensorMetricBoundary hr = new SensorMetricBoundary(MetricType.HEART_RATE, 30, 240, false);
        SensorMetricBoundaryProvider provider = providerWith(Map.of(MetricType.HEART_RATE, hr));

        assertThat(provider.boundaryFor(MetricType.POWER)).isEmpty();
    }

    @Test
    void boundaryFor_returnedBoundary_validatesSampleOutsideLimitAsFailedKeepingPayload() {
        SensorMetricBoundary hr = new SensorMetricBoundary(MetricType.HEART_RATE, 30, 240, false);
        SensorMetricBoundaryProvider provider = providerWith(Map.of(MetricType.HEART_RATE, hr));
        TelemetrySample outOfRange = sample(MetricType.HEART_RATE, 300);

        TelemetrySample result = provider.boundaryFor(MetricType.HEART_RATE).orElseThrow().validate(outOfRange);

        assertThat(result.validationStatus()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
        assertThat(result.value()).isEqualTo(300);
    }
}
