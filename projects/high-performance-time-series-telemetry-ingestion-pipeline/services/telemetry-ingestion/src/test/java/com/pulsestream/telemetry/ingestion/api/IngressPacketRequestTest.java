package com.pulsestream.telemetry.ingestion.api;

import static org.assertj.core.api.Assertions.assertThat;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import java.time.Instant;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;

class IngressPacketRequestTest {

    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();
    private static final Instant T = Instant.parse("2026-01-01T00:00:00Z");

    private static IngressPacketRequest.SampleDto sample(String metric, Double value) {
        return new IngressPacketRequest.SampleDto(metric, T, value, null);
    }

    private Set<ConstraintViolation<IngressPacketRequest>> validate(List<IngressPacketRequest.SampleDto> samples) {
        return validator.validate(new IngressPacketRequest("dev-1", samples));
    }

    @Test
    void validate_validPacket_noViolations() {
        assertThat(validate(List.of(sample("temp", 1.0)))).isEmpty();
    }

    @Test
    void validate_emptySamples_rejected() {
        assertThat(validate(Collections.emptyList())).isNotEmpty();
    }

    @Test
    void validate_exactly500Samples_accepted() {
        assertThat(validate(samples(500))).isEmpty();
    }

    @Test
    void validate_moreThan500Samples_rejected() {
        assertThat(validate(samples(501))).isNotEmpty();
    }

    @Test
    void validate_blankMetric_rejected() {
        assertThat(validate(List.of(sample("  ", 1.0)))).isNotEmpty();
    }

    @Test
    void validate_nullValue_rejected() {
        assertThat(validate(List.of(sample("temp", null)))).isNotEmpty();
    }

    @Test
    void accessors_returnConstructorValues() {
        IngressPacketRequest.SampleDto dto = new IngressPacketRequest.SampleDto("temp", T, 2.0, "p");
        IngressPacketRequest request = new IngressPacketRequest("dev-1", List.of(dto));

        assertThat(request.deviceId()).isEqualTo("dev-1");
        assertThat(request.samples()).containsExactly(dto);
        assertThat(List.of(dto.metric(), dto.tDevice(), dto.value(), dto.payload()))
                .containsExactly("temp", T, 2.0, "p");
    }

    private static List<IngressPacketRequest.SampleDto> samples(int n) {
        return IntStream.range(0, n).mapToObj(i -> sample("temp", 1.0)).collect(Collectors.toList());
    }
}
