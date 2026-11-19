package com.pulsestream.telemetry.ingestion.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.application.AuditEntry;
import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import java.lang.reflect.Method;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.time.Instant;
import java.util.Arrays;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.FileSystemResource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.test.StepVerifier;

class R2dbcAuditTrailTest {

    private static final Instant NOW = Instant.parse("2026-01-01T00:00:00Z");

    private DatabaseClient client;
    private R2dbcAuditTrail trail;

    @BeforeEach
    void setUp() throws Exception {
        String name = "audit" + UUID.randomUUID().toString().replace("-", "");
        try (Connection c = DriverManager.getConnection(
                "jdbc:h2:mem:" + name + ";DB_CLOSE_DELAY=-1", "sa", "")) {
            ScriptUtils.executeSqlScript(c,
                    new FileSystemResource(Path.of("db/migrations/V3__create_audit_trail.sql")));
        }
        ConnectionFactory cf = ConnectionFactories.get(
                "r2dbc:h2:mem:///" + name + ";DB_CLOSE_DELAY=-1;USER=sa;PASSWORD=");
        client = DatabaseClient.create(cf);
        trail = new R2dbcAuditTrail(client);
    }

    private Map<String, Object> onlyRow() {
        return client.sql("SELECT actor, action, outcome, correlation_id FROM audit_trail")
                .fetch().one().block();
    }

    @Test
    void record_validEntry_persistsDurableRowWithAllFields() {
        var entry = new AuditEntry("dev-1", "INGEST", "DENIED", NOW, "corr-1");

        StepVerifier.create(trail.record(entry)).verifyComplete();

        assertThat(onlyRow()).containsEntry("ACTOR", "dev-1").containsEntry("ACTION", "INGEST")
                .containsEntry("OUTCOME", "DENIED").containsEntry("CORRELATION_ID", "corr-1");
    }

    @Test
    void record_validEntry_storesOccurredAtTimestamp() {
        StepVerifier.create(trail.record(new AuditEntry("dev-1", "INGEST", "OK", NOW, "corr-1")))
                .verifyComplete();

        Object at = client.sql("SELECT occurred_at FROM audit_trail").fetch().one().block()
                .get("OCCURRED_AT");
        assertThat(at).isNotNull();
        assertThat(at.toString()).contains("2026-01-01T00:00");
    }

    @Test
    void record_twoEntries_appendsTwoRows() {
        StepVerifier.create(trail.record(new AuditEntry("a", "x", "OK", NOW, "c1"))
                .then(trail.record(new AuditEntry("a", "x", "OK", NOW, "c2")))).verifyComplete();

        Number n = (Number) client.sql("SELECT COUNT(*) AS c FROM audit_trail").fetch().one().block().get("C");
        assertThat(n.longValue()).isEqualTo(2L);
    }

    @Test
    void record_nullActor_failsNotNullConstraint() {
        StepVerifier.create(trail.record(new AuditEntry(null, "INGEST", "OK", NOW, "corr-1")))
                .expectError().verify();
    }

    @Test
    void auditTrail_publicSurface_exposesNoUpdateOrDeletePath() {
        var names = Arrays.stream(R2dbcAuditTrail.class.getDeclaredMethods())
                .filter(m -> java.lang.reflect.Modifier.isPublic(m.getModifiers()))
                .map(Method::getName).toList();

        assertThat(names).containsExactly("record");
    }
}
