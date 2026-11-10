package com.pulsestream.telemetry.broadcasting.interfaces;

import java.time.Instant;
import java.util.List;
import java.util.Objects;
import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;

public record TelemetryStreamMessage(String kind, String deviceId, List<SampleView> samples) {

    public static TelemetryStreamMessage from(BroadcastItem item) {
        Objects.requireNonNull(item, "item must not be null");
        List<SampleView> views = item.samples().stream().map(sample -> new SampleView(sample.metric(), sample.value(), sample.tDevice(), sample.validationStatus())).toList();
        return new TelemetryStreamMessage(item.kind().name(), item.deviceId(), views);
    }

    public record SampleView(String metric, double value, Instant tDevice, String validationStatus) {
    }
}
