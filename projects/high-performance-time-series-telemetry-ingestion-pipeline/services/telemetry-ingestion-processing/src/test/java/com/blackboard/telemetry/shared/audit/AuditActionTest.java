package com.blackboard.telemetry.shared.audit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class AuditActionTest {

    @Test
    void values_called_returnsExactConstantsInOrder() {
        AuditAction[] result = AuditAction.values();

        assertThat(result).containsExactly(
                AuditAction.INGEST_PACKET,
                AuditAction.VALIDATE_SAMPLE,
                AuditAction.APPEND_REVISION,
                AuditAction.BROADCAST_WINDOW);
    }

    @ParameterizedTest
    @EnumSource(AuditAction.class)
    void valueOf_constantName_returnsSameConstant(AuditAction action) {
        AuditAction result = AuditAction.valueOf(action.name());

        assertThat(result).isSameAs(action);
    }

    @Test
    void valueOf_unknownName_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> AuditAction.valueOf("UNKNOWN_ACTION"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void valueOf_nullName_throwsNullPointerException() {
        assertThatThrownBy(() -> AuditAction.valueOf(null))
                .isInstanceOf(NullPointerException.class);
    }
}
