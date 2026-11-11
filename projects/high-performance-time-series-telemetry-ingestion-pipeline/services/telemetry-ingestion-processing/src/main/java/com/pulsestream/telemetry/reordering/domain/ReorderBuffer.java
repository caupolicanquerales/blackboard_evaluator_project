package com.pulsestream.telemetry.reordering.domain;

import java.util.ArrayList;
import java.util.List;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;

@org.springframework.stereotype.Component
public class ReorderBuffer {

    private final List<TelemetrySample> buffer = new ArrayList<>();

    private final long windowMs;

    public ReorderBuffer(TelemetryProperties properties) {
        this.windowMs = properties.reorderWindowSeconds() * 1000L;
    }

    public List<TelemetrySample> drain() {
        List<TelemetrySample> all = new ArrayList<>(buffer);
        buffer.clear();
        return all;
    }

    public List<TelemetrySample> accept(TelemetrySample sample, long nowEpochMs) {
        int insertedAt = insertOrdered(sample);
        int count = countExpired(nowEpochMs - windowMs);
        // A lone late sample that sorts first is held back while newer ones remain buffered.
        if (count == 1 && insertedAt == 0 && buffer.size() > 1) {
            count = 0;
        }
        List<TelemetrySample> head = buffer.subList(0, count);
        List<TelemetrySample> released = new ArrayList<>(head);
        head.clear();
        return released;
    }

    // Upper-bound binary search keeps equal timestamps in arrival order (stable).
    private int insertOrdered(TelemetrySample sample) {
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
        return low;
    }

    private int countExpired(long cutoff) {
        int count = 0;
        while (count < buffer.size() && buffer.get(count).tDeviceEpochMs() <= cutoff) {
            count++;
        }
        return count;
    }
}
