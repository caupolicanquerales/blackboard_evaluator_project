package com.blackboard.telemetry.ingestion.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class SourceKindTest {

    @Test
    void values_called_returnsExactlyTheThreeOrigins() {
        SourceKind[] result = SourceKind.values();

        assertThat(result.length).isEqualTo(3);
        assertThat(result[0].name()).isEqualTo("EDGE_DEVICE");
        assertThat(result[1].name()).isEqualTo("BIKE_COMPUTER");
        assertThat(result[2].name()).isEqualTo("SMART_WEARABLE");
    }

    @ParameterizedTest
    @EnumSource(SourceKind.class)
    void valueOf_existingName_returnsSameConstant(SourceKind kind) {
        assertThat(SourceKind.valueOf(kind.name())).isSameAs(kind);
    }

    @Test
    void valueOf_unknownName_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> SourceKind.valueOf("TOASTER"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
