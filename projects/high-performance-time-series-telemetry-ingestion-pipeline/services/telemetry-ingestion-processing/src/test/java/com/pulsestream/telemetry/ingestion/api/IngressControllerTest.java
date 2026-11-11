package com.pulsestream.telemetry.ingestion.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ingestion.application.IngestSamplesUseCase;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.webflux.test.autoconfigure.WebFluxTest;
import org.springframework.context.annotation.Bean;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Flux;

@WebFluxTest(IngressController.class)
class IngressControllerTest {

    private static final String URI = "/api/v1/telemetry/packets";

    @TestConfiguration
    static class ClockConfig {
        @Bean
        Clock clock() {
            return Clock.fixed(Instant.ofEpochMilli(5_000L), ZoneOffset.UTC);
        }
    }

    @Autowired
    private WebTestClient client;

    @MockitoBean
    private IngestSamplesUseCase useCase;

    @Test
    void receivePacket_validArray_returns202WithAcceptedCount() {
        TelemetrySample s = new TelemetrySample("d1", "temp", 1L, 1.0, 5_000L, TelemetrySample.VALID);
        when(useCase.ingest(any())).thenReturn(Flux.just(s, s));

        client.post().uri(URI).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(List.of(new IngressSampleDto("d1", "temp", 1L, 1.0),
                        new IngressSampleDto("d1", "temp", 2L, 2.0)))
                .exchange()
                .expectStatus().isAccepted()
                .expectBody(Long.class).isEqualTo(2L);
    }

    @Test
    void receivePacket_validationFailedSample_stillCountsAsAccepted() {
        TelemetrySample failed = new TelemetrySample("d1", "temp", 1L, 1.0, 5_000L, TelemetrySample.VALIDATION_FAILED);
        when(useCase.ingest(any())).thenReturn(Flux.just(failed));

        client.post().uri(URI).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(List.of(new IngressSampleDto("d1", "temp", 1L, 1.0)))
                .exchange()
                .expectStatus().isAccepted()
                .expectBody(Long.class).isEqualTo(1L);
    }

    @Test
    void receivePacket_blankDeviceId_returns400() {
        when(useCase.ingest(any())).thenReturn(Flux.empty());

        client.post().uri(URI).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(List.of(new IngressSampleDto(" ", "temp", 1L, 1.0)))
                .exchange()
                .expectStatus().isBadRequest();
    }
}
