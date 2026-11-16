package com.blackboard.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class SensorMetricBoundaryTest {

    private static SensorMetricBoundary heartRate() {
        return new SensorMetricBoundary(MetricKind.HEART_RATE, 30.0, 220.0, false, true);
    }

    @Test
    void accessors_returnConstructorValues() {
        SensorMetricBoundary boundary = new SensorMetricBoundary(MetricKind.SWIM_PACE, 10.0, 200.0, true, true);

        assertThat(boundary.metric()).isEqualTo(MetricKind.SWIM_PACE);
        assertThat(boundary.min()).isEqualTo(10.0);
        assertThat(boundary.max()).isEqualTo(200.0);
        assertThat(boundary.minExclusive()).isTrue();
        assertThat(boundary.enabled()).isTrue();
    }

    @Test
    void constructor_nullMetric_throwsNullPointerException() {
        assertThatThrownBy(() -> new SensorMetricBoundary(null, 0.0, 1.0, false, true))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_minGreaterThanMax_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> new SensorMetricBoundary(MetricKind.POWER, 10.0, 5.0, false, true))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_minEqualsMax_isAllowed() {
        SensorMetricBoundary boundary = new SensorMetricBoundary(MetricKind.POWER, 5.0, 5.0, false, true);

        assertThat(boundary.accepts(5.0)).isTrue();
    }

    @ParameterizedTest
    @CsvSource({"30.0,true", "150.0,true", "220.0,true", "29.99,false", "220.01,false", "300.0,false"})
    void accepts_inclusiveBoundary_matchesRange(double value, boolean expected) {
        assertThat(heartRate().accepts(value)).isEqualTo(expected);
    }

    @ParameterizedTest
    @CsvSource({"10.0,false", "10.01,true", "200.0,true", "200.01,false", "5.0,false"})
    void accepts_minExclusive_excludesMinimum(double value, boolean expected) {
        SensorMetricBoundary boundary = new SensorMetricBoundary(MetricKind.SWIM_PACE, 10.0, 200.0, true, true);

        assertThat(boundary.accepts(value)).isEqualTo(expected);
    }

    @Test
    void accepts_disabledBoundary_acceptsAnyValue() {
        SensorMetricBoundary boundary = new SensorMetricBoundary(MetricKind.HEART_RATE, 30.0, 220.0, false, false);

        assertThat(boundary.accepts(100000.0)).isTrue();
        assertThat(boundary.accepts(-5.0)).isTrue();
    }
}
