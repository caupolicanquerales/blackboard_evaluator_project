package com.pulsestream.telemetry.ingestion.infrastructure;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;

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
import org.springframework.r2dbc.connection.R2dbcTransactionManager;
import org.springframework.transaction.reactive.TransactionalOperator;
import com.pulsestream.telemetry.ingestion.application.TelemetryRecordRepository;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.ingestion.domain.TelemetryRevision;

public class R2dbcTelemetryRecordRepository implements TelemetryRecordRepository {

    private static final String UNIQUE_VIOLATION_SQL_STATE = "23505";
    private static final int INITIAL_REVISION_NUMBER = 1;
    private static final String INITIAL_REVISION_REASON = "INITIAL";
    private static final String INSERT_RECORD_SQL = "INSERT INTO telemetry_records (device_id, metric, t_device, t_ingress, sample_value, validation_status, payload_hash, payload) VALUES (:deviceId, :metric, :tDevice, :tIngress, :value, :status, :hash, :payload)";

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
            if (t instanceof R2dbcException r && UNIQUE_VIOLATION_SQL_STATE.equals(r.getSqlState())) {
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
        String plainPayload = sample.payload();
        String encryptedPayload = plainPayload == null ? null : cipher.encrypt(plainPayload);
        String payloadHash = sha256Hex(plainPayload == null ? "" : plainPayload);
        TransactionalOperator transaction = TransactionalOperator.create(new R2dbcTransactionManager(client.getConnectionFactory()));
        DatabaseClient.GenericExecuteSpec insert = client.sql(INSERT_RECORD_SQL).bind("deviceId", sample.deviceId()).bind("metric", sample.metric()).bind("tDevice", utc(sample.tDevice())).bind("tIngress", utc(sample.tIngress())).bind("value", sample.value()).bind("status", (sample.status() == com.pulsestream.telemetry.ingestion.domain.ValidationStatus.LATE ? com.pulsestream.telemetry.ingestion.domain.ValidationStatus.VALIDATED : sample.status()).name()).bind("hash", payloadHash);
        DatabaseClient.GenericExecuteSpec withPayload = encryptedPayload == null ? insert.bindNull("payload", String.class) : insert.bind("payload", encryptedPayload);
        Mono<Boolean> appended = withPayload.filter(statement -> statement.returnGeneratedValues("record_id")).map(row -> row.get(0, Long.class)).one().flatMap(recordId -> insertRevision(recordId, INITIAL_REVISION_NUMBER, sample.value(), INITIAL_REVISION_REASON)).thenReturn(true);
        return transaction.transactional(appended).onErrorResume(RuntimeException.class, error -> isUniqueViolation(error) ? Mono.just(false) : Mono.error(error));
    }
}
