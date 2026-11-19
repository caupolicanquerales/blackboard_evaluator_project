package com.pulsestream.telemetry.ingestion.api;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record IngressPacketRequest(String deviceId, @NotEmpty @Size(max = 500) @Valid List<SampleDto> samples) {

    @JsonCreator
    static IngressPacketRequest fromWire(@JsonProperty("deviceId") String deviceId,
            @JsonProperty("samples") List<SampleDto> samples,
            @JsonProperty("metric") String metric,
            @JsonProperty("tDevice") Instant tDevice,
            @JsonProperty("value") Double value,
            @JsonProperty("payload") String payload) {
        if (samples == null && (metric != null || tDevice != null || value != null)) {
            samples = List.of(new SampleDto(metric, tDevice, value, payload));
        }
        return new IngressPacketRequest(deviceId, samples);
    }

    record SampleDto(@NotBlank String metric, @NotNull Instant tDevice, @NotNull Double value, @Size(max = 1024) String payload) {
    }
}
