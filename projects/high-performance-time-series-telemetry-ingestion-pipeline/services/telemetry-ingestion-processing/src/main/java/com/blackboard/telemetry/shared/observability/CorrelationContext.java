package com.blackboard.telemetry.shared.observability;

import reactor.core.publisher.Mono;

public class CorrelationContext {

    private static final String CONTEXT_KEY = "requestId";

    private static final String HEADER_NAME = "X-Request-Id";

    public static final String UNCORRELATED = "UNCORRELATED";

    private CorrelationContext() {
    }

    public static String contextKey() {
        return CONTEXT_KEY;
    }

    public static String headerName() {
        return HEADER_NAME;
    }

    public static Mono<String> current() {
        return Mono.deferContextual(ctx -> Mono.just(ctx.getOrDefault(CONTEXT_KEY, UNCORRELATED)));
    }
}
