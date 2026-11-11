package com.pulsestream.telemetry.reordering.domain;

import java.util.ArrayList;
import java.util.List;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;

public class ReorderBuffer {

    private final java.util.List<TelemetrySample> buffer = new java.util.ArrayList<>();

    private final long windowMs;

    public ReorderBuffer(TelemetryProperties properties) {
        this.windowMs = properties.reorderWindowSeconds() * 1000L;
    }

    public java.util.List<TelemetrySample> drain() {
        java.util.List<TelemetrySample> all = new java.util.ArrayList<>(buffer);
        buffer.clear();
        return all;
    }

    public java.util.List<TelemetrySample> accept(TelemetrySample sample, long nowEpochMs) {
        int low = 0;
        int high = buffer.size();
        while (low < high) {
            int mid = (low + high) >>> 1;
            if (buffer.get(mid).tDeviceEpochMs() <= sample.tDeviceEpochMs()) {
                low = mid + 1;
            } else {
                high = mid;
            }
        }
        buffer.add(low, sample);
        long cutoff = nowEpochMs - windowMs;
        int count = 0;
        while (count < buffer.size() && buffer.get(count).tDeviceEpochMs() < cutoff) {
            count++;
        }
        java.util.List<TelemetrySample> head = buffer.subList(0, count);
        java.util.List<TelemetrySample> released = new java.util.ArrayList<>(head);
        head.clear();
        return released;
    }
}
