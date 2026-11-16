package com.blackboard.telemetry.ingestion.api;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

import com.blackboard.telemetry.shared.observability.CorrelationContext;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class CorrelationWebFilterTest {

    private final CorrelationWebFilter filter = new CorrelationWebFilter();

    private MockServerWebExchange exchange(String headerValue) {
        MockServerHttpRequest.BaseBuilder<?> request = MockServerHttpRequest.post("/api/v1/telemetry/packets");
        if (headerValue != null) {
            request.header(CorrelationContext.headerName(), headerValue);
        }
        return MockServerWebExchange.from(request);
    }

    private String run(MockServerWebExchange exchange, AtomicReference<String> seen) {
        WebFilterChain chain = ex -> CorrelationContext.current().doOnNext(seen::set).then();
        StepVerifier.create(filter.filter(exchange, chain)).verifyComplete();
        return exchange.getResponse().getHeaders().getFirst(CorrelationContext.headerName());
    }

    @Test
    void filter_validInboundHeader_adoptsItInResponseAndContext() {
        AtomicReference<String> seen = new AtomicReference<>();

        String header = run(exchange("req-1.A_b"), seen);

        assertThat(header).isEqualTo("req-1.A_b");
        assertThat(seen.get()).isEqualTo("req-1.A_b");
    }

    @Test
    void filter_headerAbsent_generatesUuid() {
        AtomicReference<String> seen = new AtomicReference<>();

        String header = run(exchange(null), seen);

        assertThat(java.util.UUID.fromString(header)).isNotNull();
        assertThat(seen.get()).isEqualTo(header);
    }

    @Test
    void filter_blankHeader_generatesUuid() {
        AtomicReference<String> seen = new AtomicReference<>();

        String header = run(exchange("   "), seen);

        assertThat(java.util.UUID.fromString(header)).isNotNull();
        assertThat(seen.get()).isEqualTo(header);
    }

    @Test
    void filter_headerWithIllegalCharacters_replacedByUuid() {
        AtomicReference<String> seen = new AtomicReference<>();

        String header = run(exchange("bad id!"), seen);

        assertThat(header).isNotEqualTo("bad id!");
        assertThat(java.util.UUID.fromString(header)).isNotNull();
    }

    @Test
    void filter_headerOf128Chars_isAdopted() {
        String id = "a".repeat(128);
        AtomicReference<String> seen = new AtomicReference<>();

        assertThat(run(exchange(id), seen)).isEqualTo(id);
    }

    @Test
    void filter_headerOf129Chars_isReplaced() {
        String id = "a".repeat(129);
        AtomicReference<String> seen = new AtomicReference<>();

        String header = run(exchange(id), seen);

        assertThat(header).isNotEqualTo(id);
        assertThat(java.util.UUID.fromString(header)).isNotNull();
    }

    @Test
    void filter_twoRequestsWithoutHeader_generateDistinctIds() {
        String first = run(exchange(null), new AtomicReference<>());
        String second = run(exchange(null), new AtomicReference<>());

        assertThat(first).isNotEqualTo(second);
    }

    @Test
    void filter_chainSubscribed_exactlyOnce() {
        AtomicReference<Integer> calls = new AtomicReference<>(0);
        WebFilterChain chain = ex -> Mono.fromRunnable(() -> calls.set(calls.get() + 1));

        StepVerifier.create(filter.filter(exchange("x"), chain)).verifyComplete();

        assertThat(calls.get()).isEqualTo(1);
    }
}
