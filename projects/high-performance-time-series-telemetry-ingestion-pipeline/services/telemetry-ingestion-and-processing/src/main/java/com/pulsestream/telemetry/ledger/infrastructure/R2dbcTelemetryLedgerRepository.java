package com.pulsestream.telemetry.ledger.infrastructure;

import com.pulsestream.telemetry.ledger.application.port.out.TelemetryLedgerRepository;
import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import java.util.Objects;
import org.springframework.data.r2dbc.core.R2dbcEntityTemplate;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Repository
public class R2dbcTelemetryLedgerRepository implements TelemetryLedgerRepository {

    private final TelemetryRecordR2dbcRepository repository;

    private final R2dbcEntityTemplate template;

    public R2dbcTelemetryLedgerRepository(TelemetryRecordR2dbcRepository repository, R2dbcEntityTemplate template) {
        this.repository = Objects.requireNonNull(repository, "repository must not be null");
        this.template = Objects.requireNonNull(template, "template must not be null");
    }

    public Flux<TelemetryRecord> findHistory(String deviceId, Instant fromInclusive, Instant toExclusive) {
        return repository.findHistory(deviceId, fromInclusive, toExclusive).map(TelemetryRecordEntity::toDomain);
    }

    public Mono<TelemetryRecord> findLatestRevision(String deviceId, String metric, Instant tDevice) {
        return repository.findLatestRevision(deviceId, metric, tDevice).map(TelemetryRecordEntity::toDomain);
    }

    public Flux<TelemetryRecord> findRevisionChain(String deviceId, String metric, Instant tDevice) {
        return repository.findRevisionChain(deviceId, metric, tDevice).map(TelemetryRecordEntity::toDomain);
    }

    public Mono<TelemetryRecord> append(TelemetryRecord record) {
        return template.insert(TelemetryRecordEntity.fromDomain(record)).map(TelemetryRecordEntity::toDomain);
    }
}
