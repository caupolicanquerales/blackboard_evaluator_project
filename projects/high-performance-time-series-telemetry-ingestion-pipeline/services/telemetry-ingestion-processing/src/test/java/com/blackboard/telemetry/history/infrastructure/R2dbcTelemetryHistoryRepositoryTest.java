package com.blackboard.telemetry.history.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.blackboard.telemetry.history.domain.RevisionReason;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.test.StepVerifier;

class R2dbcTelemetryHistoryRepositoryTest {

    private static final Instant T0 = Instant.parse("2026-01-01T10:00:00Z");
    private static final Instant INGRESS = Instant.parse("2026-01-01T10:05:00Z");

    private DatabaseClient client;
    private R2dbcTelemetryHistoryRepository repository;

    @BeforeEach
    void setUp() throws IOException {
        ConnectionFactory factory = ConnectionFactories.get(
                "r2dbc:h2:mem:///" + UUID.randomUUID() + ";DB_CLOSE_DELAY=-1;NON_KEYWORDS=VALUE");
        client = DatabaseClient.create(factory);
        runMigration("db/migrations/V1__create_telemetry_history.sql");
        runMigration("db/migrations/V2__create_event_revision_and_audit_trail.sql");
        repository = new R2dbcTelemetryHistoryRepository(client);
    }

    private void runMigration(String file) throws IOException {
        for (String statement : Files.readString(Path.of(file)).split(";")) {
            if (!statement.isBlank()) {
                client.sql(statement).fetch().rowsUpdated().block();
            }
        }
    }

    private static TelemetrySample sample(String device, MetricKind metric, Instant tDevice, double value,
            ValidationStatus status) {
        return new TelemetrySample(device, metric, tDevice, INGRESS, value, status);
    }

    private long count(String table) {
        return client.sql("SELECT COUNT(*) AS c FROM " + table).map((r, m) -> r.get("c", Long.class))
                .one().block();
    }

    @Test
    void appendSample_newSample_emitsGeneratedIdAndPersistsRow() {
        TelemetrySample s = sample("dev-1", MetricKind.POWER, T0, 250.5, ValidationStatus.UNVALIDATED);

        StepVerifier.create(repository.appendSample(s)).assertNext(id -> assertThat(id).isPositive())
                .verifyComplete();

        var row = client.sql("SELECT device_id, metric, t_device, t_ingress, value, validation_status "
                + "FROM telemetry_sample").fetch().one().block();
        assertThat(row).containsEntry("DEVICE_ID", "dev-1").containsEntry("METRIC", "POWER")
                .containsEntry("T_DEVICE", LocalDateTime.ofInstant(T0, ZoneOffset.UTC))
                .containsEntry("T_INGRESS", LocalDateTime.ofInstant(INGRESS, ZoneOffset.UTC))
                .containsEntry("VALUE", 250.5)
                .containsEntry("VALIDATION_STATUS", ValidationStatus.UNVALIDATED.name());
    }

    @Test
    void appendSample_duplicateIdentity_emitsEmptyAndKeepsSingleRow() {
        TelemetrySample s = sample("dev-1", MetricKind.POWER, T0, 250.5, ValidationStatus.UNVALIDATED);
        repository.appendSample(s).block();

        StepVerifier.create(repository.appendSample(s)).verifyComplete();

        assertThat(count("telemetry_sample")).isEqualTo(1);
    }

    @Test
    void appendSample_validationFailedPayload_persistsRawValueAndStatus() {
        TelemetrySample s = sample("dev-1", MetricKind.HEART_RATE, T0, -999.0, ValidationStatus.VALIDATION_FAILED);

        repository.appendSample(s).block();

        var row = client.sql("SELECT value, validation_status FROM telemetry_sample").fetch().one().block();
        assertThat(row).containsEntry("VALUE", -999.0).containsEntry("VALIDATION_STATUS", "VALIDATION_FAILED");
    }

    @Test
    void appendSample_sameTimestampDifferentMetric_storesBoth() {
        repository.appendSample(sample("dev-1", MetricKind.POWER, T0, 1, ValidationStatus.UNVALIDATED)).block();

        StepVerifier.create(repository.appendSample(
                sample("dev-1", MetricKind.CADENCE, T0, 2, ValidationStatus.UNVALIDATED)))
                .expectNextCount(1).verifyComplete();

        assertThat(count("telemetry_sample")).isEqualTo(2);
    }

    @Test
    void appendSample_otherError_propagates() {
        DatabaseClient broken = DatabaseClient.create(ConnectionFactories.get(
                "r2dbc:h2:mem:///" + UUID.randomUUID() + ";DB_CLOSE_DELAY=-1;NON_KEYWORDS=VALUE"));
        R2dbcTelemetryHistoryRepository noSchema = new R2dbcTelemetryHistoryRepository(broken);

        StepVerifier.create(noSchema.appendSample(
                sample("dev-1", MetricKind.POWER, T0, 1, ValidationStatus.UNVALIDATED)))
                .expectError().verify();
    }

