package com.pulsestream.telemetry.ingestion.application;

import reactor.core.publisher.Mono;

public interface AuditTrail {

    Mono<Void> record(AuditEntry entry);
}
