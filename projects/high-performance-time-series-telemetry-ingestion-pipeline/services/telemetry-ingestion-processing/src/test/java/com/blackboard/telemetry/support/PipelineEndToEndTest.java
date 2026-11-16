package com.blackboard.telemetry.support;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.http.MediaType;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class PipelineEndToEndTest {

    private static final String URI = "/api/v1/telemetry/packets";

    @Autowired
    private WebTestClient webClient;

    @Autowired
    private DatabaseClient databaseClient;

    private Mono<Long> awaitRows(String table, long expected) {
        return Mono.defer(() -> PipelineSliceFixtures.countRows(databaseClient, table))
                .filter(count -> count >= expected)
                .repeatWhenEmpty(100, attempts -> attempts.delayElements(Duration.ofMillis(50)));
    }

    private WebTestClient.ResponseSpec post(String body) {
        return webClient.post().uri(URI).contentType(MediaType.APPLICATION_JSON).bodyValue(body).exchange();
    }

    @Test
    void packetJson_validArguments_buildsSingleObjectBody() {
        String json = PipelineSliceFixtures.packetJson("dev-1", "EDGE_DEVICE", "HEART_RATE", 1000L, 72.5);

        assertThat(json).contains("\"deviceId\"", "dev-1", "\"sourceKind\"", "EDGE_DEVICE", "HEART_RATE", "1000", "72.5");
    }

    @Test
    void countRows_unknownTable_throwsIllegalArgument() {
        assertThatThrownBy(() -> PipelineSliceFixtures.countRows(databaseClient, "users"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void countRows_allowedTable_emitsCount() {
        StepVerifier.create(PipelineSliceFixtures.countRows(databaseClient, "audit_trail"))
                .assertNext(count -> assertThat(count).isGreaterThanOrEqualTo(0L))
                .verifyComplete();
    }

    @Test
    void ingest_validHeartRatePacket_returns202AndPersistsValidRowWithCorrelation() {
        String body = PipelineSliceFixtures.packetJson("dev-valid", "EDGE_DEVICE", "HEART_RATE",
                Instant.now().toEpochMilli(), 72.0);

        String requestId = post(body).expectStatus().isAccepted().returnResult(Void.class)
                .getResponseHeaders().getFirst("X-Request-Id");

        StepVerifier.create(awaitRows("telemetry_sample", 1)).expectNextCount(1).verifyComplete();
        Map<String, Object> row = databaseClient.sql(
                        "SELECT validation_status FROM telemetry_sample WHERE device_id = 'dev-valid'")
                .fetch().one().block();
        Long audited = databaseClient.sql(
                        "SELECT COUNT(*) AS c FROM audit_trail WHERE correlation_id = :id")
                .bind("id", requestId).map(r -> r.get("c", Long.class)).one().block();
        assertThat(row.get("validation_status")).isEqualTo("VALID");
        assertThat(audited).isGreaterThanOrEqualTo(1L);
    }

    @Test
    void ingest_outOfBoundsHeartRate_returns202AndKeepsValidationFailedRow() {
        String body = PipelineSliceFixtures.packetJson("dev-high", "EDGE_DEVICE", "HEART_RATE",
                Instant.now().toEpochMilli(), 300.0);

        post(body).expectStatus().isAccepted();

        StepVerifier.create(awaitRows("telemetry_sample", 1)).expectNextCount(1).verifyComplete();
        Map<String, Object> row = databaseClient.sql(
                        "SELECT validation_status, value FROM telemetry_sample WHERE device_id = 'dev-high'")
                .fetch().one().block();
        assertThat(row.get("validation_status")).isEqualTo("VALIDATION_FAILED");
        assertThat(((Number) row.get("value")).doubleValue()).isEqualTo(300.0);
    }

    @Test
    void ingest_samePacketResent_keepsOneRowAndNoRevision() {
        String body = PipelineSliceFixtures.packetJson("dev-retry", "EDGE_DEVICE", "HEART_RATE",
                Instant.now().toEpochMilli(), 70.0);

        post(body).expectStatus().isAccepted();
        post(body).expectStatus().isAccepted();

        StepVerifier.create(awaitRows("telemetry_sample", 1)).expectNextCount(1).verifyComplete();
        Long rows = databaseClient.sql("SELECT COUNT(*) AS c FROM telemetry_sample WHERE device_id = 'dev-retry'")
                .map(r -> r.get("c", Long.class)).one().block();
        Long revisions = PipelineSliceFixtures.countRows(databaseClient, "event_revision").block();
        assertThat(rows).isEqualTo(1L);
        assertThat(revisions).isZero();
    }

    @Test
    void ingest_lateArrivingPacket_appendsRevisionOneAndAuditRow() {
        String body = PipelineSliceFixtures.packetJson("dev-late", "EDGE_DEVICE", "HEART_RATE",
                Instant.now().minusSeconds(120).toEpochMilli(), 80.0);

        post(body).expectStatus().isAccepted();

        StepVerifier.create(awaitRows("event_revision", 1)).expectNextCount(1).verifyComplete();
        Integer revisionNo = databaseClient.sql("SELECT MIN(revision_no) AS n FROM event_revision")
                .map(r -> r.get("n", Integer.class)).one().block();
        Long audits = databaseClient.sql("SELECT COUNT(*) AS c FROM audit_trail WHERE action = 'APPEND_REVISION'")
                .map(r -> r.get("c", Long.class)).one().block();
        assertThat(revisionNo).isEqualTo(1);
        assertThat(audits).isGreaterThanOrEqualTo(1L);
    }

    @Test
    void ingest_blankDeviceId_returns400AndWritesNoRows() {
        String body = PipelineSliceFixtures.packetJson(" ", "EDGE_DEVICE", "HEART_RATE",
                Instant.now().toEpochMilli(), 72.0);

        post(body).expectStatus().isBadRequest();

        Long rows = databaseClient.sql("SELECT COUNT(*) AS c FROM telemetry_sample WHERE device_id = ' '")
                .map(r -> r.get("c", Long.class)).one().block();
        assertThat(rows).isZero();
    }
}
