package com.pulsestream.telemetry.shared.observability;

import reactor.core.publisher.Mono;

public interface AuditTrail {

    Mono<Void> record(AuditEntry entry);
}
