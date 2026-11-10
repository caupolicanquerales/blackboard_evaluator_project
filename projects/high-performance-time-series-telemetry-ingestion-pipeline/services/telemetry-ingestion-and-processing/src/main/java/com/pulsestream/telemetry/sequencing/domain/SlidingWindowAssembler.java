package com.pulsestream.telemetry.sequencing.domain;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.TreeMap;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;

public class SlidingWindowAssembler {

    private final Duration size;

    private final Duration slide;

    private final TreeMap<Instant, List<TelemetrySampleEvent>> openWindows = new TreeMap<>();

    public SlidingWindowAssembler(Duration size, Duration slide) {
        Objects.requireNonNull(size, "size must not be null");
        Objects.requireNonNull(slide, "slide must not be null");
        if (slide.isZero() || slide.isNegative()) {
            throw new IllegalArgumentException("slide must be positive");
        }
        if (size.compareTo(slide) < 0) {
            throw new IllegalArgumentException("size must be greater than or equal to slide");
        }
        this.size = size;
        this.slide = slide;
    }

    public List<TelemetryWindowClosedEvent> flush() {
        return closeEndingAtOrBefore(Instant.MAX);
    }

    private List<TelemetryWindowClosedEvent> closeEndingAtOrBefore(Instant bound) {
        List<TelemetryWindowClosedEvent> closed = new ArrayList<>();
        var iterator = openWindows.entrySet().iterator();
        while (iterator.hasNext()) {
            var entry = iterator.next();
            Instant end = entry.getKey().plus(size);
            if (end.isAfter(bound)) {
                break;
            }
            List<TelemetrySampleEvent> samples = entry.getValue();
            closed.add(new TelemetryWindowClosedEvent(samples.get(0).deviceId(), entry.getKey(), end, samples));
            iterator.remove();
        }
        return closed;
    }

    public List<TelemetryWindowClosedEvent> add(TelemetrySampleEvent orderedSample) {
        Objects.requireNonNull(orderedSample, "orderedSample must not be null");
        Instant tDevice = orderedSample.tDevice();
        List<TelemetryWindowClosedEvent> closed = closeEndingAtOrBefore(tDevice);
        long slideNanos = slide.toNanos();
        long epochNanos = Math.addExact(Math.multiplyExact(tDevice.getEpochSecond(), 1_000_000_000L), tDevice.getNano());
        Instant start = Instant.ofEpochSecond(0, Math.floorDiv(epochNanos, slideNanos) * slideNanos);
        while (start.plus(size).isAfter(tDevice)) {
            openWindows.computeIfAbsent(start, key -> new ArrayList<>()).add(orderedSample);
            start = start.minus(slide);
        }
        return closed;
    }
}
