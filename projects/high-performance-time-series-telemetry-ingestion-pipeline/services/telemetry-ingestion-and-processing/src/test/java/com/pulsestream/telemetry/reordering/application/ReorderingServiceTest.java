package com.pulsestream.telemetry.reordering.application;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.Test;

import com.pulsestream.telemetry.reordering.domain.TelemetryBackfillDetected;
import com.pulsestream.telemetry.reordering.domain.TelemetryWindowOrdered;
import com.pulsestream.telemetry.reordering.domain.ValidatedTelemetryEvent;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;
import reactor.test.scheduler.VirtualTimeScheduler;

class ReorderingServiceTest {

    private static final Duration WINDOW = Duration.ofSeconds(10);
    private static final Instant T0 = Instant.parse("2024-01-01T00:00:00Z");

    private static final class FakeLedgerEventPort implements LedgerEventPort {
        final List<Object> published = new ArrayList<>();
        final AtomicInteger failuresLeft = new AtomicInteger();
        final AtomicInteger attempts = new AtomicInteger();

        @Override
        public Mono<Void> publish(Object event) {
            return Mono.defer(() -> {
                attempts.incrementAndGet();
                if (failuresLeft.getAndUpdate(n -> Math.max(0, n - 1)) > 0) {
                    return Mono.error(new IllegalStateException("ledger down"));
                }
                published.add(event);
                return Mono.empty();
            });
        }
    }

    private static ValidatedTelemetryEvent event(String metric, long offsetSeconds) {
        return new ValidatedTelemetryEvent(metric, T0.plusSeconds(offsetSeconds), 1.0);
    }

    private static ReorderingService service(FakeLedgerEventPort port) {
        return new ReorderingService(port, WINDOW);
    }

    @Test
    void process_windowCloses_emitsWindowOrderedWithSamplesSortedByTimestamp() {
        VirtualTimeScheduler.getOrSet();
        FakeLedgerEventPort port = new FakeLedgerEventPort();
        Flux<ValidatedTelemetryEvent> source = Flux.just(event("cpu", 5), event("cpu", 2), event("cpu", 12));

        StepVerifier.withVirtualTime(() -> service(port).process(source))
                .thenAwait(WINDOW.multipliedBy(2))
                .verifyComplete();

        assertThat(port.published).hasAtLeastOneElementOfType(TelemetryWindowOrdered.class);
        TelemetryWindowOrdered first = port.published.stream()
                .filter(TelemetryWindowOrdered.class::isInstance)
                .map(TelemetryWindowOrdered.class::cast)
                .findFirst().orElseThrow();
        assertThat(first.samples()).extracting(ValidatedTelemetryEvent::timestamp)
                .containsExactly(T0.plusSeconds(2), T0.plusSeconds(5));
    }

    @Test
    void process_oneWindowPerClose_emitsOneWindowOrderedPerClosedWindow() {
        VirtualTimeScheduler.getOrSet();
        FakeLedgerEventPort port = new FakeLedgerEventPort();
        Flux<ValidatedTelemetryEvent> source = Flux.just(event("cpu", 1), event("cpu", 11), event("cpu", 21));

        StepVerifier.withVirtualTime(() -> service(port).process(source))
                .thenAwait(WINDOW.multipliedBy(5))
                .verifyComplete();

        assertThat(port.published).filteredOn(TelemetryWindowOrdered.class::isInstance).hasSize(3);
    }

    @Test
    void process_lateSample_emitsBackfillDetected() {
        VirtualTimeScheduler.getOrSet();
        FakeLedgerEventPort port = new FakeLedgerEventPort();
        Flux<ValidatedTelemetryEvent> source = Flux.just(event("cpu", 1), event("cpu", 25), event("cpu", 3));

        StepVerifier.withVirtualTime(() -> service(port).process(source))
                .thenAwait(WINDOW.multipliedBy(5))
                .verifyComplete();

        assertThat(port.published).filteredOn(TelemetryBackfillDetected.class::isInstance).hasSize(1);
    }

    @Test
    void process_inOrderSamples_emitsNoBackfillDetected() {
        VirtualTimeScheduler.getOrSet();
        FakeLedgerEventPort port = new FakeLedgerEventPort();
        Flux<ValidatedTelemetryEvent> source = Flux.just(event("cpu", 1), event("cpu", 2), event("cpu", 15));

        StepVerifier.withVirtualTime(() -> service(port).process(source))
                .thenAwait(WINDOW.multipliedBy(5))
                .verifyComplete();

        assertThat(port.published).noneMatch(TelemetryBackfillDetected.class::isInstance);
    }

    @Test
    void process_downstreamFailsTransiently_retriesAndEventuallyPublishes() {
        VirtualTimeScheduler.getOrSet();
        FakeLedgerEventPort port = new FakeLedgerEventPort();
        port.failuresLeft.set(2);
        Flux<ValidatedTelemetryEvent> source = Flux.just(event("cpu", 1), event("cpu", 12));

        StepVerifier.withVirtualTime(() -> service(port).process(source))
                .thenAwait(Duration.ofMinutes(10))
                .verifyComplete();

        assertThat(port.attempts.get()).isGreaterThan(2);
        assertThat(port.published).filteredOn(TelemetryWindowOrdered.class::isInstance).isNotEmpty();
    }

    @Test
    void process_downstreamKeepsFailing_doesNotDiscardEventSilently() {
        VirtualTimeScheduler.getOrSet();
        FakeLedgerEventPort port = new FakeLedgerEventPort();
        port.failuresLeft.set(Integer.MAX_VALUE);
        Flux<ValidatedTelemetryEvent> source = Flux.just(event("cpu", 1), event("cpu", 12));

        StepVerifier.withVirtualTime(() -> service(port).process(source))
                .thenAwait(Duration.ofMinutes(10))
                .expectError()
                .verify(Duration.ofSeconds(5));

        assertThat(port.attempts.get()).isGreaterThan(1);
    }
}
