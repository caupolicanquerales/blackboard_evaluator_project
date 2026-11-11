package com.pulsestream.telemetry.eventlog.application;

import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Flux;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.eventlog.domain.EventLogRepository;

@Service
public class EventLogService {

    private final EventLogRepository repository;

    public EventLogService(EventLogRepository repository) {
        this.repository = repository;
    }

    public Mono<Void> reconcile(TelemetrySample revision) {
        return repository.appendRevision(revision);
    }

    public Flux<TelemetrySample> query(String deviceId, long fromEpochMs, long toEpochMs) {
        return repository.findByDeviceAndRange(deviceId, fromEpochMs, toEpochMs);
    }

    public Mono<Void> record(TelemetrySample sample) {
        return repository.appendRecord(sample).then();
    }
}
