package com.pulsestream.telemetry.ingestion.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class Sha256RedactionAdapterTest {

    private final Sha256RedactionAdapter adapter = new Sha256RedactionAdapter();

    @Test
    void mask_sameInputTwice_isDeterministic() {
        assertThat(adapter.mask("dev-secret")).isEqualTo(adapter.mask("dev-secret"));
    }

    @Test
    void mask_anyInput_differsFromInput() {
        assertThat(adapter.mask("dev-secret")).isNotEqualTo("dev-secret");
    }

    @Test
    void mask_anyInput_doesNotContainInput() {
        assertThat(adapter.mask("dev-secret")).doesNotContain("dev-secret");
    }

    @Test
    void mask_differentInputs_produceDifferentMasks() {
        assertThat(adapter.mask("dev-a")).isNotEqualTo(adapter.mask("dev-b"));
    }
}
