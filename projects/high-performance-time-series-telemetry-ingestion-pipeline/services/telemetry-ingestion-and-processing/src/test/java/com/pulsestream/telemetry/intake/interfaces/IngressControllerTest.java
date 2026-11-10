package com.pulsestream.telemetry.intake.interfaces;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.application.port.in.IngestTelemetryUseCase;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Mono;

@ExtendWith(MockitoExtension.class)
class IngressControllerTest {

    private static final String URI = "/api/v1/telemetry/packets";
    private static final Instant NOW = Instant.parse("2025-01-01T00:00:00Z");

    @Mock
    private IngestTelemetryUseCase useCase;

    private WebTestClient client;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(NOW, ZoneOffset.UTC);
        client = WebTestClient.bindToController(new IngressController(useCase, clock)).build();
    }

    private WebTestClient.RequestHeadersSpec<?> post(String body) {
        return client.post().uri(URI).contentType(MediaType.APPLICATION_JSON).bodyValue(body);
    }

    private static String validBody() {
        return """
            {"deviceId":"dev-1","samples":[
              {"metric":"temp","value":21.5,"tDevice":"2024-12-31T23:59:59Z"},
              {"metric":"hum","value":40.0,"tDevice":"2024-12-31T23:59:58Z"}]}
            """;
    }

    @Test
    void ingest_validPacket_returns202WithAcknowledgement() {
        when(useCase.ingest(any())).thenReturn(Mono.just(2));

        post(validBody()).exchange()
            .expectStatus().isAccepted()
            .expectBody(IngressController.IngressAcknowledgement.class)
            .isEqualTo(new IngressController.IngressAcknowledgement("dev-1", 2));
    }

    @Test
    void ingest_validPacket_delegatesToUseCaseOnce() {
        when(useCase.ingest(any())).thenReturn(Mono.just(2));

        post(validBody()).exchange().expectStatus().isAccepted();

        verify(useCase).ingest(any());
    }

    @Test
    void ingest_useCaseAcceptsZero_acknowledgesZero() {
        when(useCase.ingest(any())).thenReturn(Mono.just(0));

        post(validBody()).exchange()
            .expectStatus().isAccepted()
            .expectBody(IngressController.IngressAcknowledgement.class)
            .isEqualTo(new IngressController.IngressAcknowledgement("dev-1", 0));
    }

    @Test
    void ingest_channelOverflow_returns503() {
        when(useCase.ingest(any()))
            .thenReturn(Mono.error(new BoundedEventChannel.OverflowException("intake")));

        post(validBody()).exchange().expectStatus().isEqualTo(503);
    }

    @Test
    void ingest_blankDeviceId_returns400WithoutCallingUseCase() {
        post("""
            {"deviceId":" ","samples":[{"metric":"temp","value":1.0,"tDevice":"2024-12-31T23:59:59Z"}]}
            """).exchange().expectStatus().isBadRequest();

        verify(useCase, never()).ingest(any());
    }

    @Test
    void ingest_emptySamples_returns400WithoutCallingUseCase() {
        post("{\"deviceId\":\"dev-1\",\"samples\":[]}")
            .exchange().expectStatus().isBadRequest();

        verify(useCase, never()).ingest(any());
    }

    @Test
    void ingest_invalidSample_returns400WithoutCallingUseCase() {
        post("""
            {"deviceId":"dev-1","samples":[{"metric":"","value":null,"tDevice":null}]}
            """).exchange().expectStatus().isBadRequest();

        verify(useCase, never()).ingest(any());
    }

    @Test
    void ingest_malformedJson_returns400() {
        post("{not-json").exchange().expectStatus().isBadRequest();
    }
}
