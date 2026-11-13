package com.blackboard.telemetry.eventstore.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.blackboard.telemetry.eventstore.domain.TelemetryRecord;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.data.r2dbc.DataR2dbcTest;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.test.StepVerifier;

@DataR2dbcTest(properties = {
        "spring.r2dbc.url=r2dbc:h2:mem:///eventstore;DB_CLOSE_DELAY=-1;NON_KEYWORDS=VALUE",
        "spring.flyway.enabled=false"
})
class R2dbcTelemetryEventStoreTest {

    private static final Instant T1 = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T2 = Instant.parse("2024-01-01T00:01:00Z");
    private static final Instant T3 = Instant.parse("2024-01-01T00:02:00Z");

    @Autowired
    private DatabaseClient databaseClient;

    private R2dbcTelemetryEventStore store;

    @BeforeEach
    void setUp() {
        databaseClient.sql("DROP TABLE IF EXISTS telemetry_records").then().block();
        databaseClient.sql("""
                CREATE TABLE telemetry_records (
                    device_id VARCHAR(128) NOT NULL,
                    metric VARCHAR(128) NOT NULL,
                    t_device TIMESTAMP WITH TIME ZONE NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    "value" DOUBLE PRECISION,
                    validation_status VARCHAR(32) NOT NULL,
                    t_ingress TIMESTAMP WITH TIME ZONE NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    CONSTRAINT pk_telemetry_records PRIMARY KEY (device_id, metric, t_device, revision)
                )""").then().block();
        store = new R2dbcTelemetryEventStore(databaseClient);
    }

    private static TelemetryRecord rec(Instant tDevice, long revision) {
        return new TelemetryRecord("dev-1", "temp", tDevice, tDevice, 10.0 + revision, "VALIDATED", revision);
    }

    private long rowCount() {
        return databaseClient.sql("SELECT COUNT(*) AS c FROM telemetry_records")
                .map(row -> row.get("c", Long.class)).one().block();
    }

    @Test
    void append_newRecord_insertsRowAndEmitsRecord() {
        TelemetryRecord record = rec(T1, 1);

        StepVerifier.create(store.append(record)).expectNext(record).verifyComplete();

        assertThat(rowCount()).isEqualTo(1);
    }

    @Test
    void append_higherRevisionSameIdentity_keepsOldRow() {
        store.append(rec(T1, 1)).block();

        StepVerifier.create(store.append(rec(T1, 2))).expectNext(rec(T1, 2)).verifyComplete();

        assertThat(rowCount()).isEqualTo(2);
    }

    @Test
    void findLatestInRange_multipleRevisions_returnsHighestRevisionOnly() {
        store.append(rec(T1, 1)).block();
        store.append(rec(T1, 2)).block();

        StepVerifier.create(store.findLatestInRange("dev-1", "temp", T1, T3))
                .expectNext(rec(T1, 2)).verifyComplete();
    }

    @Test
    void findLatestInRange_unorderedAppends_returnsOrderedByTDevice() {
        store.append(rec(T3, 1)).block();
        store.append(rec(T1, 1)).block();
        store.append(rec(T2, 1)).block();

        StepVerifier.create(store.findLatestInRange("dev-1", "temp", T1, T3).map(TelemetryRecord::tDevice))
                .expectNext(T1, T2, T3).verifyComplete();
    }

    @Test
    void findLatestInRange_recordsOutsideRange_areExcluded() {
        store.append(rec(T1, 1)).block();
        store.append(rec(T2, 1)).block();
        store.append(rec(T3, 1)).block();

        StepVerifier.create(store.findLatestInRange("dev-1", "temp", T2, T3).map(TelemetryRecord::tDevice))
                .expectNext(T2, T3).verifyComplete();
    }
}
