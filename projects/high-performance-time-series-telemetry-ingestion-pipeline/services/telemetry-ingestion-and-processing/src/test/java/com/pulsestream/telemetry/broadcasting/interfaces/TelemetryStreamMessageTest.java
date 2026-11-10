package com.pulsestream.telemetry.broadcasting.interfaces;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem;
import com.pulsestream.telemetry.broadcasting.domain.BroadcastItem.Kind;
import com.pulsestream.telemetry.broadcasting.interfaces.TelemetryStreamMessage.SampleView;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class TelemetryStreamMessageTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:05Z");

    private static TelemetrySampleEvent event(String deviceId, String metric, double value, String status) {
        return new TelemetrySampleEvent(deviceId, metric, value, T_DEVICE, T_INGRESS, status);
    }

    @Test
    void from_sampleItem_mapsKindDeviceAndSingleSample() {
        BroadcastItem item = BroadcastItem.sample(event("device-1", "temp", 21.5, TelemetrySampleEvent.VALID));

        TelemetryStreamMessage message = TelemetryStreamMessage.from(item);

        assertThat(message.kind()).isEqualTo("SAMPLE");
        assertThat(message.deviceId()).isEqualTo("device-1");
        assertThat(message.samples()).containsExactly(new SampleView("temp", 21.5, T_DEVICE, "VALID"));
    }

    @Test
    void from_windowItem_mapsKindAndAllSamplesInOrder() {
        TelemetrySampleEvent first = event("device-2", "temp", 1.0, TelemetrySampleEvent.VALID);
        TelemetrySampleEvent second = event("device-2", "humidity", 2.0, TelemetrySampleEvent.VALID);
        BroadcastItem item = new BroadcastItem(Kind.WINDOW, "device-2", List.of(first, second));

        TelemetryStreamMessage message = TelemetryStreamMessage.from(item);

        assertThat(message.kind()).isEqualTo("WINDOW");
        assertThat(message.samples()).extracting(SampleView::metric).containsExactly("temp", "humidity");
    }

    @Test
    void from_failedValidationSample_exposesOnlyValidationStatus() {
        BroadcastItem item = BroadcastItem.sample(
                event("device-3", "temp", 9.0, TelemetrySampleEvent.VALIDATION_FAILED));

        TelemetryStreamMessage message = TelemetryStreamMessage.from(item);

        assertThat(message.samples().get(0).validationStatus()).isEqualTo("VALIDATION_FAILED");
    }

    @Test
    void from_sampleItem_usesDeviceTimeNotIngressTime() {
        BroadcastItem item = BroadcastItem.sample(event("device-4", "temp", 3.0, TelemetrySampleEvent.VALID));

        TelemetryStreamMessage message = TelemetryStreamMessage.from(item);

        assertThat(message.samples().get(0).tDevice()).isEqualTo(T_DEVICE);
    }

    @Test
    void from_null_throws() {
        assertThatThrownBy(() -> TelemetryStreamMessage.from(null)).isInstanceOf(RuntimeException.class);
    }
}
