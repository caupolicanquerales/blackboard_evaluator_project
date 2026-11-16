package com.blackboard.telemetry.history.infrastructure;

import com.blackboard.telemetry.history.application.TelemetryHistoryRepository;
import com.blackboard.telemetry.history.domain.RevisionReason;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.Optional;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public class R2dbcTelemetryHistoryRepository implements TelemetryHistoryRepository {

    private static final String NEXT_REVISION_SQL =
            "SELECT COALESCE(MAX(revision_no), 0) + 1 AS next_no FROM event_revision WHERE sample_id = :sampleId";
    private static final String INSERT_REVISION_SQL =
            "INSERT INTO event_revision (sample_id, reason, value, t_ingress, revision_no) "
                    + "VALUES (:sampleId, :reason, :value, :tIngress, :revisionNo)";
    private static final String LATEST_T_DEVICE_SQL =
            "SELECT MAX(t_device) AS latest FROM telemetry_sample WHERE device_id = :deviceId AND metric = :metric";
    private static final String FIND_WINDOW_SQL =
            "SELECT device_id, metric, t_device, t_ingress, value, validation_status FROM telemetry_sample "
                    + "WHERE device_id = :deviceId AND metric = :metric AND t_device >= :from AND t_device <= :to "
                    + "ORDER BY t_device ASC LIMIT :limit";
    private static final String INSERT_SAMPLE_SQL =
            "INSERT INTO telemetry_sample (device_id, metric, t_device, t_ingress, value, validation_status) "
                    + "VALUES (:deviceId, :metric, :tDevice, :tIngress, :value, :status)";

    private final DatabaseClient client;

    public R2dbcTelemetryHistoryRepository(DatabaseClient client) {
        this.client = client;
    }

    public Mono<Integer> appendRevision(long sampleId, RevisionReason reason, double value, Instant tIngress) {
        return client.sql(NEXT_REVISION_SQL)
                .bind("sampleId", sampleId)
                .map((row, metadata) -> row.get("next_no", Integer.class))
                .one()
                .flatMap(revisionNo -> client.sql(INSERT_REVISION_SQL)
                        .bind("sampleId", sampleId)
                        .bind("reason", reason.name())
                        .bind("value", value)
                        .bind("tIngress", toUtc(tIngress))
                        .bind("revisionNo", revisionNo)
                        .fetch()
                        .rowsUpdated()
                        .thenReturn(revisionNo));
    }

    public Mono<Instant> findLatestTDevice(String deviceId, MetricKind metric) {
        return client.sql(LATEST_T_DEVICE_SQL)
                .bind("deviceId", deviceId)
                .bind("metric", metric.name())
                .map((row, metadata) -> Optional.ofNullable(row.get("latest", LocalDateTime.class)))
                .one()
                .flatMap(latest -> Mono.justOrEmpty(latest).map(R2dbcTelemetryHistoryRepository::fromUtc));
    }

    public Flux<TelemetrySample> findWindow(String deviceId, MetricKind metric, Instant from, Instant to, int limit) {
        return client.sql(FIND_WINDOW_SQL)
                .bind("deviceId", deviceId)
                .bind("metric", metric.name())
                .bind("from", toUtc(from))
                .bind("to", toUtc(to))
                .bind("limit", limit)
                .map((row, metadata) -> new TelemetrySample(
                        row.get("device_id", String.class),
                        MetricKind.valueOf(row.get("metric", String.class)),
                        fromUtc(row.get("t_device", LocalDateTime.class)),
                        fromUtc(row.get("t_ingress", LocalDateTime.class)),
                        row.get("value", Double.class),
                        ValidationStatus.valueOf(row.get("validation_status", String.class))))
                .all();
    }

    public Mono<Long> appendSample(TelemetrySample sample) {
        return client.sql(INSERT_SAMPLE_SQL)
                .bind("deviceId", sample.deviceId())
                .bind("metric", sample.metric().name())
                .bind("tDevice", toUtc(sample.tDevice()))
                .bind("tIngress", toUtc(sample.tIngress()))
                .bind("value", sample.value())
                .bind("status", sample.status().name())
                .filter(statement -> statement.returnGeneratedValues("id"))
                .map((row, metadata) -> row.get("id", Long.class))
                .one()
                .onErrorResume(DataIntegrityViolationException.class, ex -> Mono.empty());
    }

    private static LocalDateTime toUtc(Instant instant) {
        return LocalDateTime.ofInstant(instant, ZoneOffset.UTC);
    }

    private static Instant fromUtc(LocalDateTime dateTime) {
        return dateTime.toInstant(ZoneOffset.UTC);
    }
}
