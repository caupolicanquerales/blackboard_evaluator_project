package com.blackboard.telemetry.shared.audit;

import reactor.core.publisher.Mono;

public interface AuditTrail {

    Mono<Void> record(AuditEntry entry);
}
