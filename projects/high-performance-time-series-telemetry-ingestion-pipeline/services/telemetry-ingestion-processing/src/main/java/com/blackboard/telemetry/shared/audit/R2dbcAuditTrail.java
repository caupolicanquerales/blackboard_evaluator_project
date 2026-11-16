package com.blackboard.telemetry.shared.audit;

import org.springframework.r2dbc.core.DatabaseClient;
import reactor.core.publisher.Mono;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.Objects;

public class R2dbcAuditTrail implements AuditTrail {

    private static final String INSERT_SQL = "INSERT INTO audit_trail (actor, action, outcome, occurred_at, correlation_id) "
            + "VALUES (:actor, :action, :outcome, :occurredAt, :correlationId)";

    private final DatabaseClient client;

    public R2dbcAuditTrail(DatabaseClient client) {
        this.client = Objects.requireNonNull(client, "client");
    }

    @Override
    public Mono<Void> record(AuditEntry entry) {
        return client.sql(INSERT_SQL)
                .bind("actor", entry.actor())
                .bind("action", entry.action().name())
                .bind("outcome", entry.outcome())
                .bind("occurredAt", LocalDateTime.ofInstant(entry.timestamp(), ZoneOffset.UTC))
                .bind("correlationId", entry.correlationId())
                .then();
    }
}
