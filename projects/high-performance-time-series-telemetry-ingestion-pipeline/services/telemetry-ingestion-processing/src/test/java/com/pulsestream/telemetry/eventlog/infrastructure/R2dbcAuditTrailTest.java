package com.pulsestream.telemetry.eventlog.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.shared.observability.AuditEntry;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.test.StepVerifier;

class R2dbcAuditTrailTest {

    private static final Instant NOW = Instant.parse("2025-01-01T10:00:00Z");

    private static String newDb() {
        return "audit" + UUID.randomUUID().toString().replace("-", "");
    }

    private static DatabaseClient client(String db) {
        ConnectionFactory cf = ConnectionFactories.get("r2dbc:h2:mem:///" + db + ";DB_CLOSE_DELAY=-1;USER=sa;PASSWORD=");
        return DatabaseClient.create(cf);
    }

    private static void migrate(String db) {
        Flyway.configure()
                .dataSource("jdbc:h2:mem:" + db + ";DB_CLOSE_DELAY=-1", "sa", "")
                .locations("filesystem:db/migrations")
                .load()
                .migrate();
    }

    private static List<Map<String, Object>> rows(DatabaseClient client) {
        return client.sql("SELECT * FROM audit_trail ORDER BY audit_id")
                .fetch().all().collectList().block();
    }

    @Test
    void record_validEntry_persistsAllFieldsInDurableRow() {
        String db = newDb();
        migrate(db);
        DatabaseClient client = client(db);
        R2dbcAuditTrail trail = new R2dbcAuditTrail(client, new SimpleMeterRegistry());

        StepVerifier.create(trail.record(new AuditEntry("alice", "INGEST", "ACCEPTED", NOW, "corr-1")))
                .verifyComplete();

        Map<String, Object> row = rows(client).get(0);
        assertThat(row.get("ACTOR")).isEqualTo("alice");
        assertThat(row.get("ACTION")).isEqualTo("INGEST");
        assertThat(row.get("OUTCOME")).isEqualTo("ACCEPTED");
        assertThat(((OffsetDateTime) row.get("OCCURRED_AT")).toInstant()).isEqualTo(NOW);
        assertThat(row.get("CORRELATION_ID")).isEqualTo("corr-1");
    }

    @Test
    void record_twoEntries_persistsTwoRows() {
        String db = newDb();
        migrate(db);
        DatabaseClient client = client(db);
        R2dbcAuditTrail trail = new R2dbcAuditTrail(client, new SimpleMeterRegistry());

        trail.record(new AuditEntry("a", "X", "OK", NOW, "c1")).block();
        trail.record(new AuditEntry("b", "Y", "OK", NOW, "c2")).block();

        assertThat(rows(client)).hasSize(2);
    }

    @Test
    void record_databaseFailure_countsDroppedAuditAndCompletesEmpty() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        R2dbcAuditTrail trail = new R2dbcAuditTrail(client(newDb()), registry);

        StepVerifier.create(trail.record(new AuditEntry("a", "X", "OK", NOW, "c1")))
                .verifyComplete();

        assertThat(registry.get("telemetry.pipeline.dropped").tag("stage", "audit").counter().count())
                .isEqualTo(1.0);
    }
}
