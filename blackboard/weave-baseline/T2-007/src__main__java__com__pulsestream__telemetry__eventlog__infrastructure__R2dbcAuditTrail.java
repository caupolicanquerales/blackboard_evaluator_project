package com.pulsestream.telemetry.eventlog.infrastructure;

import com.pulsestream.telemetry.shared.observability.AuditEntry;
import com.pulsestream.telemetry.shared.observability.AuditTrail;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.core.publisher.Mono;

public class R2dbcAuditTrail implements AuditTrail {

    private final DatabaseClient databaseClient;

    private final MeterRegistry meterRegistry;

    public R2dbcAuditTrail(DatabaseClient databaseClient, MeterRegistry meterRegistry) {
        this.databaseClient = databaseClient;
        this.meterRegistry = meterRegistry;
    }

    public Mono<Void> record(AuditEntry entry) {
        return databaseClient.sql("INSERT INTO audit_trail (actor, action, outcome, occurred_at, correlation_id) VALUES (:actor, :action, :outcome, :occurredAt, :correlationId)").bind("actor", entry.actor()).bind("action", entry.action()).bind("outcome", entry.outcome()).bind("occurredAt", OffsetDateTime.ofInstant(entry.timestamp(), ZoneOffset.UTC)).bind("correlationId", entry.correlationId()).fetch().rowsUpdated().then().onErrorResume(error -> {
            meterRegistry.counter("telemetry.pipeline.dropped", "stage", "audit").increment();
            return Mono.empty();
        });
    }
}
