package com.pulsestream.telemetry.intake.api;

import java.time.Instant;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;
import com.pulsestream.telemetry.intake.application.IntakeTelemetryUseCase;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;

@RestController
@RequestMapping("/telemetry")
public class TelemetryIngressController {

    private final IntakeTelemetryUseCase useCase;

    public TelemetryIngressController(IntakeTelemetryUseCase useCase) {
        this.useCase = useCase;
    }

    public record TelemetrySampleRequest(@NotBlank String deviceId, @NotBlank String metric, @NotNull Double value, @NotNull Instant timestamp) {
    }

    @PostMapping("/samples")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public Mono<Void> ingest(@Valid @RequestBody TelemetrySampleRequest request) {
        return useCase.ingest(new TelemetrySample(request.deviceId(), request.metric(), request.value(), request.timestamp()));
    }
}
