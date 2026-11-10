package com.pulsestream.telemetry.ledger.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.shared.event.TelemetryEvent;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import reactor.test.StepVerifier;

class InMemoryDeadLetterSinkTest {

    private static InMemoryDeadLetterSink sink(int capacity) {
        TelemetryProperties props = mock(TelemetryProperties.class);
        when(props.deadLetterCapacity()).thenReturn(capacity);
        return new InMemoryDeadLetterSink(props);
    }

    @Test
    void reject_withEventAndCause_completesWithoutError() {
        InMemoryDeadLetterSink sink = sink(4);

        StepVerifier.create(sink.reject(mock(TelemetryEvent.class), new IllegalStateException("boom")))
                .verifyComplete();
    }

    @Test
    void deadLetters_afterReject_replaysEventAndCause() {
        InMemoryDeadLetterSink sink = sink(4);
        TelemetryEvent event = mock(TelemetryEvent.class);
        sink.reject(event, new IllegalStateException("boom")).block(Duration.ofSeconds(1));

        StepVerifier.create(sink.deadLetters().take(1))
                .assertNext(letter -> {
                    assertThat(letter.event()).isSameAs(event);
                    assertThat(letter.cause()).contains("boom");
                })
                .verifyComplete();
    }

    @Test
    void reject_beyondCapacity_neverBlocksNorErrors() {
        InMemoryDeadLetterSink sink = sink(2);

        for (int i = 0; i < 10; i++) {
            StepVerifier.create(sink.reject(mock(TelemetryEvent.class), new RuntimeException("c" + i)))
                    .verifyComplete();
        }
    }

    @Test
    void deadLetters_afterOverflow_retainsAtMostCapacityEntries() {
        InMemoryDeadLetterSink sink = sink(2);
        for (int i = 0; i < 5; i++) {
            sink.reject(mock(TelemetryEvent.class), new RuntimeException("c" + i)).block(Duration.ofSeconds(1));
        }

        assertThat(sink.deadLetters().take(Duration.ofMillis(200)).collectList().block(Duration.ofSeconds(2)))
                .hasSizeLessThanOrEqualTo(2);
    }
}
