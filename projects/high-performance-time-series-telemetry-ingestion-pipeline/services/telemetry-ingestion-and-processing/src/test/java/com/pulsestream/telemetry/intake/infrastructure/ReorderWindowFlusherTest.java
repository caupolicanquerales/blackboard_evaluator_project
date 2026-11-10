package com.pulsestream.telemetry.intake.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.application.TelemetryIngestionService;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Mono;
import reactor.test.scheduler.VirtualTimeScheduler;

@ExtendWith(MockitoExtension.class)
class ReorderWindowFlusherTest {

    private static final Duration FLUSH_INTERVAL = Duration.ofSeconds(1);

    @Mock
    private TelemetryIngestionService ingestionService;

    private VirtualTimeScheduler scheduler;
    private ReorderWindowFlusher flusher;

    @BeforeEach
    void setUp() {
        scheduler = VirtualTimeScheduler.getOrSet();
        flusher = new ReorderWindowFlusher(ingestionService, properties());
    }

    @AfterEach
    void tearDown() {
        flusher.stop();
        VirtualTimeScheduler.reset();
    }

    @Test
    void isRunning_beforeStart_returnsFalse() {
        assertThat(flusher.isRunning()).isFalse();
    }

    @Test
    void isRunning_afterStart_returnsTrue() {
        flusher.start();

        assertThat(flusher.isRunning()).isTrue();
    }

    @Test
    void isRunning_afterStop_returnsFalse() {
        flusher.start();

        flusher.stop();

        assertThat(flusher.isRunning()).isFalse();
    }

    @Test
    void start_beforeIntervalElapses_doesNotFlush() {
        flusher.start();

        scheduler.advanceTimeBy(FLUSH_INTERVAL.minusMillis(1));

        verifyNoInteractions(ingestionService);
    }

    @Test
    void start_eachIntervalElapsed_invokesFlushReleasable() {
        when(ingestionService.flushReleasable()).thenReturn(Mono.empty());
        flusher.start();

        scheduler.advanceTimeBy(FLUSH_INTERVAL.multipliedBy(3));

        verify(ingestionService, times(3)).flushReleasable();
    }

    @Test
    void start_flushFails_continuesOnNextInterval() {
        AtomicInteger calls = new AtomicInteger();
        when(ingestionService.flushReleasable()).thenAnswer(invocation ->
                calls.getAndIncrement() == 0
                        ? Mono.<Void>error(new IllegalStateException("boom"))
                        : Mono.<Void>empty());
        flusher.start();

        scheduler.advanceTimeBy(FLUSH_INTERVAL.multipliedBy(3));

        assertThat(calls.get()).isEqualTo(3);
        assertThat(flusher.isRunning()).isTrue();
    }

    @Test
    void start_flushInFlight_doesNotOverlapFlushes() {
        when(ingestionService.flushReleasable()).thenReturn(Mono.never());
        flusher.start();

        scheduler.advanceTimeBy(FLUSH_INTERVAL.multipliedBy(5));

        verify(ingestionService, times(1)).flushReleasable();
    }

    @Test
    void stop_afterStart_stopsFurtherFlushes() {
        when(ingestionService.flushReleasable()).thenReturn(Mono.empty());
        flusher.start();
        scheduler.advanceTimeBy(FLUSH_INTERVAL);

        flusher.stop();
        scheduler.advanceTimeBy(FLUSH_INTERVAL.multipliedBy(5));

        verify(ingestionService, times(1)).flushReleasable();
    }

    @Test
    void stop_withoutStart_doesNotThrowAndStaysStopped() {
        flusher.stop();

        assertThat(flusher.isRunning()).isFalse();
        verifyNoInteractions(ingestionService);
    }

    @Test
    void start_flushIntervalFromConfig_usesConfiguredInterval() {
        when(ingestionService.flushReleasable()).thenReturn(Mono.empty());
        ReorderWindowFlusher custom = new ReorderWindowFlusher(
                ingestionService, propertiesWithInterval(Duration.ofSeconds(10)));
        custom.start();

        scheduler.advanceTimeBy(Duration.ofSeconds(9));
        verifyNoInteractions(ingestionService);
        scheduler.advanceTimeBy(Duration.ofSeconds(1));
        custom.stop();

        verify(ingestionService, atLeastOnce()).flushReleasable();
    }

    private static TelemetryProperties properties() {
        return propertiesWithInterval(FLUSH_INTERVAL);
    }

    private static TelemetryProperties propertiesWithInterval(Duration flushInterval) {
        return new TelemetryProperties(
                Map.of(),
                Duration.ofSeconds(5),
                flushInterval,
                16,
                TelemetryProperties.OverflowStrategy.REJECT,
                TelemetryProperties.LatePacketPolicy.APPEND_REVISION,
                3,
                Duration.ofMillis(100),
                8);
    }
}
