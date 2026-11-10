package com.pulsestream.telemetry.sequencing.domain;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;

public class ReorderWindow {

    private final Duration window;

    private final int capacity;

    private final List<TelemetrySampleEvent> buffer = new ArrayList<>();

    private Instant highest;

    public enum Outcome {

        IN_ORDER, BACKFILL, LATE
    }

    public ReorderWindow(Duration window, int capacity) {
        Objects.requireNonNull(window, "window must not be null");
        if (window.isZero() || window.isNegative()) {
            throw new IllegalArgumentException("window must be positive");
        }
        if (capacity <= 0) {
            throw new IllegalArgumentException("capacity must be positive");
        }
        this.window = window;
        this.capacity = capacity;
    }

    public List<TelemetrySampleEvent> drainReady() {
        List<TelemetrySampleEvent> released = new ArrayList<>();
        if (highest == null) {
            return released;
        }
        Instant cutoff = highest.minus(window);
        while (!buffer.isEmpty() && (!buffer.get(0).tDevice().isAfter(cutoff) || buffer.size() > capacity)) {
            released.add(buffer.remove(0));
        }
        return released;
    }

    public List<TelemetrySampleEvent> drainAll() {
        List<TelemetrySampleEvent> released = new ArrayList<>(buffer);
        buffer.clear();
        return released;
    }

    private void insertOrdered(TelemetrySampleEvent event) {
        int index = buffer.size();
        while (index > 0 && buffer.get(index - 1).tDevice().isAfter(event.tDevice())) {
            index--;
        }
        buffer.add(index, event);
    }

    public Outcome offer(TelemetrySampleEvent event) {
        Objects.requireNonNull(event, "event must not be null");
        Instant tDevice = event.tDevice();
        if (highest == null || !tDevice.isBefore(highest)) {
            highest = tDevice;
            insertOrdered(event);
            return Outcome.IN_ORDER;
        }
        if (tDevice.isBefore(highest.minus(window))) {
            return Outcome.LATE;
        }
        insertOrdered(event);
        return Outcome.BACKFILL;
    }
}
