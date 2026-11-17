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
        return databaseClient.sql("SELECT revision, t_ingress, sample_value, validation_status FROM telemetry_record WHERE device_id = :deviceId AND metric = :metric AND t_device = :deviceTime ORDER BY revision DESC LIMIT 1").bind("deviceId", deviceId).bind("metric", metric).bind("deviceTime", OffsetDateTime.ofInstant(tDevice, ZoneOffset.UTC)).map(row -> {
            int revision = row.get("revision", Number.class).intValue();
            TelemetrySample stored = new TelemetrySample(deviceId, metric, tDevice, row.get("t_ingress", OffsetDateTime.class).toInstant(), row.get("sample_value", Number.class).doubleValue(), row.get("validation_status", String.class), "");
            return new EventRecord(stored, revision, revision == 1 ? EventRecord.KIND_RECORD : EventRecord.KIND_REVISION);
        }).one();
    }

    public Mono<EventRecord> append(TelemetrySample sample) {
        OffsetDateTime deviceTime = OffsetDateTime.ofInstant(sample.tDevice(), ZoneOffset.UTC);
        OffsetDateTime ingressTime = OffsetDateTime.ofInstant(sample.tIngress(), ZoneOffset.UTC);
        return databaseClient.sql("SELECT COALESCE(MAX(revision), 0) AS max_revision FROM telemetry_record WHERE device_id = :deviceId AND metric = :metric AND t_device = :deviceTime").bind("deviceId", sample.deviceId()).bind("metric", sample.metric()).bind("deviceTime", deviceTime).map(row -> row.get("max_revision", Number.class).intValue()).one().defaultIfEmpty(0).flatMap(maxRevision -> {
            int revision = maxRevision + 1;
            String kind = revision == 1 ? EventRecord.KIND_RECORD : EventRecord.KIND_REVISION;
            return databaseClient.sql("INSERT INTO telemetry_record (device_id, metric, t_device, revision, t_ingress, sample_value, validation_status) VALUES (:deviceId, :metric, :deviceTime, :revision, :ingressTime, :sampleValue, :validationStatus)").bind("deviceId", sample.deviceId()).bind("metric", sample.metric()).bind("deviceTime", deviceTime).bind("revision", revision).bind("ingressTime", ingressTime).bind("sampleValue", sample.value()).bind("validationStatus", sample.status()).fetch().rowsUpdated().thenReturn(new EventRecord(sample, revision, kind));
        });
    }
}
