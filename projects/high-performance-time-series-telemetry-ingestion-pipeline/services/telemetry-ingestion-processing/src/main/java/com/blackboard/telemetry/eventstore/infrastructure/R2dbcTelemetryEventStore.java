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
import java.time.ZonedDateTime;
import java.time.LocalDateTime;

@Repository
public class R2dbcTelemetryEventStore implements TelemetryEventStore {

    private static final String INSERT_SQL =
            "INSERT INTO telemetry_records (device_id, metric, t_device, revision, \"value\", validation_status, t_ingress) "
            + "VALUES (:pDeviceId, :pMetric, :pTDevice, :pRevision, :pValue, :pStatus, :pTIngress)";

    private static final String LATEST_IN_RANGE_SQL =
            "SELECT r.device_id, r.metric, r.t_device, r.t_ingress, r.\"value\", r.validation_status, r.revision "
            + "FROM telemetry_records r "
            + "WHERE r.device_id = :pDeviceId AND r.metric = :pMetric AND r.t_device >= :pFrom AND r.t_device <= :pTo "
            + "AND r.revision = (SELECT MAX(m.revision) FROM telemetry_records m "
            + "WHERE m.device_id = r.device_id AND m.metric = r.metric AND m.t_device = r.t_device) "
            + "ORDER BY r.t_device ASC";

    private final DatabaseClient databaseClient;

    public R2dbcTelemetryEventStore(DatabaseClient databaseClient) {
        this.databaseClient = databaseClient;
    }

    @Override
    public Mono<TelemetryRecord> append(TelemetryRecord record) {
        return databaseClient.sql(INSERT_SQL)
                .bind("pDeviceId", record.deviceId())
                .bind("pMetric", record.metric())
                .bind("pTDevice", record.tDevice().atOffset(ZoneOffset.UTC))
                .bind("pRevision", (int) record.revision())
                .bind("pValue", record.value())
                .bind("pStatus", record.status())
                .bind("pTIngress", record.tIngress().atOffset(ZoneOffset.UTC))
                .fetch()
                .rowsUpdated()
                .thenReturn(record);
    }

    @Override
    public Flux<TelemetryRecord> findLatestInRange(String deviceId, String metric, Instant from, Instant to) {
        return databaseClient.sql(LATEST_IN_RANGE_SQL)
                .bind("pDeviceId", deviceId)
                .bind("pMetric", metric)
                .bind("pFrom", from.atOffset(ZoneOffset.UTC))
                .bind("pTo", to.atOffset(ZoneOffset.UTC))
                .map((row, metadata) -> new TelemetryRecord(
                        row.get("device_id", String.class),
                        row.get("metric", String.class),
                        toInstant(row.get("t_device")),
                        toInstant(row.get("t_ingress")),
                        ((Number) row.get("value")).doubleValue(),
                        row.get("validation_status", String.class),
                        ((Number) row.get("revision")).longValue()))
                .all();
    }

    private static Instant toInstant(Object raw) {
        if (raw instanceof OffsetDateTime odt) {
            return odt.toInstant();
        }
        if (raw instanceof ZonedDateTime zdt) {
            return zdt.toInstant();
        }
        if (raw instanceof LocalDateTime ldt) {
            return ldt.toInstant(ZoneOffset.UTC);
        }
        return (Instant) raw;
    }
}
