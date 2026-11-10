package com.pulsestream.telemetry.broadcasting.interfaces;

import java.util.Objects;
import com.pulsestream.telemetry.broadcasting.application.port.in.BroadcastTelemetryUseCase;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

@RestController
public class TelemetryStreamController {

    private final BroadcastTelemetryUseCase useCase;

    public TelemetryStreamController(BroadcastTelemetryUseCase useCase) {
        this.useCase = Objects.requireNonNull(useCase, "useCase must not be null");
    }

    @GetMapping(value = "/api/v1/telemetry/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<TelemetryStreamMessage> stream(@RequestParam(name = "deviceId", required = false) String deviceId) {
        return useCase.stream(deviceId).map(TelemetryStreamMessage::from);
    }
}
