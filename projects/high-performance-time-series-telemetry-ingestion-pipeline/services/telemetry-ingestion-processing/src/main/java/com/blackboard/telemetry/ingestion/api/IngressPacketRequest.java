package com.blackboard.telemetry.ingestion.api;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.time.Instant;
import java.util.List;
import com.blackboard.telemetry.ingestion.domain.IngressPacket;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.SourceKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;

public record IngressPacketRequest(@NotBlank String deviceId, @NotBlank String sourceKind, @NotEmpty @Valid List<SampleRequest> samples) {

    public record SampleRequest(@NotBlank String metric, @NotNull Long tDeviceEpochMillis, @NotNull Double value) {
    }

    public IngressPacket toDomain(Instant tIngress) {
        SourceKind kind = SourceKind.valueOf(sourceKind);
        List<TelemetrySample> domainSamples = samples.stream().map(sample -> new TelemetrySample(deviceId, MetricKind.valueOf(sample.metric()), Instant.ofEpochMilli(sample.tDeviceEpochMillis()), tIngress, sample.value(), ValidationStatus.UNVALIDATED)).toList();
        return new IngressPacket(deviceId, kind, domainSamples);
    }
}
