package com.pulsestream.telemetry.validation.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class TelemetrySampleTest {

    private static final Instant T_DEVICE = Instant.parse("2025-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2025-01-01T10:00:01Z");

    private static TelemetrySample sample() {
        return new TelemetrySample("dev-1", "heart_rate", T_DEVICE, T_INGRESS, 142.5,
                TelemetrySample.STATUS_PENDING, "corr-1");
    }

    @Test
    void accessors_constructedSample_returnConstructorValues() {
        TelemetrySample s = sample();

        assertThat(s.deviceId()).isEqualTo("dev-1");
        assertThat(s.metric()).isEqualTo("heart_rate");
        assertThat(s.tDevice()).isEqualTo(T_DEVICE);
        assertThat(s.tIngress()).isEqualTo(T_INGRESS);
        assertThat(s.value()).isEqualTo(142.5);
        assertThat(s.status()).isEqualTo("PENDING");
        assertThat(s.correlationId()).isEqualTo("corr-1");
    }

    @Test
    void withStatus_newStatus_returnsCopyWithOnlyStatusReplaced() {
        TelemetrySample original = sample();

        TelemetrySample copy = original.withStatus(TelemetrySample.STATUS_VALID);

        assertThat(copy).isNotSameAs(original);
        assertThat(copy.status()).isEqualTo("VALID");
        assertThat(copy).usingRecursiveComparison().ignoringFields("status").isEqualTo(original);
    }

    @Test
    void withStatus_newStatus_leavesOriginalUnchanged() {
        TelemetrySample original = sample();

        original.withStatus(TelemetrySample.STATUS_VALIDATION_FAILED);

        assertThat(original).isEqualTo(sample());
    }

    @Test
    void withIngress_newInstant_returnsCopyWithOnlyIngressReplaced() {
        TelemetrySample original = sample();
        Instant later = T_INGRESS.plusSeconds(5);

        TelemetrySample copy = original.withIngress(later);

        assertThat(copy).isNotSameAs(original);
        assertThat(copy.tIngress()).isEqualTo(later);
        assertThat(copy).usingRecursiveComparison().ignoringFields("tIngress").isEqualTo(original);
    }

    @Test
    void withIngress_newInstant_leavesOriginalUnchanged() {
        TelemetrySample original = sample();

        original.withIngress(T_INGRESS.plusSeconds(5));

        assertThat(original.tIngress()).isEqualTo(T_INGRESS);
        assertThat(original).isEqualTo(sample());
    }

    @Test
    void statusConstants_values_matchContract() {
        assertThat(TelemetrySample.STATUS_PENDING).isEqualTo("PENDING");
        assertThat(TelemetrySample.STATUS_VALID).isEqualTo("VALID");
        assertThat(TelemetrySample.STATUS_VALIDATION_FAILED).isEqualTo("VALIDATION_FAILED");
    }
}
