package com.pulsestream.telemetry.shared.config;

import com.pulsestream.telemetry.broadcasting.application.port.in.BroadcastTelemetryUseCase;
import com.pulsestream.telemetry.ledger.application.port.in.RecordTelemetryUseCase;
import com.pulsestream.telemetry.sequencing.application.port.in.SequenceTelemetryUseCase;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetryBackfillDetectedEvent;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.SmartLifecycle;
import org.springframework.stereotype.Component;
import reactor.core.Disposable;
import reactor.core.publisher.Mono;

@Component
public class TelemetryPipelineWiring {

    private static final Logger log = LoggerFactory.getLogger(TelemetryPipelineWiring.class);

    private final BoundedEventChannel<TelemetrySampleEvent> validatedSamples;

    private final BoundedEventChannel<TelemetrySampleEvent> sequencedSamples;

    private final BoundedEventChannel<TelemetryBackfillDetectedEvent> backfillDetections;

    private final BoundedEventChannel<TelemetryWindowClosedEvent> closedWindows;

    private final SequenceTelemetryUseCase sequence;

    private final RecordTelemetryUseCase record;

    private final BroadcastTelemetryUseCase broadcast;

    private final List<Disposable> subscriptions = new ArrayList<>();

    private boolean running;

    @Override
    public synchronized void start() {
        if (running) {
            return;
        }
        subscriptions.add(subscribe(validatedSamples, sequence::onSampleReceived));
        subscriptions.add(subscribe(sequencedSamples, record::recordSequenced));
        subscriptions.add(subscribe(sequencedSamples, broadcast::broadcastSample));
        subscriptions.add(subscribe(backfillDetections, record::recordBackfill));
        subscriptions.add(subscribe(closedWindows, broadcast::broadcastWindow));
        running = true;
    }

    @Override
    public synchronized void stop() {
        if (!running) {
            return;
        }
        subscriptions.forEach(Disposable::dispose);
        subscriptions.clear();
        running = false;
        sequence.flush().subscribe(ignored -> {
        }, error -> log.error("Sequencing flush failed", error));
    }

    @Override
    public synchronized boolean isRunning() {
        return running;
    }

    private <E> Disposable subscribe(BoundedEventChannel<E> channel, Function<E, Mono<?>> handler) {
        return channel.stream().concatMap(event -> Mono.defer(() -> handler.apply(event).then()).onErrorResume(error -> {
            log.error("Pipeline consumer failed on channel {}", channel.name(), error);
            return Mono.empty();
        })).subscribe();
    }

    public void TelemetryPipelineWiring(@Qualifier("validatedSamples") BoundedEventChannel<TelemetrySampleEvent> validatedSamples, @Qualifier("sequencedSamples") BoundedEventChannel<TelemetrySampleEvent> sequencedSamples, @Qualifier("backfillDetections") BoundedEventChannel<TelemetryBackfillDetectedEvent> backfillDetections, @Qualifier("closedWindows") BoundedEventChannel<TelemetryWindowClosedEvent> closedWindows, SequenceTelemetryUseCase sequence, RecordTelemetryUseCase record, BroadcastTelemetryUseCase broadcast) {
        this.validatedSamples = validatedSamples;
        this.sequencedSamples = sequencedSamples;
        this.backfillDetections = backfillDetections;
        this.closedWindows = closedWindows;
        this.sequence = sequence;
        this.record = record;
        this.broadcast = broadcast;
    }
}
