package com.blackboard.telemetry.shared.audit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class AuditEntryTest {

    private static final Instant NOW = Instant.parse("2025-01-01T00:00:00Z");

    private static AuditEntry entry(String actor, AuditAction action, String outcome,
                                    Instant timestamp, String correlationId) {
        return new AuditEntry(actor, action, outcome, timestamp, correlationId);
    }

    @ParameterizedTest
    @ValueSource(strings = {"SUCCESS", "FAILURE"})
    void accessors_validArguments_returnConstructedValues(String outcome) {
        AuditEntry result = entry("ingest-service", AuditAction.INGEST_PACKET, outcome, NOW, "req-1");

        assertThat(result.actor()).isEqualTo("ingest-service");
        assertThat(result.action()).isEqualTo(AuditAction.INGEST_PACKET);
        assertThat(result.outcome()).isEqualTo(outcome);
        assertThat(result.timestamp()).isEqualTo(NOW);
        assertThat(result.correlationId()).isEqualTo("req-1");
    }

    @Test
    void constructor_nullActor_throwsNullPointerException() {
        assertThatThrownBy(() -> entry(null, AuditAction.INGEST_PACKET, "SUCCESS", NOW, "req-1"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullAction_throwsNullPointerException() {
        assertThatThrownBy(() -> entry("actor", null, "SUCCESS", NOW, "req-1"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullOutcome_throwsNullPointerException() {
        assertThatThrownBy(() -> entry("actor", AuditAction.INGEST_PACKET, null, NOW, "req-1"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullTimestamp_throwsNullPointerException() {
        assertThatThrownBy(() -> entry("actor", AuditAction.INGEST_PACKET, "SUCCESS", null, "req-1"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_nullCorrelationId_throwsNullPointerException() {
        assertThatThrownBy(() -> entry("actor", AuditAction.INGEST_PACKET, "SUCCESS", NOW, null))
                .isInstanceOf(NullPointerException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   "})
    void constructor_blankActor_throwsIllegalArgumentException(String actor) {
        assertThatThrownBy(() -> entry(actor, AuditAction.INGEST_PACKET, "SUCCESS", NOW, "req-1"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   "})
    void constructor_blankCorrelationId_throwsIllegalArgumentException(String correlationId) {
        assertThatThrownBy(() -> entry("actor", AuditAction.INGEST_PACKET, "SUCCESS", NOW, correlationId))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"OK", "success", "Failure", ""})
    void constructor_outcomeNotSuccessOrFailure_throwsIllegalArgumentException(String outcome) {
        assertThatThrownBy(() -> entry("actor", AuditAction.INGEST_PACKET, outcome, NOW, "req-1"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
