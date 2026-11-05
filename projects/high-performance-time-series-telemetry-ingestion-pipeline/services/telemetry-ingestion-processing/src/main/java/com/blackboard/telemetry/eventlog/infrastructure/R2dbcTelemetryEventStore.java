package com.blackboard.telemetry.eventlog.infrastructure;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Objects;
import io.r2dbc.spi.Row;
import org.springframework.r2dbc.core.DatabaseClient;
import com.blackboard.telemetry.eventlog.domain.EventRevision;
import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public class R2dbcTelemetryEventStore {

    private static final String COLUMNS = "device_id, t_device, revision, t_ingress, validation_status, payload #>> '{}' AS payload";

    private static final String INSERT_SQL = "INSERT INTO telemetry_events (event_id, device_id, t_device, revision, t_ingress, validation_status, payload, original_event_id) " + "SELECT gen_random_uuid(), CAST(:deviceId AS text), CAST(:tDevice AS timestamptz), CAST(:revision AS integer), " + "CAST(:tIngress AS timestamptz), CAST(:status AS text), to_jsonb(CAST(:payload AS text)), " + "(SELECT e.event_id FROM telemetry_events e WHERE e.device_id = :deviceId AND e.t_device = :tDevice AND e.revision = 0)";

    private static final String HISTORY_SQL = "SELECT " + COLUMNS + " FROM telemetry_events WHERE device_id = :deviceId AND t_device = :tDevice ORDER BY revision ASC";

    private static final String RANGE_SQL = "SELECT " + COLUMNS + " FROM telemetry_events WHERE device_id = :deviceId AND t_device >= :from AND t_device <= :to ORDER BY t_device ASC, revision ASC";

    private final DatabaseClient client;

    public R2dbcTelemetryEventStore(DatabaseClient client) {
        this.client = Objects.requireNonNull(client, "client must not be null");
    }

    public Flux<EventRevision> history(String deviceId, Instant tDevice) {
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(tDevice, "tDevice must not be null");
        return client.sql(HISTORY_SQL).bind("deviceId", deviceId).bind("tDevice", tDevice.atOffset(ZoneOffset.UTC)).map((row, metadata) -> toRevision(row)).all();
    }

    public Flux<EventRevision> range(String deviceId, Instant from, Instant to) {
        Objects.requireNonNull(deviceId, "deviceId must not be null");
        Objects.requireNonNull(from, "from must not be null");
        Objects.requireNonNull(to, "to must not be null");
        return client.sql(RANGE_SQL).bind("deviceId", deviceId).bind("from", from.atOffset(ZoneOffset.UTC)).bind("to", to.atOffset(ZoneOffset.UTC)).map((row, metadata) -> toRevision(row)).all();
    }

    private static String toDbStatus(ValidationStatus status) {
        return status == ValidationStatus.VALID ? "VALID" : "INVALID";
    }

    private static EventRevision toRevision(Row row) {
        ValidationStatus status = "VALID".equals(row.get("validation_status", String.class)) ? ValidationStatus.VALID : ValidationStatus.VALIDATION_FAILED;
        Instant tIngress = row.get("t_ingress", OffsetDateTime.class).toInstant();
        String payload = row.get("payload", String.class);
        EventRevision revision = EventRevision.first(row.get("device_id", String.class), row.get("t_device", OffsetDateTime.class).toInstant(), tIngress, status, payload);
        int target = row.get("revision", Integer.class);
        for (int i = 0; i < target; i++) {
            revision = revision.nextRevision(tIngress, status, payload);
        }
        return revision;
    }

    public Mono<EventRevision> append(EventRevision record) {
        Objects.requireNonNull(record, "record must not be null");
        return client.sql(INSERT_SQL).bind("deviceId", record.deviceId()).bind("tDevice", record.tDevice().atOffset(ZoneOffset.UTC)).bind("revision", record.revision()).bind("tIngress", record.tIngress().atOffset(ZoneOffset.UTC)).bind("status", toDbStatus(record.validationStatus())).bind("payload", record.payload()).fetch().rowsUpdated().thenReturn(record);
    }
}
