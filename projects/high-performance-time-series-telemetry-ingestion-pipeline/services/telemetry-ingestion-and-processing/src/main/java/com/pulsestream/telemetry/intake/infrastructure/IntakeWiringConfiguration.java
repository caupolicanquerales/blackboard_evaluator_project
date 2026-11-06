package com.pulsestream.telemetry.intake.infrastructure;

import com.pulsestream.telemetry.intake.application.IntakeTelemetryUseCase;
import com.pulsestream.telemetry.intake.application.ReorderingEventPort;
import com.pulsestream.telemetry.intake.domain.MetricBoundary;
import com.pulsestream.telemetry.intake.domain.MetricBoundaryPolicy;
import java.time.Clock;
import java.util.Map;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import reactor.core.publisher.Mono;

@Configuration
public class IntakeWiringConfiguration {

    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }

    @Bean
    public MetricBoundaryPolicy metricBoundaryPolicy() {
        return new MetricBoundaryPolicy(Map.<String, MetricBoundary>of());
    }

    @Bean
    public ReorderingEventPort reorderingEventPort() {
        return event -> Mono.empty();
    }

    @Bean
    public IntakeTelemetryUseCase intakeTelemetryUseCase(MetricBoundaryPolicy policy, ReorderingEventPort port, Clock clock) {
        return new IntakeTelemetryUseCase(policy, port, clock);
    }
}
