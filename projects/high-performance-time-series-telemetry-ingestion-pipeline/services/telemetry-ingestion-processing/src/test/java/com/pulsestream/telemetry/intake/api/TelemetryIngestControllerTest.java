package com.pulsestream.telemetry.intake.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.application.IntakeService;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = "telemetry.reorder-window-seconds=1")
class TelemetryIngestControllerTest {

    private static final String PATH = "/api/v1/telemetry/packets";
    private static final String T_DEVICE = "2025-01-01T10:00:00Z";

    @LocalServerPort
    private int port;

    @Autowired
    private DatabaseClient db;

    private WebTestClient client;

    @BeforeEach
    void setUp() {
        client = WebTestClient.bindToServer().baseUrl("http://localhost:" + port).build();
        db.sql("DELETE FROM telemetry_record").fetch().rowsUpdated().block();
        db.sql("DELETE FROM audit_trail").fetch().rowsUpdated().block();
    }

    private static String body(String deviceId, String samples) {
        return "{\"deviceId\":\"" + deviceId + "\",\"samples\":" + samples + "}";
    }

    private static String heartRate(double value) {
        return "[{\"metric\":\"heart_rate\",\"tDevice\":\"" + T_DEVICE + "\",\"value\":" + value + "}]";
    }

    private WebTestClient.ResponseSpec post(String json, String requestId) {
        return client.post().uri(PATH)
                .contentType(MediaType.APPLICATION_JSON)
                .header("X-Request-Id", requestId)
                .bodyValue(json)
                .exchange();
    }

    private long count(String table) {
        return db.sql("SELECT COUNT(*) AS c FROM " + table).map((row, md) -> row.get("c", Long.class))
                .one().blockOptional().orElse(0L);
    }

    private void awaitRows(String table, long expected) {
        await().atMost(Duration.ofSeconds(8)).untilAsserted(() -> assertThat(count(table)).isEqualTo(expected));
    }

    @Test
    void ingest_validPacket_returns202WithAcceptedCount() {
        post(body("dev-1", heartRate(80)), "req-1")
                .expectStatus().isAccepted()
                .expectBody().jsonPath("$.accepted").isEqualTo(1);
    }

    @Test
    void ingest_validPacket_persistsDurableRow() {
        post(body("dev-1", heartRate(80)), "req-2").expectStatus().isAccepted();

        awaitRows("telemetry_record", 1);
        String status = db.sql("SELECT validation_status AS s FROM telemetry_record")
                .map((row, md) -> row.get("s", String.class)).one().block();
        assertThat(status).isNotEqualTo("VALIDATION_FAILED");
    }

    @Test
    void ingest_outOfRangeHeartRate_keepsValueAndMarksValidationFailed() {
        post(body("dev-1", heartRate(500)), "req-3").expectStatus().isAccepted();

        awaitRows("telemetry_record", 1);
        var row = db.sql("SELECT sample_value AS v, validation_status AS s FROM telemetry_record")
                .map((r, md) -> r.get("v", Double.class) + "|" + r.get("s", String.class)).one().block();
        assertThat(row).isEqualTo("500.0|VALIDATION_FAILED");
    }

    @Test
    void ingest_repeatedPost_appendsSecondRevisionRow() {
        post(body("dev-1", heartRate(80)), "req-4a").expectStatus().isAccepted();
        awaitRows("telemetry_record", 1);
        post(body("dev-1", heartRate(81)), "req-4b").expectStatus().isAccepted();

        awaitRows("telemetry_record", 2);
        Long maxRevision = db.sql("SELECT MAX(revision) AS r FROM telemetry_record")
                .map((r, md) -> r.get("r", Number.class).longValue()).one().block();
        assertThat(maxRevision).isEqualTo(2L);
    }

    @Test
    void ingest_requestId_isWrittenAsAuditCorrelationId() {
        post(body("dev-1", heartRate(80)), "req-audit-5").expectStatus().isAccepted();

        await().atMost(Duration.ofSeconds(8)).untilAsserted(() -> {
            Long n = db.sql("SELECT COUNT(*) AS c FROM audit_trail WHERE correlation_id = 'req-audit-5'")
                    .map((r, md) -> r.get("c", Long.class)).one().block();
            assertThat(n).isGreaterThanOrEqualTo(1L);
        });
    }

    @Test
    void ingest_blankDeviceId_returns400ProblemJsonAndNoRows() {
        post(body("", heartRate(80)), "req-6")
                .expectStatus().isBadRequest()
                .expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON);

        assertThat(count("telemetry_record")).isZero();
    }

    @Test
    void ingest_emptySamples_returns400ProblemJsonAndNoRows() {
        post(body("dev-1", "[]"), "req-7")
                .expectStatus().isBadRequest()
                .expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON);

        assertThat(count("telemetry_record")).isZero();
    }

    @Test
    void ingest_withMockedService_mapsSamplesAndAnswers202() {
        IntakeService service = mock(IntakeService.class);
        when(service.receive(anyList())).thenReturn(Mono.just(1));
        var controller = new TelemetryIngestController(service);
        var packet = new TelemetryIngestController.IngressPacketDto("dev-1",
                List.of(new TelemetryIngestController.SampleDto("heart_rate", Instant.parse(T_DEVICE), 80.0)));

        StepVerifier.create(controller.ingest(packet)
                        .contextWrite(ctx -> ctx.put(CorrelationWebFilter.CONTEXT_KEY, "rid-9")))
                .assertNext(response -> {
                    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
                    assertThat(response.getBody()).isEqualTo(new TelemetryIngestController.IngressAck(1));
                })
                .verifyComplete();

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<TelemetrySample>> captor = ArgumentCaptor.forClass(List.class);
        verify(service).receive(captor.capture());
        assertThat(captor.getValue()).singleElement().satisfies(s -> {
            assertThat(s.deviceId()).isEqualTo("dev-1");
            assertThat(s.metric()).isEqualTo("heart_rate");
            assertThat(s.status()).isEqualTo("PENDING");
            assertThat(s.tIngress()).isEqualTo(Instant.EPOCH);
            assertThat(s.correlationId()).isEqualTo("rid-9");
        });
    }
}
