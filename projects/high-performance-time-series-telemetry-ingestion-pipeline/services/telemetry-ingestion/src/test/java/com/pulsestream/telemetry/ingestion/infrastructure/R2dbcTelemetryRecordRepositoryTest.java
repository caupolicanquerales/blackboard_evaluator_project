package com.pulsestream.telemetry.ingestion.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.domain.TelemetryRevision;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;
import io.r2dbc.spi.ConnectionFactories;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.FileSystemResource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.test.StepVerifier;

class R2dbcTelemetryRecordRepositoryTest {

    private static final Instant T = Instant.parse("2026-01-01T00:00:00Z");
    private static final String PLAIN = "{\"secret\":\"plain-payload-marker\"}";

    private DatabaseClient client;
    private R2dbcTelemetryRecordRepository repo;

    @BeforeEach
    void setUp() throws Exception {
        String name = "rec" + UUID.randomUUID().toString().replace("-", "");
        try (Connection c = DriverManager.getConnection(
                "jdbc:h2:mem:" + name + ";DB_CLOSE_DELAY=-1", "sa", "")) {
            for (String v : new String[] {"V1__create_telemetry_records.sql",
                    "V2__create_telemetry_revisions.sql", "V3__create_audit_trail.sql"}) {
                ScriptUtils.executeSqlScript(c, new FileSystemResource(Path.of("db/migrations", v)));
            }
        }
        client = DatabaseClient.create(ConnectionFactories.get(
                "r2dbc:h2:mem:///" + name + ";DB_CLOSE_DELAY=-1;USER=sa;PASSWORD="));
        repo = new R2dbcTelemetryRecordRepository(client, new AesGcmPayloadCipher(new byte[32]));
    }

    private static TelemetrySample sample(String device, String payload) {
        return new TelemetrySample(device, "temp", T, T.plusSeconds(1), 21.5, ValidationStatus.VALIDATED, payload);
    }

    private long count(String table) {
        Map<String, Object> row = client.sql("SELECT COUNT(*) AS c FROM " + table).fetch().one().block();
        return ((Number) row.get("C")).longValue();
    }

    @Test
    void appendRecord_newIdentity_returnsTrueAndPersistsRow() {
        StepVerifier.create(repo.appendRecord(sample("dev-1", PLAIN))).expectNext(true).verifyComplete();

        assertThat(count("telemetry_records")).isEqualTo(1);
    }

    @Test
    void appendRecord_newIdentity_storesPayloadColumnNotAsPlaintext() {
        repo.appendRecord(sample("dev-1", PLAIN)).block();

        Object stored = client.sql("SELECT payload FROM telemetry_records").fetch().one().block().get("PAYLOAD");
        assertThat(stored).isNotNull();
        assertThat(stored.toString()).isNotEqualTo(PLAIN).doesNotContain("plain-payload-marker");
    }

    @Test
    void appendRecord_newIdentity_writesRevisionOne() {
        repo.appendRecord(sample("dev-1", PLAIN)).block();

        StepVerifier.create(repo.findLatestRevision("dev-1", "temp", T))
                .assertNext(r -> assertThat(r.revisionNumber()).isEqualTo(1))
                .verifyComplete();
    }

    @Test
    void appendRecord_duplicateIdentity_returnsFalseAndKeepsOneRow() {
        repo.appendRecord(sample("dev-1", PLAIN)).block();

        StepVerifier.create(repo.appendRecord(sample("dev-1", PLAIN))).expectNext(false).verifyComplete();

        assertThat(count("telemetry_records")).isEqualTo(1);
    }

    @Test
    void appendRevision_secondRevision_becomesLatest() {
        repo.appendRecord(sample("dev-1", PLAIN)).block();

        StepVerifier.create(repo.appendRevision(new TelemetryRevision("dev-1", "temp", T, 2, 30.0, "CORRECTION")))
                .verifyComplete();

        StepVerifier.create(repo.findLatestRevision("dev-1", "temp", T))
                .assertNext(r -> {
                    assertThat(r.revisionNumber()).isEqualTo(2);
                    assertThat(r.value()).isEqualTo(30.0);
                })
                .verifyComplete();
    }

    @Test
    void findLatestRevision_unknownIdentity_isEmpty() {
        StepVerifier.create(repo.findLatestRevision("ghost", "temp", T)).verifyComplete();
    }

    @Test
    void appendRecord_nullDeviceId_failsNotNullConstraint() {
        StepVerifier.create(reactor.core.publisher.Mono.defer(() -> repo.appendRecord(sample(null, PLAIN))))
                .expectError().verify();
    }
}
