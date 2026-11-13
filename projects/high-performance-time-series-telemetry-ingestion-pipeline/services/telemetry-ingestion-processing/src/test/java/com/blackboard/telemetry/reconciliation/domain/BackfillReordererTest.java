package com.blackboard.telemetry.reconciliation.domain;

import static org.assertj.core.api.Assertions.assertThat;

import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class BackfillReordererTest {

    private static final Instant BASE = Instant.parse("2024-01-01T00:00:00Z");

    private final BackfillReorderer reorderer = new BackfillReorderer();

    private static TelemetrySample sample(String id, long deviceOffset, long ingressOffset) {
        return new TelemetrySample(id, "temp", BASE.plusSeconds(deviceOffset), BASE.plusSeconds(ingressOffset), 1.0);
    }

    @Test
    void reorder_unorderedSamples_sortsAscendingByTDevice() {
        TelemetrySample a = sample("a", 30, 1);
        TelemetrySample b = sample("b", 10, 2);
        TelemetrySample c = sample("c", 20, 3);

        List<TelemetrySample> result = reorderer.reorder(List.of(a, b, c));

        assertThat(result).containsExactly(b, c, a);
    }

    @Test
    void reorder_differingTIngress_ignoresTIngress() {
        TelemetrySample a = sample("a", 10, 99);
        TelemetrySample b = sample("b", 20, 1);

        List<TelemetrySample> result = reorderer.reorder(List.of(b, a));

        assertThat(result).containsExactly(a, b);
    }

    @Test
    void reorder_equalTDevice_keepsInputOrder() {
        TelemetrySample a = sample("a", 10, 1);
        TelemetrySample b = sample("b", 10, 2);
        TelemetrySample c = sample("c", 10, 3);

        List<TelemetrySample> result = reorderer.reorder(List.of(c, a, b));

        assertThat(result).containsExactly(c, a, b);
    }

    @Test
    void reorder_emptyInput_returnsEmptyList() {
        assertThat(reorderer.reorder(List.of())).isEmpty();
    }

    @Test
    void reorder_mutableInput_isNotMutatedAndResultIsNewList() {
        TelemetrySample a = sample("a", 20, 1);
        TelemetrySample b = sample("b", 10, 2);
        List<TelemetrySample> input = new ArrayList<>(List.of(a, b));

        List<TelemetrySample> result = reorderer.reorder(input);

        assertThat(input).containsExactly(a, b);
        assertThat(result).isNotSameAs(input).containsExactly(b, a);
    }
}
