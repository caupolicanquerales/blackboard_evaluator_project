package com.pulsestream.telemetry.eventlog.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import reactor.test.StepVerifier;

class SinkEventBroadcastTest {

    private static final Instant T = Instant.parse("2025-01-01T10:00:00Z");

    private static SinkEventBroadcast broadcast(int capacity) {
        return new SinkEventBroadcast(
                new TelemetryProperties(60, capacity, 30, 220, 0, 2000, 0, 200, 0));
    }

    private static EventRecord record(int revision) {
        return new EventRecord(
                new TelemetrySample("d1", "heart_rate", T, T, 100.0, "VALID", "corr"),
                revision, revision == 1 ? "RECORD" : "REVISION");
    }

    @Test
    void stream_subscriberAttached_receivesPublishedRecordsInOrder() {
        SinkEventBroadcast broadcast = broadcast(4);
        EventRecord first = record(1);
        EventRecord second = record(2);

        StepVerifier.create(broadcast.stream().take(2))
                .then(() -> {
                    broadcast.publish(first);
                    broadcast.publish(second);
                })
                .expectNext(first, second)
                .expectComplete()
                .verify(Duration.ofSeconds(5));
    }

    @Test
    void publish_capacityRemaining_returnsTrue() {
        assertThat(broadcast(2).publish(record(1))).isTrue();
    }

    @Test
    void publish_boundedBufferFullWithoutSubscriber_returnsFalse() {
        SinkEventBroadcast broadcast = broadcast(2);
        broadcast.publish(record(1));
        broadcast.publish(record(2));

        assertThat(broadcast.publish(record(3))).isFalse();
    }
}
