package com.blackboard.telemetry.shared.observability;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class CorrelationIdWebFilterTest {

    private final CorrelationIdWebFilter filter = new CorrelationIdWebFilter();

    private static final class Probe implements WebFilterChain {
        final AtomicInteger calls = new AtomicInteger();
        final AtomicReference<Object> contextValue = new AtomicReference<>();

        @Override
        public Mono<Void> filter(ServerWebExchange exchange) {
            calls.incrementAndGet();
            return Mono.deferContextual(ctx -> {
                contextValue.set(ctx.getOrDefault(CorrelationIdWebFilter.CONTEXT_KEY, null));
                return Mono.empty();
            });
        }
    }

    private static MockServerWebExchange exchange(String requestId) {
        MockServerHttpRequest.BaseBuilder<?> builder = MockServerHttpRequest.get("/x");
        if (requestId != null) {
            builder.header("X-Request-Id", requestId);
        }
        return MockServerWebExchange.from(builder);
    }

    @Test
    void constants_haveContractValues() {
        assertThat(CorrelationIdWebFilter.HEADER).isEqualTo("X-Request-Id");
        assertThat(CorrelationIdWebFilter.CONTEXT_KEY).isEqualTo("requestId");
    }

    @Test
    void filter_headerPresent_adoptsValueInContext() {
        Probe probe = new Probe();

        StepVerifier.create(filter.filter(exchange("abc-123"), probe)).verifyComplete();

        assertThat(probe.contextValue.get()).isEqualTo("abc-123");
    }

    @Test
    void filter_headerPresent_echoesValueInResponse() {
        MockServerWebExchange exchange = exchange("abc-123");

        filter.filter(exchange, new Probe()).block();

        assertThat(exchange.getResponse().getHeaders().getFirst("X-Request-Id")).isEqualTo("abc-123");
    }

    @Test
    void filter_headerAbsent_generatesUuidInContextAndResponse() {
        Probe probe = new Probe();
        MockServerWebExchange exchange = exchange(null);

        filter.filter(exchange, probe).block();

        String echoed = exchange.getResponse().getHeaders().getFirst("X-Request-Id");
        assertThat(echoed).isNotBlank();
        assertThat(UUID.fromString(echoed)).isNotNull();
        assertThat(probe.contextValue.get()).isEqualTo(echoed);
    }

    @Test
    void filter_anyRequest_invokesChainExactlyOnce() {
        Probe probe = new Probe();

        filter.filter(exchange(null), probe).block();

        assertThat(probe.calls.get()).isEqualTo(1);
    }
}
