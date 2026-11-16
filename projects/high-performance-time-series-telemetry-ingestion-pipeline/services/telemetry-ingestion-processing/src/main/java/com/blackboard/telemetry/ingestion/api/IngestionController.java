package com.blackboard.telemetry.ingestion.api;

import com.blackboard.telemetry.ingestion.application.IngestPacketService;
import com.blackboard.telemetry.ingestion.domain.IngressPacket;
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
public class IngestionController {

    private final IngestPacketService service;

    private final Clock clock;

    public IngestionController(IngestPacketService service, Clock clock) {
        this.service = service;
        this.clock = clock;
    }

    @PostMapping(value = "/api/v1/telemetry/packets", consumes = MediaType.APPLICATION_JSON_VALUE)
    public Mono<ResponseEntity<Void>> ingest(@Valid @RequestBody IngressPacketRequest request) {
        IngressPacket packet;
        try {
            packet = request.toDomain(clock.instant());
        } catch (IllegalArgumentException ex) {
            return Mono.error(new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage(), ex));
        }
        return service.ingest(packet).then(Mono.fromSupplier(() -> ResponseEntity.accepted().<Void>build())).onErrorMap(IllegalStateException.class, ex -> new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, ex.getMessage(), ex));
    }
}
