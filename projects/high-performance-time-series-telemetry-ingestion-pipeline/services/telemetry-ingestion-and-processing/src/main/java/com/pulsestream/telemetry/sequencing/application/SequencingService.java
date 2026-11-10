package com.pulsestream.telemetry.sequencing.application;

import com.pulsestream.telemetry.sequencing.application.port.in.SequenceTelemetryUseCase;
import com.pulsestream.telemetry.sequencing.domain.ReorderWindow;
import com.pulsestream.telemetry.sequencing.domain.SlidingWindowAssembler;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetryBackfillDetectedEvent;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public class SequencingService implements SequenceTelemetryUseCase {

    private final Duration reorderWindow;

    private final int reorderBufferCapacity;

    private final Duration windowSize;

    private final Duration windowSlide;

    private final BoundedEventChannel<TelemetrySampleEvent> sequencedSamples;

    private final BoundedEventChannel<TelemetryBackfillDetectedEvent> backfillDetections;

    private final BoundedEventChannel<TelemetryWindowClosedEvent> closedWindows;

    private final Map<String, DeviceState> devices = new ConcurrentHashMap<>();

    public SequencingService(Duration reorderWindow, int reorderBufferCapacity, Duration windowSize, Duration windowSlide, BoundedEventChannel<TelemetrySampleEvent> sequencedSamples, BoundedEventChannel<TelemetryBackfillDetectedEvent> backfillDetections, BoundedEventChannel<TelemetryWindowClosedEvent> closedWindows) {
        this.reorderWindow = Objects.requireNonNull(reorderWindow, "reorderWindow");
        this.reorderBufferCapacity = reorderBufferCapacity;
        this.windowSize = Objects.requireNonNull(windowSize, "windowSize");
        this.windowSlide = Objects.requireNonNull(windowSlide, "windowSlide");
        this.sequencedSamples = Objects.requireNonNull(sequencedSamples, "sequencedSamples");
        this.backfillDetections = Objects.requireNonNull(backfillDetections, "backfillDetections");
        this.closedWindows = Objects.requireNonNull(closedWindows, "closedWindows");
    }

    public Mono<Void> onSampleReceived(TelemetrySampleEvent sample) {
        return Mono.defer(() -> {
            Objects.requireNonNull(sample, "sample");
            DeviceState state = devices.computeIfAbsent(sample.deviceId(), id -> new DeviceState(new ReorderWindow(reorderWindow, reorderBufferCapacity), new SlidingWindowAssembler(windowSize, windowSlide)));
            List<Mono<Void>> publications = new ArrayList<>();
            synchronized (state) {
                ReorderWindow.Outcome outcome = state.reorder.offer(sample);
                if (outcome == ReorderWindow.Outcome.BACKFILL) {
                    publications.add(backfillDetections.publish(new TelemetryBackfillDetectedEvent(sample, false)));
                } else if (outcome == ReorderWindow.Outcome.LATE) {
                    publications.add(backfillDetections.publish(new TelemetryBackfillDetectedEvent(sample, true)));
                }
                for (TelemetrySampleEvent ready : state.reorder.drainReady()) {
                    publishOrdered(state, ready, publications);
                }
            }
            return Flux.concat(publications).then();
        });
    }

    private void publishOrdered(DeviceState state, TelemetrySampleEvent ready, List<Mono<Void>> publications) {
        publications.add(sequencedSamples.publish(ready));
        for (TelemetryWindowClosedEvent window : state.assembler.add(ready)) {
            publications.add(closedWindows.publish(window));
        }
    }

    private static final class DeviceState {

        private final ReorderWindow reorder;

        private final SlidingWindowAssembler assembler;

        private DeviceState(ReorderWindow reorder, SlidingWindowAssembler assembler) {
            this.reorder = reorder;
            this.assembler = assembler;
        }
    }

    public Mono<Void> flush() {
        return Mono.defer(() -> {
            List<Mono<Void>> publications = new ArrayList<>();
            for (DeviceState state : devices.values()) {
                synchronized (state) {
                    for (TelemetrySampleEvent ready : state.reorder.drainAll()) {
                        publishOrdered(state, ready, publications);
                    }
                    for (TelemetryWindowClosedEvent window : state.assembler.flush()) {
                        publications.add(closedWindows.publish(window));
                    }
                }
            }
            return Flux.concat(publications).then();
        });
    }
}
