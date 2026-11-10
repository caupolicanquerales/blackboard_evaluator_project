package com.pulsestream.telemetry.intake.interfaces;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.intake.application.IngressPacket;
import com.pulsestream.telemetry.intake.interfaces.IngressPacketRequest.SampleRequest;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class IngressPacketRequestTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:01Z");

    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    private static SampleRequest sample(String metric, Double value, Instant tDevice) {
        return new SampleRequest(metric, value, tDevice);
    }

    private static SampleRequest validSample() {
        return sample("temperature", 20.5, T_DEVICE);
    }

    private Set<String> invalidPaths(IngressPacketRequest request) {
        return validator.validate(request).stream()
                .map(ConstraintViolation::getPropertyPath)
                .map(Object::toString)
                .collect(Collectors.toSet());
    }

    @Test
    void validate_validRequest_hasNoViolations() {
        var request = new IngressPacketRequest("dev-1", List.of(validSample()));

        assertThat(validator.validate(request)).isEmpty();
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   "})
    void validate_blankDeviceId_reportsDeviceId(String deviceId) {
        var request = new IngressPacketRequest(deviceId, List.of(validSample()));

        assertThat(invalidPaths(request)).containsExactly("deviceId");
    }

    @Test
    void validate_nullDeviceId_reportsDeviceId() {
        var request = new IngressPacketRequest(null, List.of(validSample()));

        assertThat(invalidPaths(request)).containsExactly("deviceId");
    }

    @Test
    void validate_emptySamples_reportsSamples() {
        var request = new IngressPacketRequest("dev-1", List.of());

        assertThat(invalidPaths(request)).containsExactly("samples");
    }

    @Test
    void validate_nullSamples_reportsSamples() {
        var request = new IngressPacketRequest("dev-1", null);

        assertThat(invalidPaths(request)).containsExactly("samples");
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "  "})
    void validate_blankMetric_reportsNestedMetric(String metric) {
        var request = new IngressPacketRequest("dev-1", List.of(sample(metric, 1.0, T_DEVICE)));

        assertThat(invalidPaths(request)).containsExactly("samples[0].metric");
    }

    @Test
    void validate_nullValue_reportsNestedValue() {
        var request = new IngressPacketRequest("dev-1", List.of(sample("temperature", null, T_DEVICE)));

        assertThat(invalidPaths(request)).containsExactly("samples[0].value");
    }

    @Test
    void validate_nullTDevice_reportsNestedTDevice() {
        var request = new IngressPacketRequest("dev-1", List.of(sample("temperature", 1.0, null)));

        assertThat(invalidPaths(request)).containsExactly("samples[0].tDevice");
    }

    @Test
    void validate_invalidSecondSample_reportsIndexedPath() {
        var request = new IngressPacketRequest("dev-1", List.of(validSample(), sample("", 1.0, T_DEVICE)));

        assertThat(invalidPaths(request)).containsExactly("samples[1].metric");
    }

    @Test
    void toPacket_validRequest_mapsDeviceIdIngressAndAllSamples() {
        var request = new IngressPacketRequest("dev-1",
                List.of(validSample(), sample("humidity", 40.0, T_DEVICE)));

        IngressPacket packet = request.toPacket(T_INGRESS);

        assertThat(packet.deviceId()).isEqualTo("dev-1");
        assertThat(packet.tIngress()).isEqualTo(T_INGRESS);
        assertThat(packet.samples()).hasSize(2);
        assertThat(packet.samples()).allSatisfy(s -> assertThat(s.deviceId()).isEqualTo("dev-1"));
    }
}
