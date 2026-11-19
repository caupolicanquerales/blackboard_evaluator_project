package com.pulsestream.telemetry.shared.observability;

import java.util.UUID;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class CorrelationWebFilter implements WebFilter {

    private static final String CONTEXT_KEY = "requestId";

    private static final String HEADER_NAME = "X-Request-Id";

    public static String contextKey() {
        return CONTEXT_KEY;
    }

    public static String headerName() {
        return HEADER_NAME;
    }

    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String requestId = resolveRequestId(exchange);
        exchange.getResponse().getHeaders().set(HEADER_NAME, requestId);
        return chain.filter(exchange).contextWrite(ctx -> ctx.put(CONTEXT_KEY, requestId));
    }

    private static String resolveRequestId(ServerWebExchange exchange) {
        String incoming = exchange.getRequest().getHeaders().getFirst(HEADER_NAME);
        return (incoming == null || incoming.isBlank()) ? UUID.randomUUID().toString() : incoming.trim();
    }
}
