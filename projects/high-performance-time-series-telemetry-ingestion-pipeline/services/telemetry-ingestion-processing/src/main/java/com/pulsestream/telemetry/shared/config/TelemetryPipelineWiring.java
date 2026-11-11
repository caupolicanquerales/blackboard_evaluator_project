package com.pulsestream.telemetry.shared.config;

import org.springframework.stereotype.Component;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import reactor.core.Disposable;
import reactor.core.publisher.Mono;
import com.pulsestream.telemetry.ingestion.application.TelemetryEventBus;
import com.pulsestream.telemetry.reordering.application.ReorderingService;
import com.pulsestream.telemetry.eventlog.application.EventLogService;
import reactor.core.publisher.Flux;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;

@Component
public class TelemetryPipelineWiring {

    private final TelemetryEventBus eventBus;

    private final ReorderingService reorderingService;

    private final EventLogService eventLogService;

    private Disposable recordSubscription;

    private Disposable reconcileSubscription;

    public TelemetryPipelineWiring(TelemetryEventBus eventBus, ReorderingService reorderingService, EventLogService eventLogService) {
        this.eventBus = eventBus;
        this.reorderingService = reorderingService;
        this.eventLogService = eventLogService;
    }

    @PreDestroy
    public void stop() {
        if (recordSubscription != null) {
            recordSubscription.dispose();
            recordSubscription = null;
        }
        if (reconcileSubscription != null) {
            reconcileSubscription.dispose();
            reconcileSubscription = null;
        }
    }

    @PostConstruct
    public void start() {
        stop();
        Flux<TelemetrySample> stream = eventBus.stream();
        recordSubscription = stream.concatMap(sample -> Mono.defer(() -> eventLogService.record(sample)).onErrorResume(error -> Mono.empty())).subscribe(unused -> {
        }, error -> {
        });
        reconcileSubscription = reorderingService.windows(stream).concatMap(sample -> Mono.defer(() -> eventLogService.reconcile(sample)).onErrorResume(error -> Mono.empty())).subscribe(unused -> {
        }, error -> {
        });
    }
}
