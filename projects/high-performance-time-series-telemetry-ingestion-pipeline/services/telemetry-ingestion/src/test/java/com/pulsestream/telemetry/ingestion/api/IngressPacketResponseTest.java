package com.pulsestream.telemetry.ingestion.api;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class IngressPacketResponseTest {

    @Test
    void accessors_constructedValues_returnSameValues() {
        IngressPacketResponse response = new IngressPacketResponse(4, 3, 2, 1);

        assertThat(response.appended()).isEqualTo(4);
        assertThat(response.rejectedValidation()).isEqualTo(3);
        assertThat(response.revisions()).isEqualTo(2);
        assertThat(response.duplicates()).isEqualTo(1);
    }
}
