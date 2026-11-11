package com.pulsestream.telemetry.shared.config;

import java.time.Clock;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(TelemetryProperties.class)
public class TelemetryWiringConfiguration {

    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }
}
