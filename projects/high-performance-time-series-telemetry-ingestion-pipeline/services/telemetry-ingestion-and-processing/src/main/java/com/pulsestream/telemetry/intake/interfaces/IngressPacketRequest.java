package com.pulsestream.telemetry.intake.interfaces;

import com.pulsestream.telemetry.intake.application.IngressPacket;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.time.Instant;
import java.util.List;

public record IngressPacketRequest(@NotBlank String deviceId, @NotEmpty List<SampleRequest> samples) {

    public record SampleRequest(@NotBlank String metric, @NotNull Double value, @NotNull Instant tDevice) {
    }

    public IngressPacket toPacket(Instant tIngress) {
        List<TelemetrySample> mapped = samples.stream().map(s -> TelemetrySample.unvalidated(deviceId, s.metric(), s.value(), s.tDevice(), tIngress)).toList();
        return new IngressPacket(deviceId, tIngress, mapped);
    }
}
