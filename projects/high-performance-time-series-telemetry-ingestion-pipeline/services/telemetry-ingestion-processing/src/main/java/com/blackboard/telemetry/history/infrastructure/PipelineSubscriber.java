package com.blackboard.telemetry.history.infrastructure;

import org.springframework.context.SmartLifecycle;
import reactor.core.Disposable;
import reactor.core.publisher.Mono;
import com.blackboard.telemetry.history.application.ReorderHistoryService;
import com.blackboard.telemetry.ingestion.application.ValidatedSampleStream;

public class PipelineSubscriber implements SmartLifecycle {

    private final ValidatedSampleStream stream;

    private final ReorderHistoryService service;

    private volatile Disposable subscription;

    public PipelineSubscriber(ValidatedSampleStream stream, ReorderHistoryService service) {
        this.stream = stream;
        this.service = service;
    }

    @Override
    public void stop() {
        Disposable current = this.subscription;
        if (current != null) {
            current.dispose();
        }
        this.subscription = null;
    }

    @Override
    public boolean isRunning() {
        Disposable current = this.subscription;
        return current != null && !current.isDisposed();
    }

    public void start() {
        this.subscription = stream.events().concatMap(event -> service.handle(event).onErrorResume(error -> Mono.empty())).subscribe();
    }
}
