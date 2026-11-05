package com.blackboard.telemetry.eventlog.infrastructure;
import com.blackboard.telemetry.shared.events.TelemetryEvents;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.time.ZoneOffset;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.r2dbc.core.DatabaseClient;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import com.blackboard.telemetry.eventlog.domain.EventRevision;
import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;

import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import io.r2dbc.spi.ConnectionFactoryOptions;
import reactor.test.StepVerifier;

@Testcontainers
class R2dbcTelemetryEventStoreTest {

    private static final Instant T_DEVICE = Instant.parse("2026-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2026-01-01T10:00:05Z");
    private static final String MIGRATIONS = "filesystem:db/migrations/telemetry-ingestion-processing";

    @Container
    private static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
            DockerImageName.parse("timescale/timescaledb:latest-pg16").asCompatibleSubstituteFor("postgres"));

    private static DatabaseClient client;
    private static R2dbcTelemetryEventStore store;

    @BeforeAll
    static void migrateAndConnect() {
        Flyway.configure()
                .dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword())
                .locations(MIGRATIONS)
                .load()
                .migrate();
        ConnectionFactory factory = ConnectionFactories.get(ConnectionFactoryOptions.builder()
                .option(ConnectionFactoryOptions.DRIVER, "postgresql")
                .option(ConnectionFactoryOptions.HOST, POSTGRES.getHost())
                .option(ConnectionFactoryOptions.PORT, POSTGRES.getMappedPort(PostgreSQLContainer.POSTGRESQL_PORT))
                .option(ConnectionFactoryOptions.USER, POSTGRES.getUsername())
                .option(ConnectionFactoryOptions.PASSWORD, POSTGRES.getPassword())
                .option(ConnectionFactoryOptions.DATABASE, POSTGRES.getDatabaseName())
                .build());
        client = DatabaseClient.create(factory);
        store = new R2dbcTelemetryEventStore(client);
    }

    private static EventRevision first(String device, Instant tDevice) {
        return EventRevision.first(device, tDevice, T_INGRESS, ValidationStatus.VALID, "heart_rate=150.0");
    }

    private static long rowCount(String device, Instant tDevice) {
        return client.sql("SELECT count(*) AS c FROM telemetry_events WHERE device_id = :d AND t_device = :t")
                .bind("d", device)
                .bind("t", tDevice.atOffset(ZoneOffset.UTC))
                .map(row -> row.get("c", Long.class))
                .one()
                .block();
    }

    @Test
    void append_newRevision_insertsRowAndReturnsIt() {
        EventRevision record = first("append-device", T_DEVICE);

        StepVerifier.create(store.append(record)).expectNext(record).verifyComplete();

        assertThat(rowCount("append-device", T_DEVICE)).isEqualTo(1);
    }

    @Test
    void append_duplicateKey_isRejected() {
        EventRevision record = first("dup-device", T_DEVICE);
        store.append(record).block();

        StepVerifier.create(store.append(record)).expectError().verify();
    }

    @Test
    void append_duplicateKeyWithDifferentPayload_neverOverwritesExistingRow() {
        EventRevision record = first("overwrite-device", T_DEVICE);
        store.append(record).block();
        EventRevision clash = EventRevision.first("overwrite-device", T_DEVICE, T_INGRESS.plusSeconds(60),
                ValidationStatus.VALID, "heart_rate=999.0");

        StepVerifier.create(store.append(clash)).expectError().verify();

        StepVerifier.create(store.history("overwrite-device", T_DEVICE)).expectNext(record).verifyComplete();
    }

    @Test
    void append_correction_addsNextRevisionAndLeavesEarlierRowUnchanged() {
        EventRevision original = first("correction-device", T_DEVICE);
        store.append(original).block();
        EventRevision correction = original.correctedBy(T_INGRESS.plusSeconds(60), ValidationStatus.VALID,
                "heart_rate=151.0");

        StepVerifier.create(store.append(correction)).expectNext(correction).verifyComplete();

        StepVerifier.create(store.history("correction-device", T_DEVICE))
                .expectNext(original, correction)
                .verifyComplete();
    }

    @Test
    void history_unorderedInserts_returnsOrderedByRevision() {
        EventRevision r0 = first("history-device", T_DEVICE);
        EventRevision r1 = r0.correctedBy(T_INGRESS.plusSeconds(10), ValidationStatus.VALID, "heart_rate=151.0");
        EventRevision r2 = r1.correctedBy(T_INGRESS.plusSeconds(20), ValidationStatus.VALID, "heart_rate=152.0");
        store.append(r0).block();
        store.append(r2).block();
        store.append(r1).block();

        StepVerifier.create(store.history("history-device", T_DEVICE).map(EventRevision::revision))
                .expectNext(0L, 1L, 2L)
                .verifyComplete();
    }

    @Test
    void history_otherDeviceOrTDevice_returnsOnlyMatchingKey() {
        store.append(first("scoped-device", T_DEVICE)).block();
        store.append(first("scoped-device", T_DEVICE.plusSeconds(1))).block();
        store.append(first("scoped-other", T_DEVICE)).block();

        StepVerifier.create(store.history("scoped-device", T_DEVICE).map(EventRevision::deviceId))
                .expectNext("scoped-device")
                .verifyComplete();
    }

    @Test
    void history_unknownKey_isEmpty() {
        StepVerifier.create(store.history("missing-device", T_DEVICE)).verifyComplete();
    }

    @Test
    void range_boundsGiven_returnsRowsOrderedByTDevice() {
        store.append(first("range-device", T_DEVICE.plusSeconds(30))).block();
        store.append(first("range-device", T_DEVICE)).block();
        store.append(first("range-device", T_DEVICE.plusSeconds(10))).block();

        StepVerifier.create(store.range("range-device", T_DEVICE, T_DEVICE.plusSeconds(30)).map(EventRevision::tDevice))
                .expectNext(T_DEVICE, T_DEVICE.plusSeconds(10), T_DEVICE.plusSeconds(30))
                .verifyComplete();
    }

    @Test
    void range_rowsOutsideBounds_areExcluded() {
        store.append(first("bounds-device", T_DEVICE.minusSeconds(10))).block();
        store.append(first("bounds-device", T_DEVICE)).block();
        store.append(first("bounds-device", T_DEVICE.plusSeconds(100))).block();

        StepVerifier.create(store.range("bounds-device", T_DEVICE, T_DEVICE.plusSeconds(50)).map(EventRevision::tDevice))
                .expectNext(T_DEVICE)
                .verifyComplete();
    }

    @Test
    void range_otherDevice_isExcluded() {
        store.append(first("range-a", T_DEVICE)).block();
        store.append(first("range-b", T_DEVICE)).block();

        StepVerifier.create(store.range("range-a", T_DEVICE, T_DEVICE.plusSeconds(10)).map(EventRevision::deviceId))
                .expectNext("range-a")
                .verifyComplete();
    }

    @Test
    void append_payloadAndValidationFailedStatus_roundTrip() {
        EventRevision failed = EventRevision.first("failed-device", T_DEVICE, T_INGRESS,
                ValidationStatus.VALIDATION_FAILED, "heart_rate=400.0");
        store.append(failed).block();

        StepVerifier.create(store.history("failed-device", T_DEVICE))
                .assertNext(read -> {
                    assertThat(read.validationStatus()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
                    assertThat(read.payload()).isEqualTo("heart_rate=400.0");
                    assertThat(read.tIngress()).isEqualTo(T_INGRESS);
                })
                .verifyComplete();
    }
}
