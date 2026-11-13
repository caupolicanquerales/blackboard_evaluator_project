package com.blackboard.telemetry.eventstore.infrastructure;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;
import com.blackboard.telemetry.eventstore.application.TelemetryEventStore;
import com.blackboard.telemetry.eventstore.domain.TelemetryRecord;

@Repository
public class R2dbcTelemetryEventStore implements TelemetryEventStore {

    private final DatabaseClient databaseClient;

    public R2dbcTelemetryEventStore(DatabaseClient databaseClient) {
        this.databaseClient = databaseClient;
    }

    @Override
    public Mono<TelemetryRecord> append(TelemetryRecord record) {
        return databaseClient.sql("INSERT INTO telemetry_records (device_id, metric, t_device, revision, \"value\", validation_status, t_ingress) VALUES (:deviceId, :metric, :tDevice, :revision, :value, :status, :tIngress)").bind("deviceId", record.deviceId()).bind("metric", record.metric()).bind("tDevice", record.tDevice().atOffset(ZoneOffset.UTC)).bind("revision", (int) record.revision()).bind("value", record.value()).bind("status", record.status()).bind("tIngress", record.tIngress().atOffset(ZoneOffset.UTC)).fetch().rowsUpdated().thenReturn(record);
    }

    @Override
    public Flux<TelemetryRecord> findLatestInRange(String deviceId, String metric, Instant from, Instant to) {
        String sql = "SELECT r.device_id, r.metric, r.t_device, r.t_ingress, r.\"value\", r.validation_status, r.revision " + "FROM telemetry_records r " + "WHERE r.device_id = :deviceId AND r.metric = :metric AND r.t_device >= :from AND r.t_device <= :to " + "AND r.revision = (SELECT MAX(m.revision) FROM telemetry_records m " + "WHERE m.device_id = r.device_id AND m.metric = r.metric AND m.t_device = r.t_device) " + "ORDER BY r.t_device ASC";
        return databaseClient.sql(sql).bind("deviceId", deviceId).bind("metric", metric).bind("from", from.atOffset(ZoneOffset.UTC)).bind("to", to.atOffset(ZoneOffset.UTC)).map((row, metadata) -> new TelemetryRecord(row.get("device_id", String.class), row.get("metric", String.class), row.get("t_device", OffsetDateTime.class).toInstant(), row.get("t_ingress", OffsetDateTime.class).toInstant(), row.get("value", Double.class), row.get("validation_status", String.class), row.get("revision", Integer.class))).all();
    }
}
