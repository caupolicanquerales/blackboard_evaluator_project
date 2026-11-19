package com.pulsestream.telemetry.ingestion.infrastructure;

import reactor.core.publisher.Mono;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.HexFormat;
import io.r2dbc.spi.R2dbcException;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.r2dbc.core.Parameters;
import org.springframework.r2dbc.connection.R2dbcTransactionManager;
import org.springframework.transaction.reactive.TransactionalOperator;
import com.pulsestream.telemetry.ingestion.application.TelemetryRecordRepository;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.ingestion.domain.TelemetryRevision;

public class R2dbcTelemetryRecordRepository implements TelemetryRecordRepository {

    private final DatabaseClient client;

    private final AesGcmPayloadCipher cipher;

    public R2dbcTelemetryRecordRepository(DatabaseClient client, AesGcmPayloadCipher cipher) {
        this.client = client;
        this.cipher = cipher;
    }

    private static String sha256Hex(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("digest unavailable");
        }
    }

    private static OffsetDateTime utc(Instant instant) {
        return OffsetDateTime.ofInstant(instant, ZoneOffset.UTC);
    }

    private static boolean isUniqueViolation(Throwable error) {
        for (Throwable t = error; t != null; t = t.getCause()) {
            if (t instanceof R2dbcException r && "23505".equals(r.getSqlState())) {
                return true;
            }
        }
        return false;
    }

    private Mono<Void> insertRevision(Long recordId, int revisionNumber, double value, String reason) {
        return client.sql("INSERT INTO telemetry_revisions (record_id, revision_number, sample_value, reason, created_at) VALUES (:recordId, :revisionNumber, :value, :reason, :createdAt)").bind("recordId", recordId).bind("revisionNumber", revisionNumber).bind("value", value).bind("reason", reason).bind("createdAt", OffsetDateTime.now(ZoneOffset.UTC)).fetch().rowsUpdated().then();
    }

    @Override
    public Mono<Void> appendRevision(TelemetryRevision revision) {
        return client.sql("SELECT record_id FROM telemetry_records WHERE device_id = :deviceId AND metric = :metric AND t_device = :tDevice ORDER BY record_id DESC LIMIT 1").bind("deviceId", revision.deviceId()).bind("metric", revision.metric()).bind("tDevice", utc(revision.tDevice())).map(row -> row.get(0, Long.class)).one().switchIfEmpty(Mono.error(new IllegalStateException("unknown record identity"))).flatMap(recordId -> insertRevision(recordId, revision.revisionNumber(), revision.value(), revision.reason()));
    }

    @Override
    public Mono<TelemetryRevision> findLatestRevision(String deviceId, String metric, Instant tDevice) {
        return client.sql("SELECT r.revision_number, r.sample_value, r.reason FROM telemetry_revisions r JOIN telemetry_records t ON t.record_id = r.record_id WHERE t.device_id = :deviceId AND t.metric = :metric AND t.t_device = :tDevice ORDER BY r.revision_number DESC LIMIT 1").bind("deviceId", deviceId).bind("metric", metric).bind("tDevice", utc(tDevice)).map(row -> new TelemetryRevision(deviceId, metric, tDevice, row.get(0, Integer.class), row.get(1, Double.class), row.get(2, String.class))).one();
    }

    @Override
    public Mono<Boolean> appendRecord(TelemetrySample sample) {
        String plain = sample.payload();
        String stored = plain == null ? null : cipher.encrypt(plain);
        String hash = sha256Hex(plain == null ? "" : plain);
        TransactionalOperator tx = TransactionalOperator.create(new R2dbcTransactionManager(client.getConnectionFactory()));
        Mono<Boolean> appended = client.sql("INSERT INTO telemetry_records (device_id, metric, t_device, t_ingress, sample_value, validation_status, payload_hash, payload) VALUES (:deviceId, :metric, :tDevice, :tIngress, :value, :status, :hash, :payload)").bind("deviceId", Parameters.in(String.class, sample.deviceId())).bind("metric", sample.metric()).bind("tDevice", utc(sample.tDevice())).bind("tIngress", utc(sample.tIngress())).bind("value", sample.value()).bind("status", sample.status().name()).bind("hash", hash).bind("payload", Parameters.in(String.class, stored)).filter(statement -> statement.returnGeneratedValues("record_id")).map(row -> row.get(0, Long.class)).one().flatMap(recordId -> insertRevision(recordId, 1, sample.value(), "INITIAL")).thenReturn(true);
        return tx.transactional(appended).onErrorResume(RuntimeException.class, error -> isUniqueViolation(error) ? Mono.just(false) : Mono.error(error));
    }
}
