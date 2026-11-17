package com.pulsestream.telemetry.intake.api;

import java.util.UUID;
import reactor.core.publisher.Mono;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import org.springframework.stereotype.Component;

@Component
public class CorrelationWebFilter implements WebFilter {

    public static final String CONTEXT_KEY = "requestId";

    public static final String HEADER = "X-Request-Id";

    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String inbound = exchange.getRequest().getHeaders().getFirst(HEADER);
        String requestId = inbound == null || inbound.isBlank() ? UUID.randomUUID().toString() : inbound;
        exchange.getResponse().getHeaders().set(HEADER, requestId);
        return chain.filter(exchange).contextWrite(context -> context.put(CONTEXT_KEY, requestId));
    }
}
