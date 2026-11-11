package com.pulsestream.telemetry.eventlog.infrastructure;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.eventlog.domain.EventLogRepository;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Repository
public class R2dbcEventLogRepository implements EventLogRepository {

    private final DatabaseClient client;

    public R2dbcEventLogRepository(DatabaseClient client) {
        this.client = client;
    }

    public Mono<Void> appendRevision(TelemetrySample revision) {
        return client.sql("INSERT INTO telemetry_event_log.telemetry_record_revisions (device_id, metric, t_device, value, reason, t_revised) VALUES (:deviceId, :metric, :tDevice, :value, :reason, :tRevised)").bind("deviceId", revision.deviceId()).bind("metric", revision.metric()).bind("tDevice", toOffset(revision.tDeviceEpochMs())).bind("value", revision.value()).bind("reason", "LATE_ARRIVAL").bind("tRevised", toOffset(revision.tIngressEpochMs())).fetch().rowsUpdated().then();
    }

    public Flux<TelemetrySample> findByDeviceAndRange(String deviceId, long fromEpochMs, long toEpochMs) {
        return client.sql("SELECT device_id, metric, t_device, value, validation_status, t_ingress FROM telemetry_event_log.telemetry_records WHERE device_id = :deviceId AND t_device >= :from AND t_device <= :to ORDER BY t_device ASC").bind("deviceId", deviceId).bind("from", toOffset(fromEpochMs)).bind("to", toOffset(toEpochMs)).map(row -> new TelemetrySample(row.get("device_id", String.class), row.get("metric", String.class), row.get("t_device", OffsetDateTime.class).toInstant().toEpochMilli(), row.get("value", Double.class), row.get("t_ingress", OffsetDateTime.class).toInstant().toEpochMilli(), fromDbStatus(row.get("validation_status", String.class)))).all();
    }

    private static OffsetDateTime toOffset(long epochMs) {
        return OffsetDateTime.ofInstant(Instant.ofEpochMilli(epochMs), ZoneOffset.UTC);
    }

    private static String toDbStatus(String status) {
        return TelemetrySample.VALIDATION_FAILED.equals(status) ? "INVALID" : status;
    }

    private static String fromDbStatus(String status) {
        return "INVALID".equals(status) ? TelemetrySample.VALIDATION_FAILED : status;
    }

    public Mono<Boolean> appendRecord(TelemetrySample sample) {
        return client.sql("INSERT INTO telemetry_event_log.telemetry_records (device_id, metric, t_device, value, validation_status, t_ingress) VALUES (:deviceId, :metric, :tDevice, :value, :status, :tIngress) ON CONFLICT (device_id, metric, t_device) DO NOTHING").bind("deviceId", sample.deviceId()).bind("metric", sample.metric()).bind("tDevice", toOffset(sample.tDeviceEpochMs())).bind("value", sample.value()).bind("status", toDbStatus(sample.validationStatus())).bind("tIngress", toOffset(sample.tIngressEpochMs())).fetch().rowsUpdated().map(updated -> updated > 0);
    }
}
