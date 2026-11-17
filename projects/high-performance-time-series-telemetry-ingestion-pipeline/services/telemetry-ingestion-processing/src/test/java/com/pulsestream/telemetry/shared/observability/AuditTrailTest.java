package com.pulsestream.telemetry.shared.observability;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.lang.reflect.Method;
import java.time.Instant;
import java.util.Arrays;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class AuditTrailTest {

    private static final AuditEntry ENTRY =
            new AuditEntry("intake", "intake.receive", "accepted", Instant.EPOCH, "corr-1");

    @Test
    void port_declaration_hasExactlyRecordMethod() {
        Method[] methods = AuditTrail.class.getDeclaredMethods();

        assertThat(AuditTrail.class.isInterface()).isTrue();
        assertThat(Arrays.stream(methods).map(Method::getName)).containsExactly("record");
        assertThat(methods[0].getParameterTypes()).containsExactly(AuditEntry.class);
        assertThat(methods[0].getReturnType()).isEqualTo(Mono.class);
    }

    @Test
    void record_mockedPort_completesEmptyAndReceivesEntry() {
        AuditTrail trail = mock(AuditTrail.class);
        when(trail.record(ENTRY)).thenReturn(Mono.empty());

        StepVerifier.create(trail.record(ENTRY)).verifyComplete();

        verify(trail).record(ENTRY);
    }
}
