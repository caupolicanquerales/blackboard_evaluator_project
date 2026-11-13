package com.blackboard.telemetry.ingestion.interface_;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.blackboard.telemetry.ingestion.application.IngestTelemetryUseCase;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@ExtendWith(MockitoExtension.class)
class TelemetryIngestControllerTest {

    private static final String URI = "/api/v1/telemetry/ingress";
    private static final String BODY =
            "{\"deviceId\":\"d1\",\"metric\":\"temp\",\"tDevice\":\"2024-01-01T00:00:00Z\","
                    + "\"tIngress\":\"2024-01-01T00:00:01Z\",\"value\":1.5}\n"
                    + "{\"deviceId\":\"d2\",\"metric\":\"hum\",\"tDevice\":\"2024-01-01T00:00:02Z\","
                    + "\"tIngress\":\"2024-01-01T00:00:03Z\",\"value\":2.5}\n";

    @Mock
    private IngestTelemetryUseCase useCase;

    private WebTestClient client;

    @BeforeEach
    void setUp() {
        client = WebTestClient.bindToController(new TelemetryIngestController(useCase)).build();
    }

    @Test
    void ingest_ndjsonBody_returnsUseCaseCountAsJsonNumber() {
        when(useCase.ingest(any(), any())).thenReturn(Mono.just(2L));

        client.post().uri(URI)
                .contentType(MediaType.parseMediaType("application/x-ndjson"))
                .bodyValue(BODY)
                .exchange()
                .expectStatus().isOk()
                .expectBody(Long.class).isEqualTo(2L);
    }

    @Test
    void ingest_requestIdHeader_passedAsCorrelationId() {
        when(useCase.ingest(any(), any())).thenReturn(Mono.just(2L));

        client.post().uri(URI)
                .contentType(MediaType.parseMediaType("application/x-ndjson"))
                .header("X-Request-Id", "req-123")
                .bodyValue(BODY)
                .exchange()
                .expectStatus().isOk();

        verify(useCase).ingest(any(), eq("req-123"));
    }

    @Test
    void ingest_noRequestIdHeader_passesGeneratedUuid() {
        when(useCase.ingest(any(), any())).thenReturn(Mono.just(2L));

        client.post().uri(URI)
                .contentType(MediaType.parseMediaType("application/x-ndjson"))
                .bodyValue(BODY)
                .exchange()
                .expectStatus().isOk();

        ArgumentCaptor<String> id = ArgumentCaptor.forClass(String.class);
        verify(useCase).ingest(any(), id.capture());
        assertThat(id.getValue()).isNotBlank();
        assertThat(UUID.fromString(id.getValue())).isNotNull();
    }

    @Test
    void ingest_ndjsonBody_streamsOneSamplePerLine() {
        when(useCase.ingest(any(), any())).thenAnswer(inv -> {
            Flux<TelemetrySample> flux = inv.getArgument(0);
            return flux.collectList().map(l -> (long) l.size());
        });

        client.post().uri(URI)
                .contentType(MediaType.parseMediaType("application/x-ndjson"))
                .bodyValue(BODY)
                .exchange()
                .expectStatus().isOk()
                .expectBody(Long.class).isEqualTo(2L);
    }
}
