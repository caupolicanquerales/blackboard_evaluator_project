package com.pulsestream.telemetry.distribution.api;

import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.distribution.application.BroadcastService;
import com.pulsestream.telemetry.distribution.domain.TelemetryWindowBroadcast;
import com.pulsestream.telemetry.ingestion.infrastructure.TelemetrySecurityConfiguration;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.WebFluxTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Flux;

@WebFluxTest(WindowBroadcastController.class)
@Import(TelemetrySecurityConfiguration.class)
class WindowBroadcastControllerTest {

    @Autowired
    WebTestClient client;

    @MockitoBean
    BroadcastService service;

    private void stubWindow() {
        Instant t = Instant.parse("2026-01-01T00:00:00Z");
        when(service.subscribe()).thenReturn(Flux.just(new TelemetryWindowBroadcast(t, t.plusSeconds(5), List.of())));
    }

    @Test
    void stream_scopedConsumer_receivesWindow() {
        stubWindow();

        client.get().uri("/telemetry/stream").accept(MediaType.TEXT_EVENT_STREAM)
                .headers(h -> h.setBasicAuth("stream-consumer", "stream-secret"))
                .exchange().expectStatus().isOk()
                .expectBody(String.class).value(b -> org.assertj.core.api.Assertions.assertThat(b)
                        .contains("windowStart"));
    }

    @Test
    void stream_unauthenticated_isRefusedWithoutBody() {
        stubWindow();

        client.get().uri("/telemetry/stream").accept(MediaType.TEXT_EVENT_STREAM)
                .exchange().expectStatus().isUnauthorized()
                .expectBody().isEmpty();
    }

    @Test
    void stream_authenticatedWithoutScope_isRefusedWithoutBody() {
        stubWindow();

        client.get().uri("/telemetry/stream").accept(MediaType.TEXT_EVENT_STREAM)
                .headers(h -> h.setBasicAuth("device-1", "device-secret"))
                .exchange().expectStatus().isForbidden()
                .expectBody().isEmpty();
    }
}
