package com.blackboard.telemetry.ingestion.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.blackboard.telemetry.ingestion.api.IngressPacketRequest.SampleRequest;
import com.blackboard.telemetry.ingestion.domain.IngressPacket;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.SourceKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class IngressPacketRequestTest {

    private static final Instant T_INGRESS = Instant.parse("2026-01-01T00:00:10Z");
    private static final Validator VALIDATOR = Validation.buildDefaultValidatorFactory().getValidator();

    private static String source() {
        return SourceKind.values()[0].name();
    }

    private static SampleRequest sample() {
        return new SampleRequest("HEART_RATE", 1_000L, 150.0);
    }

    @Test
    void accessors_returnConstructorValues() {
        SampleRequest sample = sample();
        IngressPacketRequest request = new IngressPacketRequest("dev-1", source(), List.of(sample));

        assertThat(request.deviceId()).isEqualTo("dev-1");
        assertThat(request.sourceKind()).isEqualTo(source());
        assertThat(request.samples()).containsExactly(sample);
        assertThat(sample.metric()).isEqualTo("HEART_RATE");
        assertThat(sample.tDeviceEpochMillis()).isEqualTo(1_000L);
        assertThat(sample.value()).isEqualTo(150.0);
    }

    @Test
    void validate_validRequest_hasNoViolations() {
        assertThat(VALIDATOR.validate(new IngressPacketRequest("dev-1", source(), List.of(sample())))).isEmpty();
    }

    @Test
    void validate_blankDeviceId_reportsViolation() {
        var violations = VALIDATOR.validate(new IngressPacketRequest(" ", source(), List.of(sample())));

        assertThat(violations).extracting(v -> v.getPropertyPath().toString()).contains("deviceId");
    }

    @Test
    void validate_blankSourceKind_reportsViolation() {
        var violations = VALIDATOR.validate(new IngressPacketRequest("dev-1", "", List.of(sample())));

        assertThat(violations).extracting(v -> v.getPropertyPath().toString()).contains("sourceKind");
    }

    @Test
    void validate_emptySamples_reportsViolation() {
        var violations = VALIDATOR.validate(new IngressPacketRequest("dev-1", source(), List.of()));

        assertThat(violations).extracting(v -> v.getPropertyPath().toString()).contains("samples");
    }

    @Test
    void validate_nullSampleValue_reportsNestedViolation() {
        var request = new IngressPacketRequest("dev-1", source(), List.of(new SampleRequest("HEART_RATE", 1L, null)));

        assertThat(VALIDATOR.validate(request)).extracting(v -> v.getPropertyPath().toString())
                .anyMatch(p -> p.contains("value"));
    }

    @Test
    void validate_blankMetricAndNullTimestamp_reportNestedViolations() {
        var request = new IngressPacketRequest("dev-1", source(), List.of(new SampleRequest("", null, 1.0)));

        assertThat(VALIDATOR.validate(request)).extracting(v -> v.getPropertyPath().toString())
                .anyMatch(p -> p.contains("metric"))
                .anyMatch(p -> p.contains("tDeviceEpochMillis"));
    }

    @Test
    void toDomain_validRequest_mapsSamplesAsUnvalidatedWithIngressTime() {
        var request = new IngressPacketRequest("dev-1", source(), List.of(sample()));

        IngressPacket packet = request.toDomain(T_INGRESS);

        TelemetrySample mapped = packet.samples().get(0);
        assertThat(packet.deviceId()).isEqualTo("dev-1");
        assertThat(packet.sourceKind()).isEqualTo(SourceKind.valueOf(source()));
        assertThat(mapped.metric()).isEqualTo(MetricKind.HEART_RATE);
        assertThat(mapped.deviceId()).isEqualTo("dev-1");
        assertThat(mapped.tDevice()).isEqualTo(Instant.ofEpochMilli(1_000L));
        assertThat(mapped.tIngress()).isEqualTo(T_INGRESS);
        assertThat(mapped.value()).isEqualTo(150.0);
        assertThat(mapped.status()).isEqualTo(ValidationStatus.UNVALIDATED);
    }

    @Test
    void toDomain_unknownSourceKind_throwsIllegalArgumentException() {
        var request = new IngressPacketRequest("dev-1", "NOT_A_SOURCE", List.of(sample()));

        assertThatThrownBy(() -> request.toDomain(T_INGRESS)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void toDomain_unknownMetric_throwsIllegalArgumentException() {
        var request = new IngressPacketRequest("dev-1", source(), List.of(new SampleRequest("NOPE", 1L, 1.0)));

        assertThatThrownBy(() -> request.toDomain(T_INGRESS)).isInstanceOf(IllegalArgumentException.class);
    }
}
