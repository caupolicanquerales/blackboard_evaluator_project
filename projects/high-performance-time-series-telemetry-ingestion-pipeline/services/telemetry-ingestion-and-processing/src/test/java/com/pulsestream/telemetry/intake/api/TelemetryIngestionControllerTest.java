package com.pulsestream.telemetry.intake.api;
import com.pulsestream.telemetry.shared.event.TelemetryEvent;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.api.TelemetryIngestionController.IngestionResponse;
import com.pulsestream.telemetry.intake.api.TelemetryIngestionController.IngressPacketRequest;
import com.pulsestream.telemetry.intake.api.TelemetryIngestionController.SampleRequest;
import com.pulsestream.telemetry.intake.application.TelemetryIngestionService;
import com.pulsestream.telemetry.intake.application.TelemetryStreamService;
import com.pulsestream.telemetry.intake.domain.IngressPacket;
import com.pulsestream.telemetry.intake.domain.TelemetrySample.MetricType;
import com.pulsestream.telemetry.shared.event.TelemetryEvent.TelemetryWindowBuffered;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class TelemetryIngestionControllerTest {

    private static final Instant NOW = Instant.parse("2025-01-01T10:00:00Z");
    private static final Instant DEVICE_TS = Instant.parse("2025-01-01T09:59:59Z");

    @Mock
    private TelemetryIngestionService ingestionService;
    @Mock
    private TelemetryStreamService streamService;

    private TelemetryIngestionController controller;

    @BeforeEach
    void setUp() {
        controller = new TelemetryIngestionController(
                ingestionService, streamService, Clock.fixed(NOW, ZoneOffset.UTC));
    }

    private static IngressPacketRequest validRequest() {
        return new IngressPacketRequest("dev-1",
                List.of(new SampleRequest(MetricType.HEART_RATE, 61.5, DEVICE_TS)));
    }

    private static Validator validator() {
        return Validation.buildDefaultValidatorFactory().getValidator();
    }

    @Test
    void ingest_validRequest_returns202WithAcceptedCount() {
        when(ingestionService.ingest(any(IngressPacket.class))).thenReturn(Mono.just(1L));

        StepVerifier.create(controller.ingest(validRequest()))
                .assertNext(response -> {
                    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
                    assertThat(response.getBody()).isNotNull();
                    assertThat(response.getBody().accepted()).isEqualTo(1L);
                })
                .verifyComplete();
    }

    @Test
    void ingest_validRequest_stampsIngressTimestampFromClock() {
        when(ingestionService.ingest(any(IngressPacket.class))).thenReturn(Mono.just(1L));

        StepVerifier.create(controller.ingest(validRequest())).expectNextCount(1).verifyComplete();

        ArgumentCaptor<IngressPacket> captor = ArgumentCaptor.forClass(IngressPacket.class);
        verify(ingestionService).ingest(captor.capture());
        assertThat(captor.getValue().ingressTimestamp()).isEqualTo(NOW);
        assertThat(captor.getValue().deviceId()).isEqualTo("dev-1");
    }

    @Test
    void ingest_serviceOverflow_propagatesIllegalStateException() {
        when(ingestionService.ingest(any(IngressPacket.class)))
                .thenReturn(Mono.error(new IllegalStateException("overflow")));

        StepVerifier.create(controller.ingest(validRequest()))
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void toDomain_validRequest_mapsSamplesAndIngressTimestamp() {
        IngressPacket packet = validRequest().toDomain(NOW);

        assertThat(packet.deviceId()).isEqualTo("dev-1");
        assertThat(packet.ingressTimestamp()).isEqualTo(NOW);
        assertThat(packet.samples()).hasSize(1);
        assertThat(packet.samples().get(0).metricType()).isEqualTo(MetricType.HEART_RATE);
        assertThat(packet.samples().get(0).value()).isEqualTo(61.5);
        assertThat(packet.samples().get(0).deviceTimestamp()).isEqualTo(DEVICE_TS);
    }

    @Test
    void validation_blankDeviceId_isRejected() {
        IngressPacketRequest request = new IngressPacketRequest(" ",
                List.of(new SampleRequest(MetricType.POWER, 200.0, DEVICE_TS)));

        assertThat(validator().validate(request)).isNotEmpty();
    }

    @Test
    void validation_emptySamples_isRejected() {
        IngressPacketRequest request = new IngressPacketRequest("dev-1", List.of());

        assertThat(validator().validate(request)).isNotEmpty();
    }

    @Test
    void validation_nullSampleFields_areRejected() {
        IngressPacketRequest request = new IngressPacketRequest("dev-1",
                List.of(new SampleRequest(null, null, null)));

        List<ConstraintViolation<IngressPacketRequest>> violations =
                List.copyOf(validator().validate(request));

        assertThat(violations).hasSizeGreaterThanOrEqualTo(3);
    }

    @Test
    void validation_validRequest_hasNoViolations() {
        assertThat(validator().validate(validRequest())).isEmpty();
    }

    @Test
    void streamWindows_serviceEmitsWindows_relaysThem() {
        TelemetryWindowBuffered window =
                new TelemetryWindowBuffered(List.of(), DEVICE_TS, NOW, NOW);
        when(streamService.windows()).thenReturn(Flux.just(window));

        StepVerifier.create(controller.streamWindows())
                .expectNext(window)
                .verifyComplete();
    }
}
