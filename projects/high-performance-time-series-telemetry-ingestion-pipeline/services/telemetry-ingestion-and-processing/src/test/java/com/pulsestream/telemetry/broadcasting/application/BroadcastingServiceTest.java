package com.pulsestream.telemetry.broadcasting.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.broadcasting.application.port.out.TelemetryStreamGateway;
import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryStreamPublishedEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class BroadcastingServiceTest {

    private static final Instant NOW = Instant.parse("2024-01-01T00:00:10Z");

    private TelemetryStreamGateway gateway;
    private BoundedEventChannel<TelemetryStreamPublishedEvent> channel;
    private BroadcastingService service;
    private List<TelemetryStreamPublishedEvent> audits;

    @BeforeEach
    void setUp() {
        gateway = mock(TelemetryStreamGateway.class);
        channel = new BoundedEventChannel<>("stream-publications", 8);
        audits = new ArrayList<>();
        channel.stream().subscribe(audits::add);
        service = new BroadcastingService(gateway, channel, Clock.fixed(NOW, ZoneOffset.UTC));
    }

    private static TelemetrySampleEvent sample(String deviceId) {
        return new TelemetrySampleEvent(deviceId, "temp", 21.5,
                Instant.parse("2024-01-01T00:00:01Z"), Instant.parse("2024-01-01T00:00:02Z"), "VALID");
    }

    private static BroadcastItem item(String deviceId) {
        return new BroadcastItem(BroadcastItem.Kind.SAMPLE, deviceId, List.of(sample(deviceId)));
    }

    @Test
    void broadcastSample_validSample_publishesSampleItemThroughGateway() {
        when(gateway.publish(any())).thenReturn(Mono.empty());

        StepVerifier.create(service.broadcastSample(sample("dev-1"))).verifyComplete();

        ArgumentCaptor<BroadcastItem> captor = ArgumentCaptor.forClass(BroadcastItem.class);
        verify(gateway).publish(captor.capture());
        assertThat(captor.getValue().kind()).isEqualTo(BroadcastItem.Kind.SAMPLE);
        assertThat(captor.getValue().deviceId()).isEqualTo("dev-1");
        assertThat(captor.getValue().samples()).containsExactly(sample("dev-1"));
    }

    @Test
    void broadcastSample_validSample_publishesAuditEventWithClockInstant() {
        when(gateway.publish(any())).thenReturn(Mono.empty());

        StepVerifier.create(service.broadcastSample(sample("dev-1"))).verifyComplete();

        assertThat(audits).containsExactly(new TelemetryStreamPublishedEvent("SAMPLE", "dev-1", 1, NOW));
    }

    @Test
    void broadcastSample_auditChannelFails_stillCompletes() {
        when(gateway.publish(any())).thenReturn(Mono.empty());
        BoundedEventChannel<TelemetryStreamPublishedEvent> failing = failingChannel();
        BroadcastingService failingService =
                new BroadcastingService(gateway, failing, Clock.fixed(NOW, ZoneOffset.UTC));

        StepVerifier.create(failingService.broadcastSample(sample("dev-1"))).verifyComplete();

        verify(gateway).publish(any());
    }

    @Test
    void broadcastSample_gatewayFails_propagatesErrorAndSkipsAudit() {
        when(gateway.publish(any())).thenReturn(Mono.error(new IllegalStateException("boom")));

        StepVerifier.create(service.broadcastSample(sample("dev-1")))
                .expectError(IllegalStateException.class)
                .verify();

        assertThat(audits).isEmpty();
    }

    @Test
    void broadcastWindow_closedWindow_publishesWindowItemAndAuditEvent() {
        when(gateway.publish(any())).thenReturn(Mono.empty());
        TelemetryWindowClosedEvent window = mock(TelemetryWindowClosedEvent.class);

        StepVerifier.create(service.broadcastWindow(window)).verifyComplete();

        ArgumentCaptor<BroadcastItem> captor = ArgumentCaptor.forClass(BroadcastItem.class);
        verify(gateway).publish(captor.capture());
        assertThat(captor.getValue().kind()).isEqualTo(BroadcastItem.Kind.WINDOW);
        assertThat(audits).hasSize(1);
        assertThat(audits.get(0).kind()).isEqualTo("WINDOW");
        assertThat(audits.get(0).publishedAt()).isEqualTo(NOW);
    }

    @Test
    void stream_nullDeviceId_emitsAllDevices() {
        when(gateway.items()).thenReturn(Flux.just(item("dev-1"), item("dev-2")));

        StepVerifier.create(service.stream(null))
                .expectNext(item("dev-1"), item("dev-2"))
                .verifyComplete();
    }

    @Test
    void stream_deviceId_emitsOnlyMatchingDevice() {
        when(gateway.items()).thenReturn(Flux.just(item("dev-1"), item("dev-2"), item("dev-1")));

        StepVerifier.create(service.stream("dev-1"))
                .expectNext(item("dev-1"), item("dev-1"))
                .verifyComplete();
    }

    @Test
    void stream_unknownDeviceId_emitsNothing() {
        when(gateway.items()).thenReturn(Flux.just(item("dev-1")));

        StepVerifier.create(service.stream("other")).verifyComplete();

        verify(gateway, never()).publish(any());
    }

    @SuppressWarnings("unchecked")
    private static BoundedEventChannel<TelemetryStreamPublishedEvent> failingChannel() {
        BoundedEventChannel<TelemetryStreamPublishedEvent> failing = mock(BoundedEventChannel.class);
        when(failing.publish(any())).thenReturn(Mono.error(new BoundedEventChannel.OverflowException("x")));
        return failing;
    }
}
