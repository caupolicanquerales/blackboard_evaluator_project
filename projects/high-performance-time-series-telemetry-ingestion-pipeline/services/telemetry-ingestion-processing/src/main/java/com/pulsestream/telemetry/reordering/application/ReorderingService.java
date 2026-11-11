package com.pulsestream.telemetry.reordering.application;

import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.reordering.domain.ReorderBuffer;

@Service
public class ReorderingService {

    private final ReorderBuffer buffer;

    private final java.time.Clock clock;

    public ReorderingService(ReorderBuffer buffer, java.time.Clock clock) {
        this.buffer = buffer;
        this.clock = clock;
    }

    public Flux<TelemetrySample> windows(Flux<TelemetrySample> samples) {
        return samples.concatMapIterable(sample -> buffer.accept(sample, clock.millis())).concatWith(Flux.defer(() -> Flux.fromIterable(buffer.drain())));
    }
}
