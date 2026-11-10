package com.pulsestream.telemetry.intake.interfaces;

import com.pulsestream.telemetry.intake.application.IngressPacket;
import com.pulsestream.telemetry.intake.application.port.in.IngestTelemetryUseCase;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import jakarta.validation.Valid;
import java.time.Clock;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Mono;

@RestController
public class IngressController {

    private final IngestTelemetryUseCase useCase;

    private final Clock clock;

    public IngressController(IngestTelemetryUseCase useCase, Clock clock) {
        this.useCase = useCase;
        this.clock = clock;
    }

    public record IngressAcknowledgement(String deviceId, int accepted) {
    }

    @PostMapping(value = "/api/v1/telemetry/packets", consumes = MediaType.APPLICATION_JSON_VALUE)
    public Mono<ResponseEntity<IngressAcknowledgement>> ingest(@Valid @RequestBody IngressPacketRequest request) {
        IngressPacket packet = request.toPacket(clock.instant());
        return useCase.ingest(packet).map(accepted -> ResponseEntity.status(HttpStatus.ACCEPTED).body(new IngressAcknowledgement(request.deviceId(), accepted))).onErrorMap(BoundedEventChannel.OverflowException.class, e -> new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, e.getMessage(), e));
    }
}
