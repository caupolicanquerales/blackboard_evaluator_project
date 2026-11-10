package com.pulsestream.telemetry.intake.application.port.in;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.application.IngressPacket;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.intake.domain.ValidationStatus;
import java.lang.reflect.Method;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class IngestTelemetryUseCaseTest {

    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:00Z");

    private static TelemetrySample sample(String deviceId) {
        return new TelemetrySample(deviceId, "cpu", 1.0, T_INGRESS, T_INGRESS,
                ValidationStatus.VALIDATION_FAILED);
    }

    private static IngressPacket packet(int size) {
        List<TelemetrySample> samples = java.util.stream.IntStream.range(0, size)
                .mapToObj(i -> sample("dev-1")).toList();
        return new IngressPacket("dev-1", T_INGRESS, samples);
    }

    @Test
    void ingest_declaredSignature_returnsMonoOfIntegerTakingIngressPacket() throws Exception {
        Method method = IngestTelemetryUseCase.class.getMethod("ingest", IngressPacket.class);

        assertThat(method.getReturnType()).isEqualTo(Mono.class);
        assertThat(method.getGenericReturnType().getTypeName())
                .isEqualTo("reactor.core.publisher.Mono<java.lang.Integer>");
    }

    @Test
    void ingest_packetWithSamples_emitsAcceptedCount() {
        IngestTelemetryUseCase useCase = mock(IngestTelemetryUseCase.class);
        IngressPacket packet = packet(3);
        when(useCase.ingest(packet)).thenReturn(Mono.just(3));

        StepVerifier.create(useCase.ingest(packet)).expectNext(3).verifyComplete();
        verify(useCase).ingest(packet);
    }

    @Test
    void ingest_validationFailedSamples_areCountedAsAccepted() {
        IngestTelemetryUseCase useCase = packet -> Mono.just(packet.samples().size());
        IngressPacket packet = packet(2);

        StepVerifier.create(useCase.ingest(packet)).expectNext(2).verifyComplete();
    }

    @Test
    void ingest_isLazy_doesNotBlockOrEmitBeforeSubscription() {
        IngestTelemetryUseCase useCase = packet -> Mono.fromSupplier(() -> packet.samples().size());

        Mono<Integer> result = useCase.ingest(packet(1));

        StepVerifier.create(result).expectNext(1).verifyComplete();
    }

    @Test
    void ingest_downstreamFailure_propagatesErrorSignal() {
        IngestTelemetryUseCase useCase = packet -> Mono.error(new IllegalStateException("store down"));

        StepVerifier.create(useCase.ingest(packet(1)))
                .expectErrorSatisfies(e -> assertThat(e).isInstanceOf(IllegalStateException.class)
                        .hasMessage("store down"))
                .verify();
    }
}
