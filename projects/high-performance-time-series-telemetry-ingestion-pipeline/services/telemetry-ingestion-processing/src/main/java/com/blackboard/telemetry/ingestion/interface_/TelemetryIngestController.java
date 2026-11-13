package com.blackboard.telemetry.ingestion.interface_;

import java.util.UUID;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import com.blackboard.telemetry.ingestion.application.IngestTelemetryUseCase;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;

@RestController
public class TelemetryIngestController {

    private final IngestTelemetryUseCase useCase;

    public TelemetryIngestController(IngestTelemetryUseCase useCase) {
        this.useCase = useCase;
    }

    @PostMapping(value = "/api/v1/telemetry/ingress", consumes = "application/x-ndjson", produces = "application/json")
    public Mono<Long> ingest(@RequestBody Flux<TelemetrySample> samples, @RequestHeader(value = "X-Request-Id", required = false) String requestId) {
        String correlationId = (requestId == null || requestId.isBlank()) ? UUID.randomUUID().toString() : requestId;
        return useCase.ingest(samples, correlationId);
    }
}
