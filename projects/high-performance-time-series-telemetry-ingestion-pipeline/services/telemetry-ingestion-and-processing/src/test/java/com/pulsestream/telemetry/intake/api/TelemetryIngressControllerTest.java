package com.pulsestream.telemetry.intake.api;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.intake.application.IntakeTelemetryUseCase;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.Mockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.webflux.test.autoconfigure.WebFluxTest;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Mono;

@WebFluxTest(TelemetryIngressController.class)
@Import(TelemetryIngressControllerTest.UseCaseDouble.class)
class TelemetryIngressControllerTest {

    private static final String URI = "/telemetry/samples";
    private static final String VALID_PAYLOAD = """
            {"deviceId":"device-1","metric":"temperature","value":21.5,"timestamp":"2025-01-01T00:00:00Z"}
            """;

    @TestConfiguration
    static class UseCaseDouble {
        @Bean
        IntakeTelemetryUseCase intakeTelemetryUseCase() {
            return Mockito.mock(IntakeTelemetryUseCase.class, invocation -> Mono.empty());
        }
    }

    @Autowired
    private WebTestClient client;

    @Autowired
    private IntakeTelemetryUseCase useCase;

    private WebTestClient.ResponseSpec post(String body) {
        return client.post().uri(URI)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .exchange();
    }

    @Test
    void postSamples_wellFormedPayload_returnsAccepted() {
        Mockito.clearInvocations(useCase);

        post(VALID_PAYLOAD).expectStatus().isAccepted();
    }

    @Test
    void postSamples_wellFormedPayload_returnsEmptyBody() {
        post(VALID_PAYLOAD).expectBody().isEmpty();
    }

    @Test
    void postSamples_wellFormedPayload_delegatesOnceToUseCase() {
        Mockito.clearInvocations(useCase);

        post(VALID_PAYLOAD).expectStatus().isAccepted();

        assertThat(Mockito.mockingDetails(useCase).getInvocations()).hasSize(1);
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "{not-json",
            "{}",
            "{\"metric\":\"temperature\",\"value\":21.5,\"timestamp\":\"2025-01-01T00:00:00Z\"}",
            "{\"deviceId\":\"device-1\",\"value\":21.5,\"timestamp\":\"2025-01-01T00:00:00Z\"}",
            "{\"deviceId\":\"device-1\",\"metric\":\"temperature\",\"value\":\"abc\",\"timestamp\":\"2025-01-01T00:00:00Z\"}",
            "{\"deviceId\":\"\",\"metric\":\"temperature\",\"value\":21.5,\"timestamp\":\"2025-01-01T00:00:00Z\"}"
    })
    void postSamples_malformedOrMissingFields_returnsBadRequest(String body) {
        post(body).expectStatus().isBadRequest();
    }

    @Test
    void postSamples_malformedPayload_doesNotInvokeUseCase() {
        Mockito.clearInvocations(useCase);

        post("{not-json").expectStatus().isBadRequest();

        assertThat(Mockito.mockingDetails(useCase).getInvocations()).isEmpty();
    }
}
