package com.pulsestream.telemetry.distribution.infrastructure;

import com.pulsestream.telemetry.distribution.application.BroadcastService;
import org.springframework.context.SmartLifecycle;

public class BroadcastLifecycle implements SmartLifecycle {

    private final BroadcastService broadcastService;

    private volatile boolean running;

    public BroadcastLifecycle(BroadcastService broadcastService) {
        this.broadcastService = broadcastService;
    }

    @Override
    public void start() {
        broadcastService.start();
        running = true;
    }

    @Override
    public void stop() {
        broadcastService.stop();
        running = false;
    }

    @Override
    public boolean isRunning() {
        return running;
    }
}
