package com.pulsestream.telemetry.sequencing.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetryBackfillDetectedEvent;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import reactor.test.StepVerifier;

class SequencingServiceTest {

    private static final Instant BASE = Instant.ofEpochSecond(1000);

    private final List<TelemetrySampleEvent> sequenced = new ArrayList<>();
    private final List<TelemetryBackfillDetectedEvent> backfills = new ArrayList<>();
    private final List<TelemetryWindowClosedEvent> windows = new ArrayList<>();
    private SequencingService service;

    @BeforeEach
    void setUp() {
        service = serviceWithBackfillCapacity(100);
    }

    private SequencingService serviceWithBackfillCapacity(int backfillCapacity) {
        BoundedEventChannel<TelemetrySampleEvent> sampleChannel = new BoundedEventChannel<>("sequenced", 100);
        BoundedEventChannel<TelemetryBackfillDetectedEvent> backfillChannel =
                new BoundedEventChannel<>("backfills", backfillCapacity);
        BoundedEventChannel<TelemetryWindowClosedEvent> windowChannel = new BoundedEventChannel<>("windows", 100);
        sequenced.clear();
        backfills.clear();
        windows.clear();
        sampleChannel.stream().subscribe(sequenced::add);
        backfillChannel.stream().subscribe(backfills::add);
        windowChannel.stream().subscribe(windows::add);
        return new SequencingService(
                Duration.ofSeconds(10), 100, Duration.ofSeconds(10), Duration.ofSeconds(10),
                sampleChannel, backfillChannel, windowChannel);
    }

    private static TelemetrySampleEvent sample(String deviceId, long offsetSeconds, String status) {
        Instant t = BASE.plusSeconds(offsetSeconds);
        return new TelemetrySampleEvent(deviceId, "temperature", 1.0, t, t.plusMillis(5), status);
    }

    private static TelemetrySampleEvent sample(String deviceId, long offsetSeconds) {
        return sample(deviceId, offsetSeconds, "VALID");
    }

    private void receive(TelemetrySampleEvent sample) {
        StepVerifier.create(service.onSampleReceived(sample)).verifyComplete();
    }

    private void flush() {
        StepVerifier.create(service.flush()).verifyComplete();
    }

    @Test
    void onSampleReceived_inOrderSampleAfterWindowElapsed_publishesSequencedWithoutBackfill() {
        TelemetrySampleEvent first = sample("d1", 1);
        receive(first);
        receive(sample("d1", 20));

        assertThat(sequenced).containsExactly(first);
        assertThat(backfills).isEmpty();
    }

    @Test
    void onSampleReceived_backfillWithinWindow_publishesBackfillNotBeyondWindow() {
        TelemetrySampleEvent late = sample("d1", 22);
        receive(sample("d1", 25));
        receive(late);

        assertThat(backfills).containsExactly(new TelemetryBackfillDetectedEvent(late, false));
    }

    @Test
    void flush_afterBackfill_publishesSamplesInTDeviceOrder() {
        TelemetrySampleEvent newer = sample("d1", 5);
        TelemetrySampleEvent older = sample("d1", 2);
        receive(newer);
        receive(older);
        flush();

        assertThat(sequenced).containsExactly(older, newer);
    }

    @Test
    void onSampleReceived_olderThanReorderWindow_publishesBackfillBeyondWindowAndDoesNotSequenceIt() {
        TelemetrySampleEvent tooLate = sample("d1", 5);
        receive(sample("d1", 30));
        receive(tooLate);
        flush();

        assertThat(backfills).containsExactly(new TelemetryBackfillDetectedEvent(tooLate, true));
        assertThat(sequenced).doesNotContain(tooLate);
    }

    @Test
    void onSampleReceived_sampleReachesWindowEnd_publishesClosedWindow() {
        TelemetrySampleEvent first = sample("d1", 1);
        receive(first);
        receive(sample("d1", 12));
        receive(sample("d1", 30));

        assertThat(windows).hasSize(1);
        assertThat(windows.get(0).deviceId()).isEqualTo("d1");
        assertThat(windows.get(0).windowStart()).isEqualTo(BASE);
        assertThat(windows.get(0).windowEnd()).isEqualTo(BASE.plusSeconds(10));
        assertThat(windows.get(0).samples()).containsExactly(first);
    }

    @Test
    void flush_withOpenWindows_closesThemAndSequencesBufferedSamples() {
        TelemetrySampleEvent a = sample("d1", 1);
        TelemetrySampleEvent b = sample("d1", 12);
        receive(a);
        receive(b);
        flush();

        assertThat(sequenced).containsExactly(a, b);
        assertThat(windows).extracting(TelemetryWindowClosedEvent::windowStart)
                .containsExactly(BASE, BASE.plusSeconds(10));
    }

    @Test
    void onSampleReceived_differentDevices_areSequencedIndependently() {
        TelemetrySampleEvent other = sample("d2", 5);
        receive(sample("d1", 50));
        receive(other);
        flush();

        assertThat(backfills).isEmpty();
        assertThat(sequenced).contains(other);
    }

    @Test
    void onSampleReceived_validationFailedSample_isSequencedWithoutRevalidation() {
        TelemetrySampleEvent failed = sample("d1", 1, "VALIDATION_FAILED");
        receive(failed);
        flush();

        assertThat(sequenced).containsExactly(failed);
    }

    @Test
    void onSampleReceived_backfillChannelOverflow_propagatesOverflowError() {
        service = serviceWithBackfillCapacity(1);
        receive(sample("d1", 30));
        receive(sample("d1", 5));

        StepVerifier.create(service.onSampleReceived(sample("d1", 6)))
                .expectError(BoundedEventChannel.OverflowException.class)
                .verify();
    }

    @Test
    void flush_withNoSamples_completesWithoutPublishing() {
        flush();

        assertThat(sequenced).isEmpty();
        assertThat(windows).isEmpty();
        assertThat(backfills).isEmpty();
    }
}
