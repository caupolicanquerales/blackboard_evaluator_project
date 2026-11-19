package com.pulsestream.telemetry.ingestion.api;

import java.security.Principal;
import java.time.Instant;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import com.pulsestream.telemetry.ingestion.application.IngestPacketUseCase;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.server.ServerWebInputException;
import java.util.Map;

@RestController
public class IngressPacketController {

    private final IngestPacketUseCase useCase;

    public IngressPacketController(IngestPacketUseCase useCase) {
        this.useCase = useCase;
    }

    @ExceptionHandler(ServerWebInputException.class)
    public ResponseEntity<Map<String, String>> invalidPacket(ServerWebInputException ex) {
        return ResponseEntity.badRequest().body(Map.of("code", "invalid_packet"));
    }

    @PostMapping(value = "/telemetry/ingress", consumes = MediaType.APPLICATION_JSON_VALUE)
    public Mono<ResponseEntity<IngressPacketResponse>> ingest(@Valid @RequestBody IngressPacketRequest request, Principal principal) {
        Flux<TelemetrySample> samples = Flux.fromIterable(request.samples()).map(s -> new TelemetrySample(request.deviceId(), s.metric(), s.tDevice(), Instant.EPOCH, s.value(), ValidationStatus.VALIDATED, s.payload()));
        return useCase.ingest(principal.getName(), samples).map(summary -> summary.refused() ? ResponseEntity.<IngressPacketResponse>status(HttpStatus.FORBIDDEN).build() : ResponseEntity.accepted().body(new IngressPacketResponse(summary.appended(), summary.rejectedValidation(), summary.revisions(), summary.duplicates())));
    }
}
