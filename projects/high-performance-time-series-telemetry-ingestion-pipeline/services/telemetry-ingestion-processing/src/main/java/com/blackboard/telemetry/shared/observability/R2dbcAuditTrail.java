package com.blackboard.telemetry.shared.observability;

import java.time.ZoneOffset;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Mono;

@Repository
public class R2dbcAuditTrail implements AuditTrail {

    private static final String INSERT_SQL = "INSERT INTO audit_trail "
            + "(actor, action, outcome, occurred_at, correlation_id) "
            + "VALUES (:actor, :action, :outcome, :occurredAt, :correlationId)";

    private final DatabaseClient databaseClient;

    public R2dbcAuditTrail(DatabaseClient databaseClient) {
        this.databaseClient = databaseClient;
    }

    @Override
    public Mono<Void> record(AuditEntry entry) {
        return databaseClient.sql(INSERT_SQL)
                .bind("actor", entry.actor())
                .bind("action", entry.action())
                .bind("outcome", entry.outcome())
                .bind("occurredAt", entry.timestamp().atOffset(ZoneOffset.UTC))
                .bind("correlationId", entry.correlationId())
                .fetch()
                .rowsUpdated()
                .then();
    }
}
