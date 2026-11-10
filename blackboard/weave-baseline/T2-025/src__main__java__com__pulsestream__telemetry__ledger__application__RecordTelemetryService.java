package com.pulsestream.telemetry.ledger.application;

import com.pulsestream.telemetry.ledger.application.port.in.RecordTelemetryUseCase;
import com.pulsestream.telemetry.ledger.application.port.out.TelemetryLedgerRepository;
import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetryBackfillDetectedEvent;
import com.pulsestream.telemetry.shared.events.TelemetryRevisionAppendedEvent;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import java.util.Objects;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

@Service
public class RecordTelemetryService {

    private final TelemetryLedgerRepository repository;

    private final BoundedEventChannel<TelemetryRevisionAppendedEvent> revisionsAppended;

    public RecordTelemetryService(TelemetryLedgerRepository repository, BoundedEventChannel<TelemetryRevisionAppendedEvent> revisionsAppended) {
        this.repository = Objects.requireNonNull(repository, "repository must not be null");
        this.revisionsAppended = Objects.requireNonNull(revisionsAppended, "revisionsAppended must not be null");
    }

    @Override
    public Mono<TelemetryRecord> recordBackfill(TelemetryBackfillDetectedEvent event) {
        return recordSequenced(event.sample());
    }

    private Mono<TelemetryRecord> appendRevision(TelemetryRecord revision) {
        return repository.append(revision).doOnNext(appended -> revisionsAppended.offer(new TelemetryRevisionAppendedEvent(appended.id(), appended.deviceId(), appended.metric(), appended.tDevice(), appended.revision())));
    }

    @Override
    public Mono<TelemetryRecord> recordSequenced(TelemetrySampleEvent sample) {
        return repository.findLatestRevision(sample.deviceId(), sample.metric(), sample.tDevice()).flatMap(latest -> latest.value() == sample.value() && latest.validationStatus().equals(sample.status()) ? Mono.just(latest) : appendRevision(latest.reviseWith(sample.value(), sample.tIngress(), sample.status()))).switchIfEmpty(Mono.defer(() -> repository.append(TelemetryRecord.original(sample.deviceId(), sample.metric(), sample.value(), sample.tDevice(), sample.tIngress(), sample.status()))));
    }
}
