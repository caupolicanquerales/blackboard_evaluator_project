package com.pulsestream.telemetry.distribution.application;

import com.pulsestream.telemetry.distribution.api.ValidatedEventConsumer;
import com.pulsestream.telemetry.distribution.domain.TelemetryWindowBroadcast;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import reactor.core.Disposable;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;

@Service
public class BroadcastService {

    private static final Logger LOG = LoggerFactory.getLogger(BroadcastService.class);
    private final ValidatedEventConsumer buffer;
    private final TelemetryEventSource source;
    private final TelemetryMetrics metrics;
    private final Sinks.Many<TelemetryWindowBroadcast> sink;
    private Disposable subscription;

    public BroadcastService(ValidatedEventConsumer buffer, TelemetryEventSource source, TelemetryMetrics metrics, int sinkCapacity) {
        this.buffer = buffer;
        this.source = source;
        this.metrics = metrics;
        this.sink = Sinks.many().multicast().onBackpressureBuffer(sinkCapacity, false);
    }

    public void start() {
        if (isRunning()) {
            return;
        }
        subscription = buffer.buffer(source.events()).subscribe(this::publish);
    }

    public void stop() {
        if (subscription != null) {
            subscription.dispose();
        }
    }

    public Flux<TelemetryWindowBroadcast> subscribe() {
        return sink.asFlux();
    }

    private boolean isRunning() {
        return subscription != null && !subscription.isDisposed();
    }

    private void publish(TelemetryWindowBroadcast window) {
        Sinks.EmitResult result = sink.tryEmitNext(window);
        if (result == Sinks.EmitResult.FAIL_OVERFLOW) {
            metrics.broadcastDropped("subscriber-overflow");
            LOG.warn("broadcast-overflow-dropped");
        } else if (result.isSuccess()) {
            metrics.windowBroadcast("broadcast");
            LOG.info("window-broadcast");
        }
    }
}
