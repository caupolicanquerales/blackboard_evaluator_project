package com.blackboard.telemetry.shared.audit;

import java.time.Instant;
import java.util.Objects;
import com.blackboard.telemetry.shared.audit.AuditAction;

public record AuditEntry(String actor, AuditAction action, String outcome, Instant timestamp, String correlationId) {

    public AuditEntry(String actor, AuditAction action, String outcome, Instant timestamp, String correlationId) {
        Objects.requireNonNull(actor, "actor");
        Objects.requireNonNull(action, "action");
        Objects.requireNonNull(outcome, "outcome");
        Objects.requireNonNull(timestamp, "timestamp");
        Objects.requireNonNull(correlationId, "correlationId");
        if (actor.isBlank()) {
            throw new IllegalArgumentException("actor must not be blank");
        }
        if (correlationId.isBlank()) {
            throw new IllegalArgumentException("correlationId must not be blank");
        }
        if (!outcome.equals("SUCCESS") && !outcome.equals("FAILURE")) {
            throw new IllegalArgumentException("outcome must be SUCCESS or FAILURE");
        }
    }
}
