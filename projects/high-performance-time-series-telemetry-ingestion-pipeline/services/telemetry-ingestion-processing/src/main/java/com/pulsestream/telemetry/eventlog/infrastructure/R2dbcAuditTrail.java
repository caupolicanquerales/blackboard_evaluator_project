package com.pulsestream.telemetry.eventlog.infrastructure;

import com.pulsestream.telemetry.shared.observability.AuditEntry;
import com.pulsestream.telemetry.shared.observability.AuditTrail;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.core.publisher.Mono;

public class R2dbcAuditTrail implements AuditTrail {

    private static final String INSERT_SQL = "INSERT INTO audit_trail "
            + "(actor, action, outcome, occurred_at, correlation_id) "
            + "VALUES (:actor, :action, :outcome, :occurredAt, :correlationId)";

    private static final String DROPPED_COUNTER = "telemetry.pipeline.dropped";

    private static final String AUDIT_STAGE = "audit";

    private final DatabaseClient databaseClient;

    private final MeterRegistry meterRegistry;

    public R2dbcAuditTrail(DatabaseClient databaseClient, MeterRegistry meterRegistry) {
        this.databaseClient = databaseClient;
        this.meterRegistry = meterRegistry;
    }

    @Override
    public Mono<Void> record(AuditEntry entry) {
        return Mono.defer(() -> insert(entry))
                .onErrorResume(error -> {
                    meterRegistry.counter(DROPPED_COUNTER, "stage", AUDIT_STAGE).increment();
                    return Mono.empty();
                });
    }

    private Mono<Void> insert(AuditEntry entry) {
        return databaseClient.sql(INSERT_SQL)
                .bind("actor", entry.actor())
                .bind("action", entry.action())
                .bind("outcome", entry.outcome())
                .bind("occurredAt", OffsetDateTime.ofInstant(entry.timestamp(), ZoneOffset.UTC))
                .bind("correlationId", entry.correlationId())
                .fetch()
                .rowsUpdated()
                .then();
    }
}
