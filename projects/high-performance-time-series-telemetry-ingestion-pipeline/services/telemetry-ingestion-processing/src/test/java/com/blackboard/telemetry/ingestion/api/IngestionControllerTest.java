package com.blackboard.telemetry.ingestion.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.assertj.core.api.Assertions.assertThat;

import com.blackboard.telemetry.ingestion.application.IngestPacketService;
import com.blackboard.telemetry.ingestion.domain.IngressPacket;
import com.blackboard.telemetry.ingestion.domain.SourceKind;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Mono;

class IngestionControllerTest {

    private static final Instant NOW = Instant.parse("2026-01-01T10:00:00Z");
    private static final String URI = "/api/v1/telemetry/packets";

    private IngestPacketService service;
    private WebTestClient client;
    private String sourceKind;

    @BeforeEach
    void setUp() {
        service = mock(IngestPacketService.class);
        sourceKind = SourceKind.values()[0].name();
        client = WebTestClient.bindToController(new IngestionController(service, Clock.fixed(NOW, ZoneOffset.UTC)))
                .build();
    }

    private WebTestClient.ResponseSpec post(String body) {
        return client.post().uri(URI).contentType(MediaType.APPLICATION_JSON).bodyValue(body).exchange();
    }

    private String body(String deviceId, String kind, String samples) {
        return "{\"deviceId\":\"" + deviceId + "\",\"sourceKind\":\"" + kind + "\",\"samples\":" + samples + "}";
    }

    private static final String ONE_SAMPLE = "[{\"metric\":\"POWER\",\"tDeviceEpochMillis\":1000,\"value\":250.0}]";

    @Test
    void ingest_validBody_answers202WithNoBody() {
        when(service.ingest(any())).thenReturn(Mono.empty());

        post(body("dev-1", sourceKind, ONE_SAMPLE)).expectStatus().isAccepted().expectBody().isEmpty();
    }

    @Test
    void ingest_validBody_passesDomainPacketStampedWithClockInstant() {
        when(service.ingest(any())).thenReturn(Mono.empty());

        post(body("dev-1", sourceKind, ONE_SAMPLE)).expectStatus().isAccepted();

        ArgumentCaptor<IngressPacket> captor = ArgumentCaptor.forClass(IngressPacket.class);
        verify(service).ingest(captor.capture());
        assertThat(captor.getValue().deviceId()).isEqualTo("dev-1");
        assertThat(captor.getValue().samples().get(0).tIngress()).isEqualTo(NOW);
        assertThat(captor.getValue().samples().get(0).tDevice()).isEqualTo(Instant.ofEpochMilli(1000));
    }

    @Test
    void ingest_blankDeviceId_answers400WithoutCallingService() {
        post(body("", sourceKind, ONE_SAMPLE)).expectStatus().isBadRequest();

        verify(service, never()).ingest(any());
    }

    @Test
    void ingest_emptySamples_answers400WithoutCallingService() {
        post(body("dev-1", sourceKind, "[]")).expectStatus().isBadRequest();

        verify(service, never()).ingest(any());
    }

    @Test
    void ingest_unknownMetric_answers400() {
        String samples = "[{\"metric\":\"NOPE\",\"tDeviceEpochMillis\":1000,\"value\":1.0}]";

        post(body("dev-1", sourceKind, samples)).expectStatus().isBadRequest();

        verify(service, never()).ingest(any());
    }

    @Test
    void ingest_unknownSourceKind_answers400() {
        post(body("dev-1", "NOT_A_KIND", ONE_SAMPLE)).expectStatus().isBadRequest();
    }

    @Test
    void ingest_serviceOverflow_answers503() {
        when(service.ingest(any())).thenReturn(Mono.error(new IllegalStateException("overflow")));

        post(body("dev-1", sourceKind, ONE_SAMPLE)).expectStatus().isEqualTo(503);
    }

    @Test
    void ingest_arrayBody_isRejectedAsClientError() {
        post("[" + body("dev-1", sourceKind, ONE_SAMPLE) + "]").expectStatus().is4xxClientError();

        verify(service, never()).ingest(any());
    }
}
