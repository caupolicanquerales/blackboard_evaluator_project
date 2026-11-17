package com.pulsestream.telemetry.intake.api;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class CorrelationWebFilterTest {

    private final CorrelationWebFilter filter = new CorrelationWebFilter();

    private static MockServerWebExchange exchange(String requestId) {
        MockServerHttpRequest.BaseBuilder<?> builder = MockServerHttpRequest.get("/x");
        if (requestId != null) {
            builder.header(CorrelationWebFilter.HEADER, requestId);
        }
        return MockServerWebExchange.from(builder);
    }

    private static WebFilterChain capturing(AtomicReference<Object> seen) {
        return ex -> Mono.deferContextual(ctx -> {
            seen.set(ctx.getOrDefault(CorrelationWebFilter.CONTEXT_KEY, null));
            return Mono.empty();
        });
    }

    @Test
    void filter_inboundHeaderPresent_adoptsItInResponseAndContext() {
        MockServerWebExchange exchange = exchange("req-123");
        AtomicReference<Object> seen = new AtomicReference<>();

        StepVerifier.create(filter.filter(exchange, capturing(seen))).verifyComplete();

        assertThat(exchange.getResponse().getHeaders().getFirst("X-Request-Id")).isEqualTo("req-123");
        assertThat(seen.get()).isEqualTo("req-123");
    }

    @Test
    void filter_inboundHeaderAbsent_generatesUuidEchoedAndInContext() {
        MockServerWebExchange exchange = exchange(null);
        AtomicReference<Object> seen = new AtomicReference<>();

        StepVerifier.create(filter.filter(exchange, capturing(seen))).verifyComplete();

        String echoed = exchange.getResponse().getHeaders().getFirst("X-Request-Id");
        assertThat(echoed).isNotBlank();
        assertThat(java.util.UUID.fromString(echoed)).isNotNull();
        assertThat(seen.get()).isEqualTo(echoed);
    }

    @Test
    void constants_exposeContractKeys() {
        assertThat(CorrelationWebFilter.CONTEXT_KEY).isEqualTo("requestId");
        assertThat(CorrelationWebFilter.HEADER).isEqualTo("X-Request-Id");
    }
}
