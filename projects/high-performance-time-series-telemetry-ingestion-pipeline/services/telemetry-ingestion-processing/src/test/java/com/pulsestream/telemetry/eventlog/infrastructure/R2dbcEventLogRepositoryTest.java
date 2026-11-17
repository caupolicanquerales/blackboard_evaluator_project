package com.pulsestream.telemetry.eventlog.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import io.r2dbc.spi.ConnectionFactories;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.test.StepVerifier;

class R2dbcEventLogRepositoryTest {

    private static final Instant T_DEVICE = Instant.parse("2025-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2025-01-01T10:00:01Z");

    private record Fixture(DatabaseClient client, R2dbcEventLogRepository repository) {}

    private static Fixture fixture() {
        String db = "evlog" + UUID.randomUUID().toString().replace("-", "");
        Flyway.configure()
                .dataSource("jdbc:h2:mem:" + db + ";DB_CLOSE_DELAY=-1", "sa", "")
                .locations("filesystem:db/migrations")
                .load()
                .migrate();
        DatabaseClient client = DatabaseClient.create(
                ConnectionFactories.get("r2dbc:h2:mem:///" + db + ";DB_CLOSE_DELAY=-1;USER=sa;PASSWORD="));
        return new Fixture(client, new R2dbcEventLogRepository(client));
    }

    private static TelemetrySample sample(String device, double value, String status) {
        return new TelemetrySample(device, "heart_rate", T_DEVICE, T_INGRESS, value, status, "corr");
    }

    private static List<Map<String, Object>> rows(DatabaseClient client) {
        return client.sql("SELECT * FROM telemetry_record ORDER BY device_id, revision")
                .fetch().all().collectList().block();
    }

    @Test
    void append_firstSampleForKey_persistsRevisionOneKindRecord() {
        Fixture f = fixture();

        StepVerifier.create(f.repository().append(sample("d1", 120.0, "VALID")))
                .assertNext(r -> {
                    assertThat(r.revision()).isEqualTo(1);
                    assertThat(r.kind()).isEqualTo("RECORD");
                })
                .verifyComplete();

        Map<String, Object> row = rows(f.client()).get(0);
        assertThat(row.get("DEVICE_ID")).isEqualTo("d1");
        assertThat(row.get("METRIC")).isEqualTo("heart_rate");
        assertThat(((OffsetDateTime) row.get("T_DEVICE")).toInstant()).isEqualTo(T_DEVICE);
        assertThat(((OffsetDateTime) row.get("T_INGRESS")).toInstant()).isEqualTo(T_INGRESS);
        assertThat(row.get("REVISION")).isEqualTo(1);
        assertThat(row.get("SAMPLE_VALUE")).isEqualTo(120.0);
        assertThat(row.get("VALIDATION_STATUS")).isEqualTo("VALID");
    }

    @Test
    void append_secondSampleSameKey_insertsRevisionTwoAndKeepsFirstRowUnchanged() {
        Fixture f = fixture();
        f.repository().append(sample("d1", 120.0, "VALID")).block();

        StepVerifier.create(f.repository().append(sample("d1", 130.0, "VALID")))
                .assertNext(r -> {
                    assertThat(r.revision()).isEqualTo(2);
                    assertThat(r.kind()).isEqualTo("REVISION");
                })
                .verifyComplete();

        List<Map<String, Object>> rows = rows(f.client());
        assertThat(rows).hasSize(2);
        assertThat(rows.get(0).get("REVISION")).isEqualTo(1);
        assertThat(rows.get(0).get("SAMPLE_VALUE")).isEqualTo(120.0);
        assertThat(rows.get(1).get("SAMPLE_VALUE")).isEqualTo(130.0);
    }

    @Test
    void append_differentKey_startsAtRevisionOne() {
        Fixture f = fixture();
        f.repository().append(sample("d1", 120.0, "VALID")).block();

        StepVerifier.create(f.repository().append(sample("d2", 121.0, "VALID")))
                .assertNext(r -> assertThat(r.revision()).isEqualTo(1))
                .verifyComplete();
    }

    @Test
    void append_validationFailedStatus_persistsStatus() {
        Fixture f = fixture();

        f.repository().append(sample("d1", 999.0, "VALIDATION_FAILED")).block();

        assertThat(rows(f.client()).get(0).get("VALIDATION_STATUS")).isEqualTo("VALIDATION_FAILED");
    }

    @Test
    void findLatest_multipleRevisions_returnsHighestRevision() {
        Fixture f = fixture();
        f.repository().append(sample("d1", 120.0, "VALID")).block();
        f.repository().append(sample("d1", 130.0, "VALID")).block();

        StepVerifier.create(f.repository().findLatest("d1", "heart_rate", T_DEVICE))
                .assertNext((EventRecord r) -> {
                    assertThat(r.revision()).isEqualTo(2);
                    assertThat(r.sample().value()).isEqualTo(130.0);
                })
                .verifyComplete();
    }
}
