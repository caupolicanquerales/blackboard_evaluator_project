package com.pulsestream.telemetry.intake.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNoException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

class SensorMetricBoundaryTest {

    private static SensorMetricBoundary range() {
        return new SensorMetricBoundary("temperature", -40.0, 125.0);
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {" ", "\t", "  \n"})
    void constructor_blankMetric_throwsIllegalArgument(String metric) {
        assertThatThrownBy(() -> new SensorMetricBoundary(metric, 0.0, 1.0))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_minGreaterThanMax_throwsIllegalArgument() {
        assertThatThrownBy(() -> new SensorMetricBoundary("temperature", 10.0, 5.0))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_minEqualsMax_isAccepted() {
        assertThatNoException().isThrownBy(() -> new SensorMetricBoundary("temperature", 5.0, 5.0));
    }

    @Test
    void constructor_nullMinAndMax_isAccepted() {
        assertThatNoException().isThrownBy(() -> new SensorMetricBoundary("temperature", null, null));
    }

    @Test
    void contains_valueInsideRange_returnsTrue() {
        assertThat(range().contains(20.0)).isTrue();
    }

    @Test
    void contains_valueEqualToMin_returnsTrue() {
        assertThat(range().contains(-40.0)).isTrue();
    }

    @Test
    void contains_valueEqualToMax_returnsTrue() {
        assertThat(range().contains(125.0)).isTrue();
    }

    @Test
    void contains_valueBelowMin_returnsFalse() {
        assertThat(range().contains(-40.1)).isFalse();
    }

    @Test
    void contains_valueAboveMax_returnsFalse() {
        assertThat(range().contains(125.1)).isFalse();
    }

    @Test
    void contains_nullMin_isUnboundedBelow() {
        SensorMetricBoundary boundary = new SensorMetricBoundary("temperature", null, 10.0);

        assertThat(boundary.contains(-1.0e300)).isTrue();
        assertThat(boundary.contains(10.5)).isFalse();
    }

    @Test
    void contains_nullMax_isUnboundedAbove() {
        SensorMetricBoundary boundary = new SensorMetricBoundary("temperature", 10.0, null);

        assertThat(boundary.contains(1.0e300)).isTrue();
        assertThat(boundary.contains(9.5)).isFalse();
    }

    @Test
    void contains_bothSidesNull_acceptsAnyFiniteValue() {
        assertThat(new SensorMetricBoundary("temperature", null, null).contains(42.0)).isTrue();
    }

    @Test
    void contains_nan_returnsFalse() {
        assertThat(range().contains(Double.NaN)).isFalse();
    }

    @Test
    void contains_nanOnUnboundedBoundary_returnsFalse() {
        assertThat(new SensorMetricBoundary("temperature", null, null).contains(Double.NaN)).isFalse();
    }

    @Test
    void contains_infinitiesOnUnboundedBoundary_returnsFalse() {
        SensorMetricBoundary boundary = new SensorMetricBoundary("temperature", null, null);

        assertThat(boundary.contains(Double.POSITIVE_INFINITY)).isFalse();
        assertThat(boundary.contains(Double.NEGATIVE_INFINITY)).isFalse();
    }

    @Test
    void contains_infinitiesOnBoundedBoundary_returnsFalse() {
        assertThat(range().contains(Double.POSITIVE_INFINITY)).isFalse();
        assertThat(range().contains(Double.NEGATIVE_INFINITY)).isFalse();
    }
}
