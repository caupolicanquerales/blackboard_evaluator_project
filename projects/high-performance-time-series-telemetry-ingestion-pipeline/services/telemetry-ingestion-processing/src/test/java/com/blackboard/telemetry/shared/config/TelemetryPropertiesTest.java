package com.blackboard.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.SensorMetricBoundary;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class TelemetryPropertiesTest {

    private static final Duration WINDOW = Duration.ofSeconds(60);
    private static final Duration RETRY = Duration.ofMillis(200);

    private static SensorMetricBoundary boundary() {
        return new SensorMetricBoundary(MetricKind.values()[0], 0.0, 100.0, false, true);
    }

    private static TelemetryProperties valid(List<SensorMetricBoundary> boundaries) {
        return new TelemetryProperties(WINDOW, 10, 20, 30, RETRY, boundaries);
    }

    @Test
    void accessors_validValues_returnConstructorValues() {
        List<SensorMetricBoundary> boundaries = List.of(boundary());

        TelemetryProperties props = valid(boundaries);

        assertThat(props.reorderWindow()).isEqualTo(WINDOW);
        assertThat(props.reorderBufferCapacity()).isEqualTo(10);
        assertThat(props.validatedStreamCapacity()).isEqualTo(20);
        assertThat(props.broadcastCapacity()).isEqualTo(30);
        assertThat(props.emitRetryTimeout()).isEqualTo(RETRY);
        assertThat(props.boundaries()).containsExactlyElementsOf(boundaries);
    }

    @Test
    void constructor_minimumCapacities_accepted() {
        TelemetryProperties props = new TelemetryProperties(WINDOW, 1, 1, 1, RETRY, List.of());

        assertThat(props.reorderBufferCapacity()).isEqualTo(1);
        assertThat(props.validatedStreamCapacity()).isEqualTo(1);
        assertThat(props.broadcastCapacity()).isEqualTo(1);
    }

    @Test
    void constructor_zeroReorderWindow_throwsIllegalArgument() {
        assertThatThrownBy(() -> new TelemetryProperties(Duration.ZERO, 1, 1, 1, RETRY, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_negativeReorderWindow_throwsIllegalArgument() {
        assertThatThrownBy(() -> new TelemetryProperties(Duration.ofSeconds(-1), 1, 1, 1, RETRY, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_zeroReorderBufferCapacity_throwsIllegalArgument() {
        assertThatThrownBy(() -> new TelemetryProperties(WINDOW, 0, 1, 1, RETRY, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_zeroValidatedStreamCapacity_throwsIllegalArgument() {
        assertThatThrownBy(() -> new TelemetryProperties(WINDOW, 1, 0, 1, RETRY, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_zeroBroadcastCapacity_throwsIllegalArgument() {
        assertThatThrownBy(() -> new TelemetryProperties(WINDOW, 1, 1, 0, RETRY, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_zeroEmitRetryTimeout_throwsIllegalArgument() {
        assertThatThrownBy(() -> new TelemetryProperties(WINDOW, 1, 1, 1, Duration.ZERO, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_negativeEmitRetryTimeout_throwsIllegalArgument() {
        assertThatThrownBy(() -> new TelemetryProperties(WINDOW, 1, 1, 1, Duration.ofMillis(-1), List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void boundaries_returnedList_isUnmodifiable() {
        TelemetryProperties props = valid(List.of(boundary()));

        assertThatThrownBy(() -> props.boundaries().add(boundary()))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void boundaries_sourceListMutatedAfterConstruction_isNotReflected() {
        List<SensorMetricBoundary> source = new ArrayList<>(List.of(boundary()));
        TelemetryProperties props = valid(source);

        source.add(boundary());

        assertThat(props.boundaries()).hasSize(1);
    }
}
