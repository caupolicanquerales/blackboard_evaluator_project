package com.pulsestream.telemetry.ledger.application;

import com.pulsestream.telemetry.ledger.domain.TelemetryEventKey;
import com.pulsestream.telemetry.ledger.domain.TelemetryRevision;
import java.util.List;

public interface TelemetryLedgerRepository {

    List<TelemetryRevision> findRevisions(TelemetryEventKey key);

    TelemetryRevision append(TelemetryRevision revision);
}
