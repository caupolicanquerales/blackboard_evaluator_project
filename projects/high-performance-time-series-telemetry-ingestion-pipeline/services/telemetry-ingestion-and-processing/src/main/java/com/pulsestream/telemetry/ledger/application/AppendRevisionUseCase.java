package com.pulsestream.telemetry.ledger.application;

import com.pulsestream.telemetry.ledger.domain.TelemetryRevision;
import com.pulsestream.telemetry.ledger.domain.TelemetryRevisionAppended;
import java.util.Objects;
import org.springframework.stereotype.Service;

@Service
public class AppendRevisionUseCase {

    private final TelemetryLedgerRepository repository;

    private final TelemetryRevisionEventPublisher publisher;

    public AppendRevisionUseCase(TelemetryLedgerRepository repository, TelemetryRevisionEventPublisher publisher) {
        this.repository = Objects.requireNonNull(repository, "repository");
        this.publisher = Objects.requireNonNull(publisher, "publisher");
    }

    public TelemetryRevision execute(AppendRevisionCommand command) {
        Objects.requireNonNull(command, "command");
        long next = repository.findRevisions(command.key()).stream().mapToLong(TelemetryRevision::revision).max().orElse(0L) + 1L;
        TelemetryRevision appended = repository.append(new TelemetryRevision(command.key(), next, command.value()));
        publisher.publish(new TelemetryRevisionAppended(appended.key(), appended.revision()));
        return appended;
    }
}
