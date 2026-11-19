package com.pulsestream.telemetry.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class RedactionPortTest {

    private final RedactionPort port = value -> "***" + value.length();

    @Test
    void mask_sameInputTwice_returnsSameOutput() {
        assertThat(port.mask("device-1")).isEqualTo(port.mask("device-1"));
    }

    @Test
    void mask_anyInput_returnsString() {
        String masked = port.mask("secret");

        assertThat(masked).isEqualTo("***6");
    }
}
