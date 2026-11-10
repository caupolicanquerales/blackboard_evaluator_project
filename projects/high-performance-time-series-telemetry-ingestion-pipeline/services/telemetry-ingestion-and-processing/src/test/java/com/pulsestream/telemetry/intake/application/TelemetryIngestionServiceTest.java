package com.pulsestream.telemetry.intake.application;
import com.pulsestream.telemetry.shared.event.TelemetryEventBus;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.IngressPacket;
import com.pulsestream.telemetry.intake.domain.ReorderWindow;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.shared.config.TelemetryProperties.LatePacketPolicy;
import com.pulsestream.telemetry.shared.config.TelemetryProperties.OverflowStrategy;
import com.pulsestream.telemetry.shared.event.TelemetryEvent;
import com.pulsestream.telemetry.shared.event.TelemetryEvent.TelemetryBackfillReordered;
import com.pulsestream.telemetry.shared.event.TelemetryEvent.TelemetrySampleValidated;
import com.pulsestream.telemetry.shared.event.TelemetryEvent.TelemetryWindowBuffered;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class TelemetryIngestionServiceTest {

    private static final Instant NOW = Instant.parse("2026-01-01T00:00:00Z");
    private static final Duration WINDOW = Duration.ofSeconds(60);
    private static final String DEVICE = "device-1";

    private SensorMetricBoundaryProvider boundaries;
    private TelemetryEventBus bus;
    private Clock clock;

    @BeforeEach
    void setUp() {
        boundaries = mock(SensorMetricBoundaryProvider.class);
        bus = mock(TelemetryEventBus.class);
        clock = Clock.fixed(NOW, ZoneOffset.UTC);
        when(boundaries.boundaryFor(any())).thenReturn(Optional.empty());
        when(bus.publish(any())).thenReturn(Mono.empty());
    }

    private TelemetryIngestionService service(ReorderWindow window, LatePacketPolicy policy) {
        TelemetryProperties props = new TelemetryProperties(Map.of(), WINDOW, Duration.ofSeconds(1), 16,
                OverflowStrategy.REJECT, policy, 3, Duration.ofMillis(10), 8);
        return new TelemetryIngestionService(boundaries, bus, window, props, clock);
    }

    private static IngressPacket.RawSample raw(long secondsFromNow) {
        return new IngressPacket.RawSample(TelemetrySample.MetricType.HEART_RATE, 100.0,
                NOW.plusSeconds(secondsFromNow));
    }

    private static IngressPacket packet(IngressPacket.RawSample... samples) {
        return new IngressPacket(DEVICE, NOW, List.of(samples));
    }

    private List<TelemetryEvent> publishedEvents(int expected) {
        ArgumentCaptor<TelemetryEvent> captor = ArgumentCaptor.forClass(TelemetryEvent.class);
        verify(bus, times(expected)).publish(captor.capture());
        return captor.getAllValues();
    }

    @Test
    void ingest_validSamplesInOrder_emitsCountAndPublishesValidatedEvents() {
        var service = service(new ReorderWindow(WINDOW), LatePacketPolicy.APPEND_REVISION);

        StepVerifier.create(service.ingest(packet(raw(-30), raw(-20)))).expectNext(2L).verifyComplete();

        List<TelemetryEvent> events = publishedEvents(2);
        assertThat(events).allMatch(e -> e instanceof TelemetrySampleValidated);
        assertThat(events).extracting(e -> ((TelemetrySampleValidated) e).sample().deviceTimestamp())
                .containsExactly(NOW.minusSeconds(30), NOW.minusSeconds(20));
    }

    @Test
    void ingest_outOfOrderSample_publishesBackfillReordered() {
        var service = service(new ReorderWindow(WINDOW), LatePacketPolicy.APPEND_REVISION);

        StepVerifier.create(service.ingest(packet(raw(-10), raw(-30)))).expectNext(2L).verifyComplete();

        List<TelemetryEvent> events = publishedEvents(3);
        assertThat(events.get(2)).isInstanceOf(TelemetryBackfillReordered.class);
        assertThat(((TelemetryBackfillReordered) events.get(2)).sample().deviceTimestamp())
                .isEqualTo(NOW.minusSeconds(30));
    }

    @Test
    void ingest_lateSampleWithAppendRevision_publishesBackfillReordered() {
        var window = releasedWindowAt(-120);
        var service = service(window, LatePacketPolicy.APPEND_REVISION);

        StepVerifier.create(service.ingest(packet(raw(-200)))).expectNext(1L).verifyComplete();

        assertThat(publishedEvents(2).get(1)).isInstanceOf(TelemetryBackfillReordered.class);
    }

    @Test
    void ingest_lateSampleWithRejectFromWindow_publishesOnlyValidation() {
        var window = releasedWindowAt(-120);
        var service = service(window, LatePacketPolicy.REJECT_FROM_WINDOW);

        StepVerifier.create(service.ingest(packet(raw(-200)))).expectNext(1L).verifyComplete();

        assertThat(publishedEvents(1).get(0)).isInstanceOf(TelemetrySampleValidated.class);
    }

    @Test
    void ingest_publishFails_propagatesError() {
        when(bus.publish(any())).thenReturn(Mono.error(new IllegalStateException("overflow")));
        var service = service(new ReorderWindow(WINDOW), LatePacketPolicy.APPEND_REVISION);

        StepVerifier.create(service.ingest(packet(raw(-30))))
                .expectError(IllegalStateException.class).verify();
    }

    @Test
    void flushReleasable_nothingReleasable_publishesNothing() {
        var service = service(new ReorderWindow(WINDOW), LatePacketPolicy.APPEND_REVISION);

        StepVerifier.create(service.flushReleasable()).verifyComplete();

        verify(bus, never()).publish(any());
    }

    @Test
    void flushReleasable_releasableSamples_publishesWindowBufferedWithBounds() {
        var service = service(new ReorderWindow(WINDOW), LatePacketPolicy.APPEND_REVISION);
        StepVerifier.create(service.ingest(packet(raw(-200), raw(-100)))).expectNext(2L).verifyComplete();
        org.mockito.Mockito.clearInvocations(bus);

        StepVerifier.create(service.flushReleasable()).verifyComplete();

        TelemetryWindowBuffered event = (TelemetryWindowBuffered) publishedEvents(1).get(0);
        assertThat(event.samples()).hasSize(2);
        assertThat(event.windowStart()).isEqualTo(NOW.minusSeconds(200));
        assertThat(event.windowEnd()).isEqualTo(NOW.minusSeconds(100));
        assertThat(event.occurredAt()).isEqualTo(NOW);
    }

    private ReorderWindow releasedWindowAt(long secondsFromNow) {
        var window = new ReorderWindow(WINDOW);
        window.offer(packet(raw(secondsFromNow)).toSamples().get(0));
        assertThat(window.drainReleasable(NOW)).hasSize(1);
        return window;
    }
}
