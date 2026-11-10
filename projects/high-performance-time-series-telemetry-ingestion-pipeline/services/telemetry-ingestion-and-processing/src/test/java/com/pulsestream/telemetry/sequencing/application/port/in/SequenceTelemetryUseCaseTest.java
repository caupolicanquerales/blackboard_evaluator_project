package com.pulsestream.telemetry.sequencing.application.port.in;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class SequenceTelemetryUseCaseTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:01Z");

    private static TelemetrySampleEvent event(String status) {
        return new TelemetrySampleEvent("dev-1", "temp", 21.5, T_DEVICE, T_INGRESS, status);
    }

    private static final class RecordingUseCase implements SequenceTelemetryUseCase {
        final List<TelemetrySampleEvent> received = new ArrayList<>();
        final AtomicInteger flushes = new AtomicInteger();
        final AtomicInteger subscriptions = new AtomicInteger();

        @Override
        public Mono<Void> onSampleReceived(TelemetrySampleEvent sample) {
            return Mono.defer(() -> {
                subscriptions.incrementAndGet();
                received.add(sample);
                return Mono.empty();
            });
        }

        @Override
        public Mono<Void> flush() {
            return Mono.defer(() -> {
                flushes.incrementAndGet();
                return Mono.empty();
            });
        }
    }

    @Test
    void onSampleReceived_validSample_completesEmptyAndDeliversSample() {
        RecordingUseCase useCase = new RecordingUseCase();
        TelemetrySampleEvent sample = event(TelemetrySampleEvent.VALID);

        StepVerifier.create(useCase.onSampleReceived(sample)).verifyComplete();

        assertThat(useCase.received).containsExactly(sample);
    }

    @Test
    void onSampleReceived_validationFailedSample_completesEmptyAndDeliversSample() {
        RecordingUseCase useCase = new RecordingUseCase();
        TelemetrySampleEvent sample = event(TelemetrySampleEvent.VALIDATION_FAILED);

        StepVerifier.create(useCase.onSampleReceived(sample)).verifyComplete();

        assertThat(useCase.received).containsExactly(sample);
    }

    @Test
    void onSampleReceived_notSubscribed_doesNotProcessSample() {
        RecordingUseCase useCase = new RecordingUseCase();

        Mono<Void> result = useCase.onSampleReceived(event(TelemetrySampleEvent.VALID));

        assertThat(result).isNotNull();
        assertThat(useCase.subscriptions.get()).isZero();
    }

    @Test
    void flush_afterSamples_completesEmpty() {
        RecordingUseCase useCase = new RecordingUseCase();
        useCase.onSampleReceived(event(TelemetrySampleEvent.VALID)).block();

        StepVerifier.create(useCase.flush()).verifyComplete();

        assertThat(useCase.flushes.get()).isEqualTo(1);
    }

    @Test
    void flush_notSubscribed_doesNotDrain() {
        RecordingUseCase useCase = new RecordingUseCase();

        Mono<Void> result = useCase.flush();

        assertThat(result).isNotNull();
        assertThat(useCase.flushes.get()).isZero();
    }
}
