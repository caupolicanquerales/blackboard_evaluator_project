package com.pulsestream.telemetry.ingestion.infrastructure;

import java.time.ZoneOffset;
import java.util.Objects;
import com.pulsestream.telemetry.ingestion.application.AuditEntry;
import com.pulsestream.telemetry.ingestion.application.AuditTrail;
import io.r2dbc.spi.Parameter;
import io.r2dbc.spi.Parameters;
import io.r2dbc.spi.R2dbcType;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.core.publisher.Mono;

public class R2dbcAuditTrail implements AuditTrail {

    private static final String INSERT = "INSERT INTO audit_trail (actor, action, outcome, occurred_at, correlation_id) VALUES (:actor, :action, :outcome, :occurredAt, :correlationId)";

    private final DatabaseClient client;

    public R2dbcAuditTrail(DatabaseClient client) {
        this.client = Objects.requireNonNull(client, "client");
    }

    public Mono<Void> record(AuditEntry entry) {
        return client.sql(INSERT)
                .bind("actor", varchar(entry.actor()))
                .bind("action", varchar(entry.action()))
                .bind("outcome", varchar(entry.outcome()))
                .bind("occurredAt", entry.timestamp().atOffset(ZoneOffset.UTC))
                .bind("correlationId", varchar(entry.correlationId()))
                .then();
    }

    private static Parameter varchar(String value) {
        return Parameters.in(R2dbcType.VARCHAR, value);
    }
}
