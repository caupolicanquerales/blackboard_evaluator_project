package com.pulsestream.telemetry.eventlog.infrastructure;

import com.pulsestream.telemetry.eventlog.application.EventLogRepository;
import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.core.publisher.Mono;

public class R2dbcEventLogRepository implements EventLogRepository {

    private final DatabaseClient databaseClient;

    public R2dbcEventLogRepository(DatabaseClient databaseClient) {
        this.databaseClient = databaseClient;
    }

    @Override
    public Mono<EventRecord> findLatest(String deviceId, String metric, Instant tDevice) {
        return databaseClient.sql("SELECT revision, t_ingress, sample_value, validation_status FROM telemetry_record WHERE device_id = :deviceId AND metric = :metric AND t_device = :tDevice ORDER BY revision DESC LIMIT 1").bind("deviceId", deviceId).bind("metric", metric).bind("tDevice", OffsetDateTime.ofInstant(tDevice, ZoneOffset.UTC)).map(row -> {
            int revision = row.get("revision", Integer.class);
            TelemetrySample stored = new TelemetrySample(deviceId, metric, tDevice, row.get("t_ingress", OffsetDateTime.class).toInstant(), row.get("sample_value", Double.class), row.get("validation_status", String.class), "");
            return new EventRecord(stored, revision, revision == 1 ? EventRecord.KIND_RECORD : EventRecord.KIND_REVISION);
        }).one();
    }

    public Mono<EventRecord> append(TelemetrySample sample) {
        OffsetDateTime tDevice = OffsetDateTime.ofInstant(sample.tDevice(), ZoneOffset.UTC);
        return databaseClient.sql("SELECT COALESCE(MAX(revision), 0) AS max_revision FROM telemetry_record WHERE device_id = :deviceId AND metric = :metric AND t_device = :tDevice").bind("deviceId", sample.deviceId()).bind("metric", sample.metric()).bind("tDevice", tDevice).map(row -> row.get("max_revision", Integer.class)).one().flatMap(max -> databaseClient.sql("INSERT INTO telemetry_record (device_id, metric, t_device, revision, t_ingress, sample_value, validation_status) VALUES (:deviceId, :metric, :tDevice, :revision, :tIngress, :value, :status)").bind("deviceId", sample.deviceId()).bind("metric", sample.metric()).bind("tDevice", tDevice).bind("revision", max + 1).bind("tIngress", OffsetDateTime.ofInstant(sample.tIngress(), ZoneOffset.UTC)).bind("value", sample.value()).bind("status", sample.status()).fetch().rowsUpdated().thenReturn(new EventRecord(sample, max + 1, max == 0 ? EventRecord.KIND_RECORD : EventRecord.KIND_REVISION)));
    }
}
