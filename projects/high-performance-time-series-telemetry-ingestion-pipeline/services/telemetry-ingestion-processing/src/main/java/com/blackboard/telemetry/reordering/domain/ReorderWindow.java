package com.blackboard.telemetry.reordering.domain;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidated;

public class ReorderWindow {

    private static final Duration MAX_DELAY = Duration.ofSeconds(60);

    private final Map<String, List<TelemetrySampleValidated>> buffers = new HashMap<>();

    private final Map<String, Instant> watermarks = new HashMap<>();

    public enum Outcome {

        IN_ORDER, BACKFILLED, TOO_LATE
    }

    public List<TelemetrySampleValidated> drain(Instant watermark) {
        Objects.requireNonNull(watermark, "watermark must not be null");
        List<TelemetrySampleValidated> released = new ArrayList<>();
        for (List<TelemetrySampleValidated> buffer : buffers.values()) {
            buffer.removeIf(sample -> {
                boolean releasable = !sample.tDevice().isAfter(watermark);
                if (releasable) {
                    released.add(sample);
                }
                return releasable;
            });
        }
        released.sort(Comparator.comparing(TelemetrySampleValidated::tDevice));
        return released;
    }

    public Outcome offer(TelemetrySampleValidated sample) {
        Objects.requireNonNull(sample, "sample must not be null");
        Instant watermark = watermarks.get(sample.deviceId());
        if (watermark != null && sample.tDevice().isBefore(watermark.minus(MAX_DELAY))) {
            return Outcome.TOO_LATE;
        }
        List<TelemetrySampleValidated> buffer = buffers.computeIfAbsent(sample.deviceId(), key -> new ArrayList<>());
        int index = buffer.size();
        while (index > 0 && buffer.get(index - 1).tDevice().isAfter(sample.tDevice())) {
            index--;
        }
        buffer.add(index, sample);
        if (watermark == null || !sample.tDevice().isBefore(watermark)) {
            watermarks.put(sample.deviceId(), sample.tDevice());
            return Outcome.IN_ORDER;
        }
        return Outcome.BACKFILLED;
    }
}
