package com.pulsestream.telemetry.eventlog.api;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.eventlog.application.EventLogService;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Flux;

class EventLogControllerTest {

    private EventLogService service;
    private WebTestClient client;

    @BeforeEach
    void setUp() {
        service = mock(EventLogService.class);
        client = WebTestClient.bindToController(new EventLogController(service)).build();
    }

    @Test
    void records_validQuery_returns200WithJsonArray() {
        TelemetrySample sample = new TelemetrySample("dev-1", "temp", 1000L, 21.5, 2000L, TelemetrySample.VALID);
        when(service.query("dev-1", 0L, 5000L)).thenReturn(Flux.just(sample));

        client.get()
                .uri("/api/v1/telemetry/records?deviceId=dev-1&from=0&to=5000")
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.length()").isEqualTo(1)
                .jsonPath("$[0].deviceId").isEqualTo("dev-1")
                .jsonPath("$[0].metric").isEqualTo("temp");
    }

    @Test
    void records_missingDeviceId_returns400() {
        client.get()
                .uri("/api/v1/telemetry/records?from=0&to=5000")
                .exchange()
                .expectStatus().isBadRequest();
    }
}
