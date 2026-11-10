package com.pulsestream.telemetry.ledger.application;

import com.pulsestream.telemetry.ledger.application.port.in.QueryTelemetryLedgerUseCase;
import com.pulsestream.telemetry.ledger.application.port.out.TelemetryLedgerRepository;
import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Objects;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

@Service
public class LedgerQueryService {

    private final TelemetryLedgerRepository repository;

    public LedgerQueryService(TelemetryLedgerRepository repository) {
        this.repository = Objects.requireNonNull(repository, "repository must not be null");
    }

    @Override
    public Flux<TelemetryRecord> history(String deviceId, Instant from, Instant toExclusive) {
        if (!from.isBefore(toExclusive)) {
            throw new IllegalArgumentException("from must be before toExclusive");
        }
        return repository.findHistory(deviceId, from, toExclusive);
    }

    @Override
    public Flux<TelemetryRecord> revisionChain(String deviceId, String metric, Instant tDevice) {
        return repository.findRevisionChain(deviceId, metric, tDevice);
    }

    @Override
    public Flux<TelemetryRecord> latestHistory(String deviceId, Instant from, Instant toExclusive) {
        return history(deviceId, from, toExclusive).collect(LinkedHashMap<List<Object>, TelemetryRecord>::new, (latest, record) -> latest.merge(List.of(record.metric(), record.tDevice()), record, (current, candidate) -> candidate.revision() > current.revision() ? candidate : current)).flatMapMany(latest -> Flux.fromIterable(latest.values()));
    }
}
