package com.pulsestream.telemetry.ingestion.api;

import java.time.Clock;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import com.pulsestream.telemetry.ingestion.application.IngestSamplesUseCase;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.springframework.web.server.ServerWebInputException;

@RestController
public class IngressController {

    private final IngestSamplesUseCase useCase;

    private final Clock clock;

    public IngressController(IngestSamplesUseCase useCase, Clock clock) {
        this.useCase = useCase;
        this.clock = clock;
    }

    @PostMapping("/api/v1/telemetry/packets")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public Mono<Long> receivePacket(@RequestBody Flux<@Valid IngressSampleDto> samples) {
        return useCase.ingest(samples.map(dto -> {
            if (!VALIDATOR.validate(dto).isEmpty()) {
                throw new ServerWebInputException("Invalid telemetry sample");
            }
            return dto.toDomain(clock.millis());
        })).count();
    }

    private static final Validator VALIDATOR = Validation.buildDefaultValidatorFactory().getValidator();
}
