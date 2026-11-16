package com.blackboard.telemetry.shared.observability;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import reactor.test.StepVerifier;

class CorrelationContextTest {

    @Test
    void contextKey_always_returnsRequestId() {
        assertThat(CorrelationContext.contextKey()).isEqualTo("requestId");
    }

    @Test
    void headerName_always_returnsXRequestId() {
        assertThat(CorrelationContext.headerName()).isEqualTo("X-Request-Id");
    }

    @Test
    void current_keyPresentInContext_emitsRequestId() {
        StepVerifier.create(CorrelationContext.current()
                        .contextWrite(ctx -> ctx.put("requestId", "req-123")))
                .expectNext("req-123")
                .verifyComplete();
    }

    @Test
    void current_keyAbsent_emitsUncorrelated() {
        StepVerifier.create(CorrelationContext.current())
                .expectNext("UNCORRELATED")
                .verifyComplete();
    }
}
