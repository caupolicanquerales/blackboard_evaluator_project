package com.blackboard.telemetry.shared.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import java.time.Clock;

@Configuration
@EnableConfigurationProperties(TelemetryProperties.class)
public class TelemetryConfiguration {

    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }
}
