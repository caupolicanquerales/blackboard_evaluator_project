package com.pulsestream.telemetry.distribution.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.distribution.api.ValidatedEventConsumer;
import com.pulsestream.telemetry.distribution.domain.TelemetryWindowBroadcast;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;
import reactor.test.StepVerifier;

class BroadcastServiceTest {

    private static final Instant T = Instant.parse("2025-01-01T00:00:00Z");

    private final ValidatedEventConsumer buffer = mock(ValidatedEventConsumer.class);
    private final TelemetryEventSource source = mock(TelemetryEventSource.class);
    private final TelemetryMetrics metrics = mock(TelemetryMetrics.class);

    private static TelemetryWindowBroadcast window(int second) {
        return new TelemetryWindowBroadcast(T.plusSeconds(second), T.plusSeconds(second + 1), List.of());
    }

    private void bufferEmits(Flux<TelemetryWindowBroadcast> windows) {
        when(source.events()).thenReturn(Flux.empty());
        when(buffer.buffer(any())).thenReturn(windows);
    }

    @Test
    void subscribe_afterStart_receivesBufferedWindow() {
        TelemetryWindowBroadcast w = window(0);
        bufferEmits(Flux.just(w).concatWith(Flux.never()));
        BroadcastService service = new BroadcastService(buffer, source, metrics, 16);

        StepVerifier.create(service.subscribe())
                .then(service::start)
                .expectNext(w)
                .thenCancel()
                .verify();
        service.stop();
    }

    @Test
    void subscribe_twoSubscribers_bothReceiveWindow() {
        TelemetryWindowBroadcast w = window(0);
        Sinks.One<Boolean> gate = Sinks.one();
        bufferEmits(gate.asMono().thenMany(Flux.just(w)).concatWith(Flux.never()));
        BroadcastService service = new BroadcastService(buffer, source, metrics, 16);
        Flux<TelemetryWindowBroadcast> flux = service.subscribe();
        service.start();

        var first = StepVerifier.create(flux).expectNext(w).thenCancel().verifyLater();
        var second = StepVerifier.create(flux).expectNext(w).thenCancel().verifyLater();
        gate.tryEmitValue(true);

        first.verify();
        second.verify();
        service.stop();
    }

    @Test
    void start_overflowWithoutDemand_countsDrop() {
        bufferEmits(Flux.just(window(0), window(1), window(2), window(3)).concatWith(Flux.never()));
        BroadcastService service = new BroadcastService(buffer, source, metrics, 1);

        StepVerifier.create(service.subscribe(), 0)
                .then(service::start)
                .thenAwait()
                .thenCancel()
                .verify();

        verify(metrics, Mockito.atLeastOnce()).broadcastDropped(anyString());
        service.stop();
    }

    @Test
    void stop_afterStart_disposesUpstreamSubscription() {
        AtomicBoolean cancelled = new AtomicBoolean(false);
        bufferEmits(Flux.<TelemetryWindowBroadcast>never().doOnCancel(() -> cancelled.set(true)));
        BroadcastService service = new BroadcastService(buffer, source, metrics, 16);
        service.start();

        service.stop();

        assertThat(cancelled).isTrue();
    }
}
