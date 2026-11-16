package com.blackboard.telemetry.ingestion.api;

import com.blackboard.telemetry.shared.observability.CorrelationContext;
import java.util.UUID;
import java.util.regex.Pattern;
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

    private static final int MAX_REQUEST_ID_LENGTH = 128;
    private static final Pattern ALLOWED_REQUEST_ID = Pattern.compile("[A-Za-z0-9._-]+");

    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String inbound = exchange.getRequest().getHeaders().getFirst(CorrelationContext.headerName());
        String requestId = isAcceptable(inbound) ? inbound : UUID.randomUUID().toString();
        exchange.getResponse().getHeaders().set(CorrelationContext.headerName(), requestId);
        return chain.filter(exchange).contextWrite(context -> context.put(CorrelationContext.contextKey(), requestId));
    }

    private static boolean isAcceptable(String candidate) {
        return candidate != null
                && !candidate.isBlank()
                && candidate.length() <= MAX_REQUEST_ID_LENGTH
                && ALLOWED_REQUEST_ID.matcher(candidate).matches();
    }
}
