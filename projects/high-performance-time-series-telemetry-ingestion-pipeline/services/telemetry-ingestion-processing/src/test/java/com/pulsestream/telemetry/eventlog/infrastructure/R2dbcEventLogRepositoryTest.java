package com.pulsestream.telemetry.eventlog.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import java.time.Duration;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.test.StepVerifier;

@SpringBootTest
class R2dbcEventLogRepositoryTest {

    private static final Duration TIMEOUT = Duration.ofSeconds(10);

    @Autowired
    private DatabaseClient client;

    private R2dbcEventLogRepository repository;

    @BeforeEach
    void setUp() {
        repository = new R2dbcEventLogRepository(client);
        client.sql("DELETE FROM telemetry_event_log.telemetry_record_revisions").then().block(TIMEOUT);
        client.sql("DELETE FROM telemetry_event_log.telemetry_records").then().block(TIMEOUT);
    }

    private static TelemetrySample sample(String device, long tDevice, double value) {
        return new TelemetrySample(device, "temp", tDevice, value, tDevice + 1, TelemetrySample.VALID);
    }

    private long count(String table) {
        return client.sql("SELECT COUNT(*) AS c FROM telemetry_event_log." + table)
                .map(row -> row.get("c", Long.class)).one().block(TIMEOUT);
    }

    @Test
    void appendRecord_sameIdentityTwice_emitsTrueThenFalseAndStoresOneRow() {
        TelemetrySample s = sample("d1", 1_000L, 1.0);

        StepVerifier.create(repository.appendRecord(s)).expectNext(true).expectComplete().verify(TIMEOUT);
        StepVerifier.create(repository.appendRecord(s)).expectNext(false).expectComplete().verify(TIMEOUT);

        assertThat(count("telemetry_records")).isEqualTo(1L);
    }

    @Test
    void appendRevision_existingRecord_storesRevisionAndKeepsOriginal() {
        TelemetrySample original = sample("d1", 1_000L, 1.0);
        repository.appendRecord(original).block(TIMEOUT);

        StepVerifier.create(repository.appendRevision(sample("d1", 1_000L, 9.0)))
                .expectComplete().verify(TIMEOUT);

        assertThat(count("telemetry_record_revisions")).isEqualTo(1L);
        StepVerifier.create(repository.findByDeviceAndRange("d1", 0L, 2_000L))
                .expectNext(original).expectComplete().verify(TIMEOUT);
    }

    @Test
    void findByDeviceAndRange_mixedData_returnsOnlyDeviceRangeOrderedByTDevice() {
        TelemetrySample late = sample("d1", 3_000L, 3.0);
        TelemetrySample early = sample("d1", 1_000L, 1.0);
        repository.appendRecord(late).block(TIMEOUT);
        repository.appendRecord(early).block(TIMEOUT);
        repository.appendRecord(sample("d1", 9_000L, 9.0)).block(TIMEOUT);
        repository.appendRecord(sample("d2", 2_000L, 2.0)).block(TIMEOUT);

        StepVerifier.create(repository.findByDeviceAndRange("d1", 1_000L, 3_000L))
                .expectNext(early, late).expectComplete().verify(TIMEOUT);
    }
}
