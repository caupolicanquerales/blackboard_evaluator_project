package com.pulsestream.telemetry.reordering.application;

import java.time.Duration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import reactor.core.publisher.Mono;

@Configuration
public class ReorderingWiringConfiguration {

    @Bean
    public LedgerEventPort ledgerEventPort() {
        return event -> Mono.empty();
    }

    @Bean
    public Duration reorderingWindow() {
        return Duration.ofSeconds(5);
    }
}
