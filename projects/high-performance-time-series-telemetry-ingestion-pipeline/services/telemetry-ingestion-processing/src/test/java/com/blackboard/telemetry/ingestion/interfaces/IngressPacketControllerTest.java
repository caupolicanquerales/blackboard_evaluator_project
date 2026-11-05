package com.blackboard.telemetry.ingestion.interfaces;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;

import com.blackboard.telemetry.ingestion.application.IngestTelemetryService;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;

import reactor.core.publisher.Flux;

@ExtendWith(MockitoExtension.class)
class IngressPacketControllerTest {

    private static final String DEVICE = "device-1";
    private static final String T_DEVICE = "2026-01-01T10:00:00Z";

    @Mock
    private IngestTelemetryService ingestService;

    private WebTestClient client;

    @BeforeEach
    void setUp() {
        client = WebTestClient.bindToController(new IngressPacketController(ingestService)).build();
    }

    private WebTestClient.ResponseSpec post(String body) {
        return client.post().uri("/ingress")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .exchange();
    }

    private static String packet(String deviceId, String tDevice, String samples) {
        StringBuilder json = new StringBuilder("{");
        if (deviceId != null) {
            json.append("\"deviceId\":\"").append(deviceId).append("\",");
        }
        if (tDevice != null) {
            json.append("\"t_device\":\"").append(tDevice).append("\",");
        }
        return json.append("\"samples\":").append(samples).append("}").toString();
    }

    private List<TelemetrySample> captureIngestedSamples() {
        @SuppressWarnings("unchecked")
        ArgumentCaptor<Flux<TelemetrySample>> captor = ArgumentCaptor.forClass(Flux.class);
        verify(ingestService).ingest(captor.capture());
        return captor.getValue().collectList().block();
    }

    @Test
    void ingress_validPacket_returns202Accepted() {
        when(ingestService.ingest(any())).thenReturn(Flux.empty());

        post(packet(DEVICE, T_DEVICE, "[{\"metric\":\"heart_rate\",\"value\":150.0}]"))
                .expectStatus().isAccepted();
    }

    @Test
    void ingress_validPacket_translatesEachEntryIntoTelemetrySample() {
        when(ingestService.ingest(any())).thenReturn(Flux.empty());

        post(packet(DEVICE, T_DEVICE,
                "[{\"metric\":\"heart_rate\",\"value\":150.0},{\"metric\":\"power\",\"value\":240}]"))
                .expectStatus().isAccepted();

        assertThat(captureIngestedSamples()).containsExactly(
                new TelemetrySample(DEVICE, Instant.parse(T_DEVICE), "heart_rate", 150.0),
                new TelemetrySample(DEVICE, Instant.parse(T_DEVICE), "power", 240.0));
    }

    @Test
    void ingress_outOfPhysicalRangeValue_isNotRejectedAndIsForwarded() {
        when(ingestService.ingest(any())).thenReturn(Flux.empty());

        post(packet(DEVICE, T_DEVICE, "[{\"metric\":\"heart_rate\",\"value\":9999.0}]"))
                .expectStatus().isAccepted();

        assertThat(captureIngestedSamples()).containsExactly(
                new TelemetrySample(DEVICE, Instant.parse(T_DEVICE), "heart_rate", 9999.0));
    }

    @Test
    void ingress_missingDeviceId_returns400AndDoesNotIngest() {
        post(packet(null, T_DEVICE, "[{\"metric\":\"heart_rate\",\"value\":150.0}]"))
                .expectStatus().isBadRequest();

        verify(ingestService, never()).ingest(any());
    }

    @Test
    void ingress_missingTDevice_returns400AndDoesNotIngest() {
        post(packet(DEVICE, null, "[{\"metric\":\"heart_rate\",\"value\":150.0}]"))
                .expectStatus().isBadRequest();

        verify(ingestService, never()).ingest(any());
    }

    @ParameterizedTest
    @ValueSource(strings = {"\"abc\"", "{}", "[1]", "true"})
    void ingress_nonNumericValue_returns400AndDoesNotIngest(String badValue) {
        post(packet(DEVICE, T_DEVICE, "[{\"metric\":\"heart_rate\",\"value\":" + badValue + "}]"))
                .expectStatus().isBadRequest();

        verify(ingestService, never()).ingest(any());
    }

    @Test
    void ingress_malformedJson_returns400AndDoesNotIngest() {
        post("{not-json").expectStatus().isBadRequest();

        verify(ingestService, never()).ingest(any());
    }
}
