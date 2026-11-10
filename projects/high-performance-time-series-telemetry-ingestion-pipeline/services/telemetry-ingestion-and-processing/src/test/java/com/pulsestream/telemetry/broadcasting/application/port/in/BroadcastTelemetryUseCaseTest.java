package com.pulsestream.telemetry.broadcasting.application.port.in;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;
import java.time.Instant;
import java.util.List;
import java.util.Objects;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;
import reactor.test.StepVerifier;

class BroadcastTelemetryUseCaseTest {

    private static final Instant START = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant END = Instant.parse("2024-01-01T00:00:10Z");

    private BroadcastTelemetryUseCase useCase;

    @BeforeEach
    void setUp() {
        useCase = new InMemoryBroadcast();
    }

    @Test
    void stream_nullDeviceId_receivesSamplesOfAllDevices() {
        TelemetrySampleEvent a = sample("device-1");
        TelemetrySampleEvent b = sample("device-2");

        StepVerifier.create(useCase.stream(null).take(2))
                .then(() -> {
                    useCase.broadcastSample(a).block();
                    useCase.broadcastSample(b).block();
                })
                .expectNext(BroadcastItem.sample(a), BroadcastItem.sample(b))
                .verifyComplete();
    }

    @Test
    void stream_withDeviceId_receivesOnlyThatDevice() {
        TelemetrySampleEvent other = sample("device-2");
        TelemetrySampleEvent mine = sample("device-1");

        StepVerifier.create(useCase.stream("device-1").take(1))
                .then(() -> {
                    useCase.broadcastSample(other).block();
                    useCase.broadcastSample(mine).block();
                })
                .expectNext(BroadcastItem.sample(mine))
                .verifyComplete();
    }

    @Test
    void broadcastWindow_closedWindow_emitsWindowItemToSubscriber() {
        TelemetryWindowClosedEvent window =
                new TelemetryWindowClosedEvent("device-1", START, END, List.of(sample("device-1")));

        StepVerifier.create(useCase.stream("device-1").take(1))
                .then(() -> useCase.broadcastWindow(window).block())
                .assertNext(item -> {
                    assertThat(item.kind()).isEqualTo(BroadcastItem.Kind.WINDOW);
                    assertThat(item.deviceId()).isEqualTo("device-1");
                    assertThat(item.samples()).containsExactlyElementsOf(window.samples());
                })
                .verifyComplete();
    }

    @Test
    void broadcastSample_noSubscribers_completesEmpty() {
        StepVerifier.create(useCase.broadcastSample(sample("device-1"))).verifyComplete();
    }

    @Test
    void broadcastSample_nullSample_errors() {
        StepVerifier.create(useCase.broadcastSample(null)).expectError(RuntimeException.class).verify();
    }

    @Test
    void broadcastWindow_nullWindow_errors() {
        StepVerifier.create(useCase.broadcastWindow(null)).expectError(RuntimeException.class).verify();
    }

    private static TelemetrySampleEvent sample(String deviceId) {
        return new TelemetrySampleEvent(
                deviceId, "temp", 21.5, START, END, TelemetrySampleEvent.VALID);
    }

    private static final class InMemoryBroadcast implements BroadcastTelemetryUseCase {
        private final Sinks.Many<BroadcastItem> sink = Sinks.many().multicast().directBestEffort();

        @Override
        public Mono<Void> broadcastSample(TelemetrySampleEvent sample) {
            return Mono.fromRunnable(() -> sink.tryEmitNext(BroadcastItem.sample(Objects.requireNonNull(sample))));
        }

        @Override
        public Mono<Void> broadcastWindow(TelemetryWindowClosedEvent window) {
            return Mono.fromRunnable(() -> sink.tryEmitNext(BroadcastItem.window(Objects.requireNonNull(window))));
        }

        @Override
        public Flux<BroadcastItem> stream(String deviceId) {
            return sink.asFlux().filter(i -> deviceId == null || deviceId.equals(i.deviceId()));
        }
    }
}
