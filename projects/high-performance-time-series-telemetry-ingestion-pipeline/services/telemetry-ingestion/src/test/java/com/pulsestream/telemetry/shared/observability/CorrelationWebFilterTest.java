package com.pulsestream.telemetry.shared.observability;

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

    private WebFilterChain capturing(AtomicReference<Object> captured) {
        return ex -> Mono.deferContextual(ctx -> {
            captured.set(ctx.getOrDefault(CorrelationWebFilter.contextKey(), null));
            return ex.getResponse().setComplete();
        });
    }

    @Test
    void contextKey_returnsRequestId() {
        assertThat(CorrelationWebFilter.contextKey()).isEqualTo("requestId");
    }

    @Test
    void headerName_returnsXRequestId() {
        assertThat(CorrelationWebFilter.headerName()).isEqualTo("X-Request-Id");
    }

    @Test
    void filter_incomingHeader_isAdoptedInContext() {
        var exchange = MockServerWebExchange.from(MockServerHttpRequest.get("/x")
                .header("X-Request-Id", "req-123").build());
        var captured = new AtomicReference<Object>();

        StepVerifier.create(filter.filter(exchange, capturing(captured))).verifyComplete();

        assertThat(captured.get()).isEqualTo("req-123");
    }

    @Test
    void filter_incomingHeader_isEchoedOnResponse() {
        var exchange = MockServerWebExchange.from(MockServerHttpRequest.get("/x")
                .header("X-Request-Id", "req-123").build());

        StepVerifier.create(filter.filter(exchange, capturing(new AtomicReference<>()))).verifyComplete();

        assertThat(exchange.getResponse().getHeaders().getFirst("X-Request-Id")).isEqualTo("req-123");
    }

    @Test
    void filter_headerAbsent_generatesNonBlankIdInContext() {
        var exchange = MockServerWebExchange.from(MockServerHttpRequest.get("/x").build());
        var captured = new AtomicReference<Object>();

        StepVerifier.create(filter.filter(exchange, capturing(captured))).verifyComplete();

        assertThat(captured.get()).isInstanceOf(String.class);
        assertThat((String) captured.get()).isNotBlank();
    }

    @Test
    void filter_headerAbsent_responseHeaderMatchesGeneratedContextId() {
        var exchange = MockServerWebExchange.from(MockServerHttpRequest.get("/x").build());
        var captured = new AtomicReference<Object>();

        StepVerifier.create(filter.filter(exchange, capturing(captured))).verifyComplete();

        assertThat(exchange.getResponse().getHeaders().getFirst("X-Request-Id")).isEqualTo(captured.get());
    }

    @Test
    void filter_headerAbsentTwice_generatesDistinctIds() {
        var first = new AtomicReference<Object>();
        var second = new AtomicReference<Object>();

        filter.filter(MockServerWebExchange.from(MockServerHttpRequest.get("/x").build()), capturing(first)).block();
        filter.filter(MockServerWebExchange.from(MockServerHttpRequest.get("/x").build()), capturing(second)).block();

        assertThat(first.get()).isNotEqualTo(second.get());
    }
}
