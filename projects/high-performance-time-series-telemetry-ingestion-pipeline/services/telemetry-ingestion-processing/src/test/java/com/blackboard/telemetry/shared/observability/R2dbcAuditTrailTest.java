package com.blackboard.telemetry.shared.observability;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.data.r2dbc.DataR2dbcTest;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.test.StepVerifier;

@DataR2dbcTest(properties = {
        "spring.r2dbc.url=r2dbc:h2:mem:///audittrail;DB_CLOSE_DELAY=-1;NON_KEYWORDS=VALUE",
        "spring.flyway.enabled=false"
})
class R2dbcAuditTrailTest {

    private static final Instant TS = Instant.parse("2024-01-01T00:00:00Z");

    @Autowired
    private DatabaseClient databaseClient;

    private R2dbcAuditTrail trail;

    @BeforeEach
    void setUp() {
        databaseClient.sql("DROP TABLE IF EXISTS audit_trail").then().block();
        databaseClient.sql("""
                CREATE TABLE audit_trail (
                    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    actor          VARCHAR(128) NOT NULL,
                    action         VARCHAR(128) NOT NULL,
                    outcome        VARCHAR(64)  NOT NULL,
                    occurred_at    TIMESTAMP WITH TIME ZONE NOT NULL,
                    correlation_id VARCHAR(128) NOT NULL
                )""").then().block();
        trail = new R2dbcAuditTrail(databaseClient);
    }

    private long rowCount() {
        return databaseClient.sql("SELECT COUNT(*) AS c FROM audit_trail")
                .map(row -> row.get("c", Long.class)).one().block();
    }

    @Test
    void record_entry_completesEmpty() {
        AuditEntry entry = new AuditEntry("actor-1", "INGEST", "SUCCESS", TS, "req-1");

        StepVerifier.create(trail.record(entry)).verifyComplete();
    }

    @Test
    void record_entry_insertsOneRowWithAllFields() {
        trail.record(new AuditEntry("actor-1", "INGEST", "SUCCESS", TS, "req-1")).block();

        Map<String, Object> row = databaseClient.sql("SELECT * FROM audit_trail")
                .fetch().one().block();

        assertThat(rowCount()).isEqualTo(1);
        assertThat(row.get("ACTOR")).isEqualTo("actor-1");
        assertThat(row.get("ACTION")).isEqualTo("INGEST");
        assertThat(row.get("OUTCOME")).isEqualTo("SUCCESS");
        assertThat(row.get("CORRELATION_ID")).isEqualTo("req-1");
        assertThat(((OffsetDateTime) row.get("OCCURRED_AT")).withOffsetSameInstant(ZoneOffset.UTC).toInstant())
                .isEqualTo(TS);
    }

    @Test
    void record_twice_insertsTwoRows() {
        AuditEntry entry = new AuditEntry("actor-1", "INGEST", "SUCCESS", TS, "req-1");

        trail.record(entry).block();
        trail.record(entry).block();

        assertThat(rowCount()).isEqualTo(2);
    }
}
