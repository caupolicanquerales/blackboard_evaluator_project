package com.blackboard.telemetry.shared.observability;

import java.util.UUID;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

@Component
public class CorrelationIdWebFilter implements WebFilter {

    public static final String HEADER = "X-Request-Id";

    public static final String CONTEXT_KEY = "requestId";

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String inbound = exchange.getRequest().getHeaders().getFirst(HEADER);
        String requestId = inbound == null || inbound.isBlank() ? UUID.randomUUID().toString() : inbound;
        exchange.getResponse().getHeaders().set(HEADER, requestId);
        return chain.filter(exchange).contextWrite(ctx -> ctx.put(CONTEXT_KEY, requestId));
    }
}
