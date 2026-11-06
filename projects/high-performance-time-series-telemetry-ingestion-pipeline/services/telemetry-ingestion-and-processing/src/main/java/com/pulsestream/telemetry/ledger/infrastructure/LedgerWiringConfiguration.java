package com.pulsestream.telemetry.ledger.infrastructure;

import com.pulsestream.telemetry.ledger.application.TelemetryLedgerRepository;
import com.pulsestream.telemetry.ledger.application.TelemetryRevisionEventPublisher;
import com.pulsestream.telemetry.ledger.domain.EventRevision;
import com.pulsestream.telemetry.ledger.domain.TelemetryRevision;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class LedgerWiringConfiguration {

    @Bean
    public TelemetryLedgerRepository telemetryLedgerRepository(R2dbcEventRevisionRepository delegate) {
        return new TelemetryLedgerRepository() {
            @Override
            public java.util.List<TelemetryRevision> findRevisions(com.pulsestream.telemetry.ledger.domain.TelemetryEventKey key) {
                return delegate.history(key.deviceId(), key.metric(), key.timestamp(), key.timestamp())
                        .map(r -> new TelemetryRevision(key, r.revision(), Double.parseDouble(r.rawPayload())))
                        .collectList().block();
            }

            @Override
            public TelemetryRevision append(TelemetryRevision revision) {
                var key = revision.key();
                delegate.append(new EventRevision(key.deviceId(), key.metric(), key.timestamp(), revision.revision(), revision.value())).block();
                return revision;
            }
        };
    }

    @Bean
    public TelemetryRevisionEventPublisher telemetryRevisionEventPublisher() {
        return event -> { };
    }
}