    @Test
    void appendRevision_firstAndSecond_emitRevisionNumbersOneThenTwo() {
        long id = repository.appendSample(sample("dev-1", MetricKind.POWER, T0, 1, ValidationStatus.UNVALIDATED))
                .block();
        RevisionReason reason = RevisionReason.values()[0];

        StepVerifier.create(repository.appendRevision(id, reason, 5.0, INGRESS)).expectNext(1).verifyComplete();
        StepVerifier.create(repository.appendRevision(id, reason, 6.0, INGRESS)).expectNext(2).verifyComplete();

        assertThat(count("event_revision")).isEqualTo(2);
    }

    @Test
    void appendRevision_otherSample_startsAtOne() {
        long a = repository.appendSample(sample("dev-1", MetricKind.POWER, T0, 1, ValidationStatus.UNVALIDATED))
                .block();
        long b = repository.appendSample(sample("dev-2", MetricKind.POWER, T0, 1, ValidationStatus.UNVALIDATED))
                .block();
        RevisionReason reason = RevisionReason.values()[0];
        repository.appendRevision(a, reason, 5.0, INGRESS).block();

        StepVerifier.create(repository.appendRevision(b, reason, 5.0, INGRESS)).expectNext(1).verifyComplete();
    }

    @Test
    void appendRevision_unknownSample_propagatesConstraintError() {
        StepVerifier.create(repository.appendRevision(9999L, RevisionReason.values()[0], 1.0, INGRESS))
                .expectError().verify();
    }

    @Test
    void findLatestTDevice_severalSamples_emitsGreatest() {
        repository.appendSample(sample("dev-1", MetricKind.POWER, T0.plusSeconds(10), 1,
                ValidationStatus.UNVALIDATED)).block();
        repository.appendSample(sample("dev-1", MetricKind.POWER, T0, 1, ValidationStatus.UNVALIDATED)).block();

        StepVerifier.create(repository.findLatestTDevice("dev-1", MetricKind.POWER))
                .expectNext(T0.plusSeconds(10)).verifyComplete();
    }

    @Test
    void findLatestTDevice_nothingStored_emitsEmpty() {
        StepVerifier.create(repository.findLatestTDevice("dev-1", MetricKind.POWER)).verifyComplete();
    }

    @Test
    void findWindow_insertedOutOfOrder_returnsAscendingByTDevice() {
        repository.appendSample(sample("dev-1", MetricKind.POWER, T0.plusSeconds(20), 3,
                ValidationStatus.UNVALIDATED)).block();
        repository.appendSample(sample("dev-1", MetricKind.POWER, T0, 1, ValidationStatus.UNVALIDATED)).block();
        repository.appendSample(sample("dev-1", MetricKind.POWER, T0.plusSeconds(10), 2,
                ValidationStatus.UNVALIDATED)).block();

        StepVerifier.create(repository.findWindow("dev-1", MetricKind.POWER, T0, T0.plusSeconds(20), 10)
                .map(TelemetrySample::tDevice))
                .expectNext(T0, T0.plusSeconds(10), T0.plusSeconds(20)).verifyComplete();
    }

    @Test
    void findWindow_boundsInclusive_excludesOutside() {
        for (int i = 0; i < 5; i++) {
            repository.appendSample(sample("dev-1", MetricKind.POWER, T0.plusSeconds(i), i,
                    ValidationStatus.UNVALIDATED)).block();
        }

        StepVerifier.create(repository.findWindow("dev-1", MetricKind.POWER, T0.plusSeconds(1),
                T0.plusSeconds(3), 10).map(TelemetrySample::value))
                .expectNext(1.0, 2.0, 3.0).verifyComplete();
    }

    @Test
    void findWindow_limitSmallerThanMatches_returnsAtMostLimit() {
        for (int i = 0; i < 5; i++) {
            repository.appendSample(sample("dev-1", MetricKind.POWER, T0.plusSeconds(i), i,
                    ValidationStatus.UNVALIDATED)).block();
        }

        StepVerifier.create(repository.findWindow("dev-1", MetricKind.POWER, T0, T0.plusSeconds(10), 2)
                .map(TelemetrySample::value)).expectNext(0.0, 1.0).verifyComplete();
    }

    @Test
    void findWindow_storedRow_mapsAllSampleFields() {
        TelemetrySample s = sample("dev-1", MetricKind.SWIM_PACE, T0, 1.5, ValidationStatus.VALIDATION_FAILED);
        repository.appendSample(s).block();

        StepVerifier.create(repository.findWindow("dev-1", MetricKind.SWIM_PACE, T0, T0, 5))
                .expectNext(s).verifyComplete();
    }
}
