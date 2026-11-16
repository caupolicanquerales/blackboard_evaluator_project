package com.blackboard.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class MetricKindTest {

    @Test
    void values_called_returnsExactConstantsInOrder() {
        MetricKind[] result = MetricKind.values();

        assertThat(result).containsExactly(
                MetricKind.HEART_RATE, MetricKind.POWER, MetricKind.CADENCE, MetricKind.SWIM_PACE,
                MetricKind.GROUND_CONTACT_TIME, MetricKind.RESPIRATION, MetricKind.SWIM_STROKE);
    }

    @Test
    void values_called_hasSevenConstants() {
        assertThat(MetricKind.values()).hasSize(7);
    }

    @ParameterizedTest
    @ValueSource(strings = {"HEART_RATE", "POWER", "CADENCE", "SWIM_PACE", "GROUND_CONTACT_TIME",
            "RESPIRATION", "SWIM_STROKE"})
    void valueOf_knownName_returnsConstantWithSameName(String name) {
        MetricKind result = MetricKind.valueOf(name);

        assertThat(result.name()).isEqualTo(name);
    }

    @Test
    void valueOf_unknownName_throwsIllegalArgument() {
        assertThatThrownBy(() -> MetricKind.valueOf("SPEED")).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void valueOf_lowercaseName_throwsIllegalArgument() {
        assertThatThrownBy(() -> MetricKind.valueOf("power")).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void valueOf_nullName_throwsNullPointer() {
        assertThatThrownBy(() -> MetricKind.valueOf(null)).isInstanceOf(NullPointerException.class);
    }
}
