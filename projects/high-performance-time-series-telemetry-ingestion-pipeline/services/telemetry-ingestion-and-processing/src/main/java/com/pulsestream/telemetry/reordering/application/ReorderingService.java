package com.pulsestream.telemetry.reordering.application;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.util.retry.Retry;
import com.pulsestream.telemetry.reordering.domain.TelemetryBackfillDetected;
import com.pulsestream.telemetry.reordering.domain.TelemetryWindowOrdered;
import com.pulsestream.telemetry.reordering.domain.ValidatedTelemetryEvent;

@Service
public class ReorderingService {

    private final LedgerEventPort port;

    private final Duration window;

    public ReorderingService(LedgerEventPort port, Duration window) {
        this.port = Objects.requireNonNull(port, "port");
        this.window = Objects.requireNonNull(window, "window");
        if (window.isZero() || window.isNegative()) {
            throw new IllegalArgumentException("window must be positive");
        }
    }

    public Flux<Void> process(Flux<ValidatedTelemetryEvent> source) {
        Objects.requireNonNull(source, "source");
        long windowMillis = window.toMillis();
        return Flux.defer(() -> {
            Map<String, Long> openBucket = new HashMap<>();
            Map<String, List<ValidatedTelemetryEvent>> buffers = new HashMap<>();
            Function<String, Object> closeWindow = metric -> {
                List<ValidatedTelemetryEvent> samples = new ArrayList<>(buffers.remove(metric));
                samples.sort(Comparator.comparing(ValidatedTelemetryEvent::timestamp));
                Instant start = Instant.ofEpochMilli(openBucket.remove(metric) * windowMillis);
                return new TelemetryWindowOrdered(metric, start, start.plus(window), List.copyOf(samples));
            };
            Flux<Object> emitted = source.concatMap(event -> {
                String metric = event.metric();
                long bucket = Math.floorDiv(event.timestamp().toEpochMilli(), windowMillis);
                Long open = openBucket.get(metric);
                List<Object> out = new ArrayList<>();
                if (open == null) {
                    openBucket.put(metric, bucket);
                    buffers.put(metric, new ArrayList<>(List.of(event)));
                } else if (bucket < open) {
                    out.add(new TelemetryBackfillDetected(metric, event.timestamp(), Instant.ofEpochMilli(open * windowMillis)));
                } else if (bucket == open) {
                    buffers.get(metric).add(event);
                } else {
                    out.add(closeWindow.apply(metric));
                    openBucket.put(metric, bucket);
                    buffers.put(metric, new ArrayList<>(List.of(event)));
                }
                return Flux.fromIterable(out);
            }).concatWith(Flux.defer(() -> Flux.fromIterable(new ArrayList<>(buffers.keySet())).map(closeWindow)));
            return emitted.concatMap(domainEvent -> port.publish(domainEvent).retryWhen(Retry.backoff(5, Duration.ofSeconds(1)).maxBackoff(Duration.ofSeconds(30))));
        });
    }
}
