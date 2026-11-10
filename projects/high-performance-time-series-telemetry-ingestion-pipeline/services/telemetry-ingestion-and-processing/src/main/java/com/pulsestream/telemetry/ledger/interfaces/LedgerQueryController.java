package com.pulsestream.telemetry.ledger.interfaces;

import com.pulsestream.telemetry.ledger.application.port.in.QueryTelemetryLedgerUseCase;
import java.time.Instant;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Flux;

@RestController
public class LedgerQueryController {

    private QueryTelemetryLedgerUseCase useCase;

    public LedgerQueryController(QueryTelemetryLedgerUseCase useCase) {
        this.useCase = useCase;
    }

    @GetMapping("/api/v1/ledger/devices/{deviceId}/revisions")
    public Flux<TelemetryRecordResponse> revisions(@PathVariable String deviceId, @RequestParam String metric, @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant tDevice) {
        return Flux.defer(() -> useCase.revisionChain(deviceId, metric, tDevice)).map(r -> new TelemetryRecordResponse(r.id(), r.deviceId(), r.metric(), r.value(), r.tDevice(), r.tIngress(), r.validationStatus(), r.revision(), r.supersedesId())).onErrorMap(IllegalArgumentException.class, e -> new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e));
    }

    @GetMapping("/api/v1/ledger/devices/{deviceId}/records")
    public Flux<TelemetryRecordResponse> records(@PathVariable String deviceId, @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant from, @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant to, @RequestParam(defaultValue = "false") boolean latestOnly) {
        return Flux.defer(() -> latestOnly ? useCase.latestHistory(deviceId, from, to) : useCase.history(deviceId, from, to)).map(r -> new TelemetryRecordResponse(r.id(), r.deviceId(), r.metric(), r.value(), r.tDevice(), r.tIngress(), r.validationStatus(), r.revision(), r.supersedesId())).onErrorMap(IllegalArgumentException.class, e -> new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e));
    }
}
