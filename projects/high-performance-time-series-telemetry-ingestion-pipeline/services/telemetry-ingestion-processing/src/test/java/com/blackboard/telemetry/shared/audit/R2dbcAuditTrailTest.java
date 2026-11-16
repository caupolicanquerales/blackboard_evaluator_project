package com.blackboard.telemetry.shared.audit;

import static org.assertj.core.api.Assertions.assertThat;

import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Stream;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.test.StepVerifier;

class R2dbcAuditTrailTest {

    private static final Path MIGRATIONS = Path.of("db", "migrations");

    private DatabaseClient client;
    private R2dbcAuditTrail trail;

    @BeforeEach
    void setUp() throws IOException {
        ConnectionFactory factory = ConnectionFactories.get(
                "r2dbc:h2:mem:///audit" + UUID.randomUUID().toString().replace("-", "")
                        + ";DB_CLOSE_DELAY=-1;NON_KEYWORDS=VALUE");
        client = DatabaseClient.create(factory);
        for (String prefix : List.of("V1__", "V2__")) {
            for (String statement : readMigration(prefix).split(";")) {
                if (!statement.isBlank()) {
                    client.sql(statement).fetch().rowsUpdated().block();
                }
            }
        }
        trail = new R2dbcAuditTrail(client);
    }

    private static String readMigration(String prefix) throws IOException {
        try (Stream<Path> files = Files.list(MIGRATIONS)) {
            Path file = files.filter(p -> p.getFileName().toString().startsWith(prefix))
                    .findFirst().orElseThrow();
            return Files.readString(file);
        }
    }

    private static AuditEntry entry(String actor, String outcome, String correlationId) {
        return new AuditEntry(actor, AuditAction.values()[0], outcome,
                Instant.parse("2025-03-04T05:06:07Z"), correlationId);
    }

    private List<Map<String, Object>> rows() {
        return client.sql("SELECT actor, action, outcome, occurred_at, correlation_id FROM audit_trail ORDER BY id")
                .fetch().all().collectList().block();
    }

    @Test
    void record_validEntry_persistsRowEqualToEntry() {
        AuditEntry entry = entry("device-1", "SUCCESS", "req-1");

        StepVerifier.create(trail.record(entry)).verifyComplete();

        Map<String, Object> row = rows().get(0);
        assertThat(row.get("ACTOR")).isEqualTo("device-1");
        assertThat(row.get("ACTION")).isEqualTo(entry.action().name());
        assertThat(row.get("OUTCOME")).isEqualTo("SUCCESS");
        assertThat(row.get("OCCURRED_AT"))
                .isEqualTo(LocalDateTime.ofInstant(entry.timestamp(), ZoneOffset.UTC));
        assertThat(row.get("CORRELATION_ID")).isEqualTo("req-1");
    }

    @Test
    void record_failureOutcome_persistsFailure() {
        StepVerifier.create(trail.record(entry("device-1", "FAILURE", "req-2"))).verifyComplete();

        assertThat(rows().get(0).get("OUTCOME")).isEqualTo("FAILURE");
    }

    @Test
    void record_calledTwice_accumulatesRows() {
        StepVerifier.create(trail.record(entry("a", "SUCCESS", "r1"))
                .then(trail.record(entry("b", "FAILURE", "r2")))).verifyComplete();

        assertThat(rows()).hasSize(2);
    }

    @Test
    void record_actorExceedsColumnLength_emitsErrorAndStoresNothing() {
        AuditEntry tooLong = entry("x".repeat(200), "SUCCESS", "req-3");

        StepVerifier.create(trail.record(tooLong)).expectError().verify();

        assertThat(rows()).isEmpty();
    }

    @Test
    void record_correlationIdExceedsColumnLength_emitsError() {
        AuditEntry tooLong = entry("actor", "SUCCESS", "c".repeat(200));

        StepVerifier.create(trail.record(tooLong)).expectError().verify();
    }

    @Test
    void record_tableMissing_emitsErrorSignal() {
        client.sql("DROP TABLE audit_trail").fetch().rowsUpdated().block();

        StepVerifier.create(trail.record(entry("a", "SUCCESS", "r"))).expectError().verify();
    }
}
