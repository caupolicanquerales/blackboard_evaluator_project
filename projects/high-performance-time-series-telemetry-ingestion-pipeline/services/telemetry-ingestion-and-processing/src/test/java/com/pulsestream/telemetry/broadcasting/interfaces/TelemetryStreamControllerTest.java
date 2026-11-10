package com.pulsestream.telemetry.broadcasting.interfaces;
import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.broadcasting.application.port.in.BroadcastTelemetryUseCase;
import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import java.lang.reflect.Method;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class TelemetryStreamControllerTest {

    @Mock
    private BroadcastTelemetryUseCase useCase;

    @Test
    void stream_withDeviceId_delegatesToUseCaseWithSameDeviceId() {
        when(useCase.stream("dev-1")).thenReturn(Flux.<BroadcastItem>empty());
        TelemetryStreamController controller = new TelemetryStreamController(useCase);

        StepVerifier.create(controller.stream("dev-1")).verifyComplete();

        verify(useCase).stream("dev-1");
    }

    @Test
    void stream_withoutDeviceId_requestsAllDevicesWithNull() {
        when(useCase.stream(null)).thenReturn(Flux.<BroadcastItem>empty());
        TelemetryStreamController controller = new TelemetryStreamController(useCase);

        StepVerifier.create(controller.stream(null)).verifyComplete();

        verify(useCase).stream(null);
    }

    @Test
    void stream_useCaseErrors_propagatesErrorToSubscriber() {
        when(useCase.stream("dev-1")).thenReturn(Flux.<BroadcastItem>error(new IllegalStateException("boom")));
        TelemetryStreamController controller = new TelemetryStreamController(useCase);

        StepVerifier.create(controller.stream("dev-1"))
                .expectErrorMessage("boom")
                .verify();
    }

    @Test
    void stream_noDemand_doesNotSubscribeEagerlyOrEmit() {
        when(useCase.stream("dev-1")).thenReturn(Flux.<BroadcastItem>never());
        TelemetryStreamController controller = new TelemetryStreamController(useCase);

        StepVerifier.create(controller.stream("dev-1"), 0)
                .expectSubscription()
                .expectNoEvent(java.time.Duration.ofMillis(10))
                .thenCancel()
                .verify();
    }

    @Test
    void stream_endpointMapping_isGetEventStreamOnTelemetryStreamPath() throws Exception {
        Method method = TelemetryStreamController.class.getMethod("stream", String.class);

        GetMapping mapping = method.getAnnotation(GetMapping.class);

        assertThat(TelemetryStreamController.class.isAnnotationPresent(RestController.class)).isTrue();
        assertThat(mapping).isNotNull();
        assertThat(mapping.produces()).containsExactly(MediaType.TEXT_EVENT_STREAM_VALUE);
        assertThat(pathOf(TelemetryStreamController.class, mapping)).isEqualTo("/api/v1/telemetry/stream");
    }

    private static String pathOf(Class<?> type, GetMapping mapping) {
        RequestMapping base = type.getAnnotation(RequestMapping.class);
        String prefix = base == null || base.value().length == 0 ? "" : base.value()[0];
        String[] paths = mapping.value().length > 0 ? mapping.value() : mapping.path();
        return prefix + (paths.length == 0 ? "" : paths[0]);
    }
}
