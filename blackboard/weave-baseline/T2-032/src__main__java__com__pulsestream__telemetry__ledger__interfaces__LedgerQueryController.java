package com.pulsestream.telemetry.ledger.interfaces;

import com.pulsestream.telemetry.ledger.application.port.in.QueryTelemetryLedgerUseCase;
import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import java.util.Objects;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

@RestController
public class LedgerQueryController {

    private final QueryTelemetryLedgerUseCase useCase;

    @GetMapping("/api/v1/ledger/devices/{deviceId}/records")
    public Flux<TelemetryRecordResponse> records(@PathVariable("deviceId") String deviceId, @RequestParam("from") Instant from, @RequestParam("to") Instant to, @RequestParam(name = "latestOnly", defaultValue = "false") boolean latestOnly) {
        Flux<TelemetryRecord> records = latestOnly ? useCase.latestHistory(deviceId, from, to) : useCase.history(deviceId, from, to);
        return records.map(TelemetryRecordResponse::from);
    }

    @GetMapping("/api/v1/ledger/devices/{deviceId}/revisions")
    public Flux<TelemetryRecordResponse> revisions(@PathVariable("deviceId") String deviceId, @RequestParam("metric") String metric, @RequestParam("tDevice") Instant tDevice) {
        return useCase.revisionChain(deviceId, metric, tDevice).map(TelemetryRecordResponse::from);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public void handleIllegalArgument(IllegalArgumentException ex) {
    }

    public void LedgerQueryController(QueryTelemetryLedgerUseCase useCase) {
        this.useCase = Objects.requireNonNull(useCase, "useCase");
    }
}
