package com.pulsestream.telemetry.ingestion.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ingestion.application.IngestPacketUseCase;
import com.pulsestream.telemetry.ingestion.application.IngestSummary;
import com.pulsestream.telemetry.ingestion.infrastructure.DeviceCredentialAuthenticationManager;
import com.pulsestream.telemetry.ingestion.infrastructure.TelemetrySecurityConfiguration;
import com.pulsestream.telemetry.ingestion.application.AuditTrail;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import java.time.Instant;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.WebFluxTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.AuthorityUtils;
import org.springframework.security.core.userdetails.ReactiveUserDetailsService;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@WebFluxTest(IngressPacketController.class)
@Import(TelemetrySecurityConfiguration.class)
class IngressPacketControllerTest {

    private static final Instant T = Instant.parse("2026-01-01T00:00:00Z");
    private static final String AUTH = "Basic ZGV2LTE6c2VjcmV0";

    @Autowired
    private WebTestClient client;
    @MockBean
    private IngestPacketUseCase useCase;
    @MockBean
    private DeviceCredentialAuthenticationManager deviceManager;
    @MockBean
    private ReactiveUserDetailsService users;
    @MockBean
    private AuditTrail auditTrail;
    @MockBean
    private TelemetryMetrics metrics;

    private void authenticateAsDev1() {
        when(deviceManager.authenticate(any())).thenReturn(Mono.just(
                new UsernamePasswordAuthenticationToken("dev-1", "x", AuthorityUtils.NO_AUTHORITIES)));
    }

    private static IngressPacketRequest request(String deviceId, String metric) {
        return new IngressPacketRequest(deviceId,
                List.of(new IngressPacketRequest.SampleDto(metric, T, 1.0, null)));
    }

    private WebTestClient.ResponseSpec post(IngressPacketRequest body) {
        return client.post().uri("/ingress/packets").header(HttpHeaders.AUTHORIZATION, AUTH)
                .bodyValue(body).exchange();
    }

    @Test
    void ingest_ownDeviceSamples_returns202() {
        authenticateAsDev1();
        when(useCase.ingest(eq("dev-1"), any(Flux.class)))
                .thenReturn(Mono.just(new IngestSummary(1, 0, 0, 0, false)));

        post(request("dev-1", "temp")).expectStatus().isAccepted()
                .expectBody().jsonPath("$.appended").isEqualTo(1);
    }

    @Test
    void ingest_noCredential_returns401() {
        client.post().uri("/ingress/packets").bodyValue(request("dev-1", "temp"))
                .exchange().expectStatus().isUnauthorized();

        verifyNoInteractions(useCase);
    }

    @Test
    void ingest_refusedSummary_returns403() {
        authenticateAsDev1();
        when(useCase.ingest(eq("dev-1"), any(Flux.class)))
                .thenReturn(Mono.just(new IngestSummary(0, 0, 0, 0, true)));

        post(request("dev-2", "temp")).expectStatus().isForbidden();
    }

    @Test
    void ingest_blankMetric_returns400WithoutEcho() {
        authenticateAsDev1();

        post(request("dev-1", "   ")).expectStatus().isBadRequest()
                .expectBody(String.class).value(b -> org.assertj.core.api.Assertions.assertThat(b)
                        .doesNotContain("dev-1"));
        verify(useCase, never()).ingest(any(), any());
    }

    @Test
    void ingest_emptySamples_returns400() {
        authenticateAsDev1();

        post(new IngressPacketRequest("dev-1", Collections.emptyList())).expectStatus().isBadRequest();
        verify(useCase, never()).ingest(any(), any());
    }

    @Test
    void ingest_oversizedPacket_returns400() {
        authenticateAsDev1();
        List<IngressPacketRequest.SampleDto> many = IntStream.range(0, 501)
                .mapToObj(i -> new IngressPacketRequest.SampleDto("temp", T, 1.0, null))
                .collect(Collectors.toList());

        post(new IngressPacketRequest("dev-1", many)).expectStatus().isBadRequest();
        verify(useCase, never()).ingest(any(), any());
    }
}
