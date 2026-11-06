package com.pulsestream.telemetry.ledger.infrastructure;

import com.pulsestream.telemetry.ledger.domain.EventRevision;
import io.r2dbc.spi.Row;
import java.time.Instant;
import java.util.Objects;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Repository
public class R2dbcEventRevisionRepository {

    private final DatabaseClient client;

    public R2dbcEventRevisionRepository(DatabaseClient client) {
        this.client = Objects.requireNonNull(client, "client");
    }

    public Flux<EventRevision> history(String deviceId, String metric, Instant from, Instant to) {
        return client.sql("SELECT device_id, metric, t_device, revision, t_ingress, validation_status, raw_payload FROM telemetry.event_revisions WHERE device_id = :deviceId AND metric = :metric AND t_device >= :from AND t_device <= :to ORDER BY t_device, revision").bind("deviceId", deviceId).bind("metric", metric).bind("from", from).bind("to", to).map((row, metadata) -> toRevision(row)).all();
    }

    public Mono<EventRevision> latest(String deviceId, String metric, Instant tDevice) {
        return client.sql("SELECT device_id, metric, t_device, revision, t_ingress, validation_status, raw_payload FROM telemetry.event_revisions WHERE device_id = :deviceId AND metric = :metric AND t_device = :tDevice ORDER BY revision DESC LIMIT 1").bind("deviceId", deviceId).bind("metric", metric).bind("tDevice", tDevice).map((row, metadata) -> toRevision(row)).first();
    }

    private static EventRevision toRevision(Row row) {
        return new EventRevision(row.get("device_id", String.class), row.get("metric", String.class), row.get("t_device", Instant.class), row.get("revision", Long.class), row.get("t_ingress", Instant.class), row.get("validation_status", String.class), row.get("raw_payload", String.class));
    }

    public Mono<Long> append(EventRevision revision) {
        Objects.requireNonNull(revision, "revision");
        return client.sql("INSERT INTO telemetry.event_revisions (device_id, metric, t_device, revision, t_ingress, validation_status, raw_payload) VALUES (:deviceId, :metric, :tDevice, :revision, :tIngress, :validationStatus, :rawPayload)").bind("deviceId", revision.deviceId()).bind("metric", revision.metric()).bind("tDevice", revision.tDevice()).bind("revision", revision.revision()).bind("tIngress", revision.tIngress()).bind("validationStatus", revision.validationStatus()).bind("rawPayload", revision.rawPayload()).fetch().rowsUpdated();
    }
}
