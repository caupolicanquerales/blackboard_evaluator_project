package com.pulsestream.telemetry.intake.api;

import com.pulsestream.telemetry.intake.application.IntakeService;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.time.Instant;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.bind.support.WebExchangeBindException;
import reactor.core.publisher.Mono;

@Controller
@RequestMapping("/api/v1/telemetry")
public class TelemetryIngestController {

    private final IntakeService intakeService;

    public TelemetryIngestController(IntakeService intakeService) {
        this.intakeService = intakeService;
    }

    @ExceptionHandler(WebExchangeBindException.class)
    @ResponseBody
    public ProblemDetail handleValidation(WebExchangeBindException exception) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "Invalid telemetry packet");
        problem.setProperty("errors", exception.getFieldErrors().stream().map(error -> error.getField() + ": " + error.getDefaultMessage()).toList());
        return problem;
    }

    public record IngressPacketDto(@NotBlank String deviceId, @NotEmpty @Valid List<SampleDto> samples) {
    }

    public record SampleDto(@NotBlank String metric, @NotNull Instant tDevice, double value) {
    }

    public record IngressAck(int accepted) {
    }

    @PostMapping("/packets")
    @ResponseBody
    public Mono<ResponseEntity<IngressAck>> ingest(@Valid @RequestBody IngressPacketDto packet) {
        return Mono.deferContextual(context -> {
            String requestId = context.getOrDefault(CorrelationWebFilter.CONTEXT_KEY, "unknown");
            List<TelemetrySample> samples = packet.samples().stream().map(sample -> new TelemetrySample(packet.deviceId(), sample.metric(), sample.tDevice(), Instant.EPOCH, sample.value(), "PENDING", requestId)).toList();
            return intakeService.receive(samples);
        }).map(accepted -> ResponseEntity.status(HttpStatus.ACCEPTED).body(new IngressAck(accepted)));
    }
}
