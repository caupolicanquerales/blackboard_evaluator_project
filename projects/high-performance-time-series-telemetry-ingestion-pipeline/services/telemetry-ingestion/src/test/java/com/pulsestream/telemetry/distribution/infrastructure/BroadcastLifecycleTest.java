package com.pulsestream.telemetry.distribution.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import com.pulsestream.telemetry.distribution.application.BroadcastService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class BroadcastLifecycleTest {

    @Mock
    private BroadcastService service;

    @Test
    void isRunning_beforeStart_false() {
        BroadcastLifecycle lifecycle = new BroadcastLifecycle(service);

        assertThat(lifecycle.isRunning()).isFalse();
    }

    @Test
    void start_called_delegatesOnceAndIsRunning() {
        BroadcastLifecycle lifecycle = new BroadcastLifecycle(service);

        lifecycle.start();

        verify(service, times(1)).start();
        assertThat(lifecycle.isRunning()).isTrue();
    }

    @Test
    void stop_afterStart_delegatesOnceAndNotRunning() {
        BroadcastLifecycle lifecycle = new BroadcastLifecycle(service);
        lifecycle.start();

        lifecycle.stop();

        verify(service, times(1)).stop();
        assertThat(lifecycle.isRunning()).isFalse();
    }
}
