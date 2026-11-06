package com.pulsestream.telemetry.reordering.domain;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;

public class ReorderWindow {

    private final Duration window;

    private final List<TelemetrySample> pending = new ArrayList<>();

    private Instant watermark = Instant.MIN;

    public ReorderWindow(Duration window) {
        this.window = Objects.requireNonNull(window, "window must not be null");
    }

    public void offer(TelemetrySample sample) {
        pending.add(Objects.requireNonNull(sample, "sample must not be null"));
    }

    public List<ReleasedSample> release(Instant now) {
        Objects.requireNonNull(now, "now must not be null");
        Instant cutoff = now.minus(window);
        List<TelemetrySample> due = pending.stream().filter(sample -> !sample.tDevice().isAfter(cutoff)).sorted(Comparator.comparing(TelemetrySample::tDevice)).toList();
        pending.removeAll(due);
        Instant batchWatermark = watermark;
        List<ReleasedSample> released = new ArrayList<>();
        for (TelemetrySample sample : due) {
            released.add(new ReleasedSample(sample, sample.tDevice().isBefore(batchWatermark)));
            if (sample.tDevice().isAfter(watermark)) {
                watermark = sample.tDevice();
            }
        }
        return List.copyOf(released);
    }
}
