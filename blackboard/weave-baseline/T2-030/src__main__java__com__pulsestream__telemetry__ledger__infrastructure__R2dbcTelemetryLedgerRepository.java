package com.pulsestream.telemetry.ledger.infrastructure;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import com.pulsestream.telemetry.ledger.application.port.out.TelemetryLedgerRepository;
import java.time.Instant;
import org.springframework.data.r2dbc.core.R2dbcEntityTemplate;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Repository
public class R2dbcTelemetryLedgerRepository {

    private final TelemetryRecordR2dbcRepository repository;

    private final R2dbcEntityTemplate template;

    public R2dbcTelemetryLedgerRepository(TelemetryRecordR2dbcRepository repository, R2dbcEntityTemplate template) {
        this.repository = repository;
        this.template = template;
    }

    @Override
    public Mono<TelemetryRecord> append(TelemetryRecord record) {
        return template.insert(TelemetryRecordEntity.fromDomain(record)).map(TelemetryRecordEntity::toDomain);
    }

    @Override
    public Flux<TelemetryRecord> findHistory(String deviceId, Instant fromInclusive, Instant toExclusive) {
        return repository.findHistory(deviceId, fromInclusive, toExclusive).map(TelemetryRecordEntity::toDomain);
    }

    @Override
    public Mono<TelemetryRecord> findLatestRevision(String deviceId, String metric, Instant tDevice) {
        return repository.findLatestRevision(deviceId, metric, tDevice).map(TelemetryRecordEntity::toDomain);
    }

    @Override
    public Flux<TelemetryRecord> findRevisionChain(String deviceId, String metric, Instant tDevice) {
        return repository.findRevisionChain(deviceId, metric, tDevice).map(TelemetryRecordEntity::toDomain);
    }

    public void R2dbcTelemetryLedgerRepository(TelemetryRecordR2dbcRepository repository, R2dbcEntityTemplate template) {
        this.repository = repository;
        this.template = template;
    }
}
